"""
The only module allowed to move coins.

Rules enforced here:
1. All movements happen inside a single transaction.
2. Wallets are locked with select_for_update(), always in ascending primary
   key order — concurrent transfers between the same accounts therefore
   acquire locks in the same order and cannot deadlock.
3. Every movement is a balanced set of ledger rows summing to zero.
4. Client-supplied idempotency keys are unique-indexed, so a retry (timeout,
   double tap) returns the original result instead of charging twice. The
   unique index makes this race-proof: if two identical requests slip past
   the pre-check, one insert loses and we return the winner's row.
5. Coins in flight (question stakes, goal pledges) sit in a real system
   escrow wallet, never in a status flag — the books balance mid-flight.
"""

import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from config.exceptions import APIError

from .models import Gift, GoalPledge, LedgerEntry, Question, Wallet


class InsufficientBalanceError(APIError):
    code = "insufficient_balance"
    message = "Not enough coins."


class InactiveGiftTypeError(APIError):
    code = "gift_type_inactive"
    message = "This gift is not available."


class NoStageError(APIError):
    code = "no_speakers"
    message = "Nobody is on stage to receive a room gift."


class QuestionNotPendingError(APIError):
    code = "question_not_pending"
    message = "This question has already been resolved."


class PledgeNotAllowedError(APIError):
    code = "no_goal"
    message = "This room has no goal to pledge to."


# --- low-level primitives ---------------------------------------------------


def _wallet_id(user):
    return Wallet.objects.values_list("id", flat=True).get(user=user)


def _lock(wallet_ids):
    """Lock the given wallets in ascending pk order; returns {id: wallet}."""
    wallets = (
        Wallet.objects.select_for_update()
        .filter(id__in=set(wallet_ids))
        .order_by("pk")
    )
    return {w.id: w for w in wallets}


def _post(legs, *, key_base, reason=None, **refs):
    """
    Write a balanced group of ledger entries and update the cached balances.

    `legs` is a list of (wallet, delta, reason) tuples whose deltas must sum
    to zero. Callers must already hold the wallet locks.
    """
    assert sum(delta for _, delta, _ in legs) == 0, "ledger entries must net to zero"
    entries = []
    for index, (wallet, delta, leg_reason) in enumerate(legs):
        if delta == 0:
            continue
        entries.append(
            LedgerEntry(
                wallet=wallet,
                delta_coins=delta,
                reason=leg_reason or reason,
                idempotency_key=f"{key_base}:{index}",
                **refs,
            )
        )
        wallet.balance_coins += delta
    LedgerEntry.objects.bulk_create(entries)
    for wallet, _, _ in legs:
        wallet.save(update_fields=("balance_coins",))
    return entries


def _transfer(*, src_id, dst_id, coins, debit_reason, credit_reason, key_base, **refs):
    """Move coins between two wallets. Caller must be inside atomic()."""
    wallets = _lock([src_id, dst_id])
    src, dst = wallets[src_id], wallets[dst_id]
    if src.balance_coins < coins:
        raise InsufficientBalanceError()
    _post(
        [(src, -coins, debit_reason), (dst, coins, credit_reason)],
        key_base=key_base,
        **refs,
    )
    return src, dst


def split_shares(total, weights):
    """
    Distribute `total` across `weights` so the parts sum to exactly `total`.

    Uses the largest-remainder method: floor every share, then hand the
    leftover coins to the largest fractional remainders. Naive rounding would
    create or destroy coins, which the ledger's zero-sum assertion forbids.
    """
    count = len(weights)
    if count == 0:
        return []
    weight_sum = sum(weights)
    if weight_sum <= 0:  # nobody has measurable stage time — split evenly
        weights = [1] * count
        weight_sum = count
    exact = [total * w / weight_sum for w in weights]
    shares = [int(value) for value in exact]
    leftover = total - sum(shares)
    order = sorted(range(count), key=lambda i: exact[i] - shares[i], reverse=True)
    for i in order[:leftover]:
        shares[i] += 1
    return shares


# --- top-ups ----------------------------------------------------------------


