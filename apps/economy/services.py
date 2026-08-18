"""
The only module allowed to move coins.

Rules enforced here:
1. All movements happen inside a single transaction.
2. Both wallets are locked with select_for_update(), always in ascending
   primary-key order — two concurrent gifts A->B and B->A therefore acquire
   locks in the same order and cannot deadlock.
3. Every movement is two ledger rows (debit + credit) summing to zero.
4. The client's Idempotency-Key is unique on Gift; a retry (timeout, double
   tap) returns the original gift instead of charging twice. The unique index
   makes this race-proof: if two identical requests slip past the pre-check,
   one insert loses and we return the winner's row.
"""

import uuid

from django.db import IntegrityError, transaction

from config.exceptions import APIError

from .models import Gift, LedgerEntry, Wallet


class InsufficientBalanceError(APIError):
    code = "insufficient_balance"
    message = "Not enough coins."


class InactiveGiftTypeError(APIError):
    code = "gift_type_inactive"
    message = "This gift is not available."


def _locked_wallets(*user_ids):
    """Lock wallets for the given users in consistent (pk) order."""
    wallets = list(
        Wallet.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("pk")
    )
    return {w.user_id: w for w in wallets}


def send_gift(*, sender, recipient, room, gift_type, idempotency_key):
    """
    Returns (gift, created). created=False means the idempotency key was
    seen before and this is a replay.
    """
    if not gift_type.is_active:
        raise InactiveGiftTypeError()

    existing = Gift.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            wallets = _locked_wallets(sender.id, recipient.id)
            sender_wallet = wallets[sender.id]
            recipient_wallet = wallets[recipient.id]

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
            entries = LedgerEntry.objects.bulk_create(
                [
                    LedgerEntry(
                        wallet=sender_wallet,
                        delta_coins=-gift.coins,
                        reason=LedgerEntry.Reason.GIFT_SENT,
                        gift=gift,
                        idempotency_key=f"{idempotency_key}:debit",
                    ),
                    LedgerEntry(
                        wallet=recipient_wallet,
                        delta_coins=gift.coins,
                        reason=LedgerEntry.Reason.GIFT_RECEIVED,
                        gift=gift,
                        idempotency_key=f"{idempotency_key}:credit",
                    ),
                ]
            )
            assert sum(e.delta_coins for e in entries) == 0

            sender_wallet.balance_coins -= gift.coins
            recipient_wallet.balance_coins += gift.coins
            sender_wallet.save(update_fields=("balance_coins",))
            recipient_wallet.save(update_fields=("balance_coins",))
    except IntegrityError:
        # Lost the idempotency race to a concurrent identical request:
        # return its result rather than erroring.
        replay = Gift.objects.filter(idempotency_key=idempotency_key).first()
        if replay is not None:
            return replay, False
        raise

    return gift, True


def topup(*, user, coins, idempotency_key=None):
    """
    Credit coins to a user's wallet (stub for a payment-gateway callback).
    Single-entry here because the counterparty is the payment provider,
    outside our coin system. Idempotent like send_gift: a replayed key
    returns the wallet untouched instead of double-crediting.
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