def topup(*, user, coins, idempotency_key=None):
    """
    Credit coins to a user's wallet (stub for a payment-gateway callback).
    Single-entry because the counterparty is the payment provider, outside
    our coin system. Idempotent like every other movement.
    """
    key = idempotency_key or f"topup:{uuid.uuid4()}"
    if LedgerEntry.objects.filter(idempotency_key=key).exists():
        return Wallet.objects.get(user=user)
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(user=user)
        LedgerEntry.objects.create(
            wallet=wallet,
            delta_coins=coins,
            reason=LedgerEntry.Reason.TOPUP,
            idempotency_key=key,
        )
        wallet.balance_coins += coins
        wallet.save(update_fields=("balance_coins",))
    return wallet


# --- gifts ------------------------------------------------------------------


def send_gift(*, sender, room, gift_type, idempotency_key, recipient=None):
    """
    Send a gift. With `recipient`, coins go to that person. Without one it is
    a *room gift*: the coins are split across everyone currently on stage in
    proportion to how long they have been speaking, so co-hosting pays.

    Returns (gift, created). created=False means this key was already used.
    """
    if not gift_type.is_active:
        raise InactiveGiftTypeError()

    existing = Gift.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            sender_wallet_id = _wallet_id(sender)

            if recipient is not None:
                shares = [(recipient, gift_type.coins)]
            else:
                shares = _stage_shares(room, gift_type.coins)

            wallet_ids = [sender_wallet_id] + [_wallet_id(u) for u, _ in shares]
            wallets = _lock(wallet_ids)
            sender_wallet = wallets[sender_wallet_id]
            if sender_wallet.balance_coins < gift_type.coins:
                raise InsufficientBalanceError()

            gift = Gift.objects.create(
                sender=sender,
                recipient=recipient,
                room=room,
                gift_type=gift_type,
                coins=gift_type.coins,
                idempotency_key=idempotency_key,
            )
            legs = [(sender_wallet, -gift.coins, LedgerEntry.Reason.GIFT_SENT)]
            for user, amount in shares:
                legs.append(
                    (
                        wallets[_wallet_id(user)],
                        amount,
                        LedgerEntry.Reason.GIFT_RECEIVED,
                    )
                )
            _post(legs, key_base=idempotency_key, gift=gift)
    except IntegrityError:
        replay = Gift.objects.filter(idempotency_key=idempotency_key).first()
        if replay is not None:
            return replay, False
        raise

    return gift, True


def _stage_shares(room, coins):
    """[(user, coins)] split across on-stage participants by speaking time."""
    from apps.rooms.models import RoomParticipant

    on_stage = list(
        room.participants.filter(
            left_at__isnull=True,
            role__in=(RoomParticipant.Role.HOST, RoomParticipant.Role.SPEAKER),
        ).select_related("user")
    )
    if not on_stage:
        raise NoStageError()
    now = timezone.now()
    weights = [p.stage_seconds(now) for p in on_stage]
    amounts = split_shares(coins, weights)
    return [(p.user, amount) for p, amount in zip(on_stage, amounts) if amount > 0]


# --- paid questions ---------------------------------------------------------


def ask_question(*, asker, room, text, coins, idempotency_key):
    """Stake coins on a question. The coins move into escrow immediately."""
    existing = Question.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            escrow = Wallet.escrow()
            question = Question.objects.create(
                room=room, asker=asker, text=text, coins=coins,
                idempotency_key=idempotency_key,
            )
            _transfer(
                src_id=_wallet_id(asker),
                dst_id=escrow.id,
                coins=coins,
                debit_reason=LedgerEntry.Reason.QUESTION_ESCROW,
                credit_reason=LedgerEntry.Reason.QUESTION_ESCROW,
                key_base=f"{idempotency_key}:escrow",
                question=question,
            )
    except IntegrityError:
        replay = Question.objects.filter(idempotency_key=idempotency_key).first()
        if replay is not None:
            return replay, False
        raise

    return question, True


def _resolve_question(question_id, *, status, payee_getter, reason):
    """Shared settle/refund path: escrow -> somebody, exactly once."""
    with transaction.atomic():
        question = Question.objects.select_for_update().select_related(
            "room", "asker"
        ).get(pk=question_id)
        if question.status != Question.Status.PENDING:
            raise QuestionNotPendingError()
        escrow = Wallet.escrow()
        _transfer(
            src_id=escrow.id,
            dst_id=_wallet_id(payee_getter(question)),
            coins=question.coins,
            debit_reason=reason,
            credit_reason=reason,
            key_base=f"{question.idempotency_key}:{status}",
            question=question,
        )
        question.status = status
        question.resolved_at = timezone.now()
        question.save(update_fields=("status", "resolved_at"))
    return question


def answer_question(question):
    """Host answered it — the stake is released to the host."""
    return _resolve_question(
        question.pk,
        status=Question.Status.ANSWERED,
        payee_getter=lambda q: q.room.host,
        reason=LedgerEntry.Reason.QUESTION_PAID,
    )


def refund_question(question):
    """Declined or the room ended — the stake goes back to the asker."""
    return _resolve_question(
        question.pk,
        status=Question.Status.REFUNDED,
        payee_getter=lambda q: q.asker,
        reason=LedgerEntry.Reason.QUESTION_REFUND,
    )


def refund_pending_questions(room):
    """Called when a room ends: nobody keeps money for unanswered questions."""
    ids = list(
        room.questions.filter(status=Question.Status.PENDING).values_list(
            "id", flat=True
        )
    )
    for question_id in ids:
        refund_question(Question(pk=question_id))
    return len(ids)


# --- goal rooms -------------------------------------------------------------


def pledge(*, user, room, coins, idempotency_key):
    """
    Pledge coins toward a room's goal. Escrowed until the goal is reached
    (settles to the host) or the room ends short (refunded to everyone).
    """
    if not room.goal_coins:
        raise PledgeNotAllowedError()

    existing = GoalPledge.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            locked_room = type(room).objects.select_for_update().get(pk=room.pk)
            escrow = Wallet.escrow()
            record = GoalPledge.objects.create(
                room=locked_room, user=user, coins=coins,
                idempotency_key=idempotency_key,
            )
            _transfer(
                src_id=_wallet_id(user),
                dst_id=escrow.id,
                coins=coins,
                debit_reason=LedgerEntry.Reason.PLEDGE_ESCROW,
                credit_reason=LedgerEntry.Reason.PLEDGE_ESCROW,
                key_base=f"{idempotency_key}:pledge",
                pledge=record,
            )
            locked_room.pledged_coins += coins
            locked_room.save(update_fields=("pledged_coins",))

            if (
                locked_room.pledged_coins >= locked_room.goal_coins
                and locked_room.goal_reached_at is None
            ):
                _settle_goal(locked_room)
    except IntegrityError:
        replay = GoalPledge.objects.filter(idempotency_key=idempotency_key).first()
        if replay is not None:
            return replay, False
        raise

    return record, True


def _settle_goal(room):
    """Goal reached: every escrowed pledge is released to the host."""
    escrow = Wallet.escrow()
    host_wallet_id = _wallet_id(room.host)
    pledges = list(room.pledges.filter(status=GoalPledge.Status.ESCROWED))
    now = timezone.now()
    for record in pledges:
        _transfer(
            src_id=escrow.id,
            dst_id=host_wallet_id,
            coins=record.coins,
            debit_reason=LedgerEntry.Reason.PLEDGE_SETTLED,
            credit_reason=LedgerEntry.Reason.PLEDGE_SETTLED,
            key_base=f"{record.idempotency_key}:settled",
            pledge=record,
        )
        record.status = GoalPledge.Status.SETTLED
        record.resolved_at = now
    GoalPledge.objects.bulk_update(pledges, ("status", "resolved_at"))
    room.goal_reached_at = now
    room.save(update_fields=("goal_reached_at",))
    return len(pledges)


def refund_pledges(room):
    """Room ended without hitting its goal: everyone gets their coins back."""
    escrow = Wallet.escrow()
    now = timezone.now()
    pledges = list(room.pledges.filter(status=GoalPledge.Status.ESCROWED))
    for record in pledges:
        with transaction.atomic():
            _transfer(
                src_id=escrow.id,
                dst_id=_wallet_id(record.user),
                coins=record.coins,
                debit_reason=LedgerEntry.Reason.PLEDGE_REFUND,
                credit_reason=LedgerEntry.Reason.PLEDGE_REFUND,
                key_base=f"{record.idempotency_key}:refund",
                pledge=record,
            )
            record.status = GoalPledge.Status.REFUNDED
            record.resolved_at = now
            record.save(update_fields=("status", "resolved_at"))
    return len(pledges)
