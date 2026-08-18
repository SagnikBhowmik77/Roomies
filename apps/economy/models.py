from django.conf import settings
from django.db import models


class Wallet(models.Model):
    """
    balance_coins is a cache, not the source of truth: the balance is always
    derivable as SUM(ledger.delta_coins). The DB-level check constraint is the
    last line of defence — even buggy code cannot persist a negative balance.

    Most wallets belong to a user. System wallets (user=NULL, label set) hold
    coins that are in flight — escrowed question stakes and goal pledges.
    Keeping escrow in a real wallet rather than a status flag means the
    invariant "total coins == sum of all top-ups" holds at every instant,
    including mid-escrow.
    """

    ESCROW = "escrow"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=32, blank=True)
    balance_coins = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_coins__gte=0), name="wallet_balance_non_negative"
            ),
            models.UniqueConstraint(
                fields=("label",),
                condition=models.Q(user__isnull=True),
                name="unique_system_wallet",
            ),
        ]

    def __str__(self):
        owner = self.user_id or f"system:{self.label}"
        return f"wallet<{owner}>: {self.balance_coins}"

    @classmethod
    def escrow(cls):
        """The singleton wallet that holds all in-flight coins."""
        wallet, _ = cls.objects.get_or_create(user=None, label=cls.ESCROW)
        return wallet


class GiftType(models.Model):
    """Catalog of purchasable gifts (rose, rocket, ...)."""

    name = models.CharField(max_length=50, unique=True)
    coins = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.coins})"


class Gift(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gifts_sent"
    )
    # NULL = a gift to the room: split across everyone on stage in proportion
    # to their time as a speaker (see services.send_gift).
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gifts_received",
        null=True,
        blank=True,
    )
    room = models.ForeignKey(
        "rooms.Room", on_delete=models.CASCADE, related_name="gifts"
    )
    gift_type = models.ForeignKey(GiftType, on_delete=models.PROTECT)
    # denormalised from gift_type at send time: catalog prices can change
    # later, historical gifts must not
    coins = models.PositiveIntegerField()
    # client-supplied Idempotency-Key; the unique index is what makes retries
    # safe under concurrency
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("recipient", "-created_at"))]


class Question(models.Model):
    """
    A paid question: the asker stakes coins to buy the host's attention.

    Coins are moved into the escrow wallet the moment the question is asked,
    and leave escrow exactly once — to the host when it is answered, or back
    to the asker if it is declined or the room ends unanswered. The stake is
    also the queue's sort key, so the host always sees the most valuable
    questions first.
    """

    class Status(models.TextChoices):
        PENDING = "pending"
        ANSWERED = "answered"
        REFUNDED = "refunded"

    room = models.ForeignKey(
        "rooms.Room", on_delete=models.CASCADE, related_name="questions"
    )
    asker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="questions_asked"
    )
    text = models.CharField(max_length=280)
    coins = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # the queue's exact access path: pending questions, highest stake first
        indexes = [models.Index(fields=("room", "status", "-coins"))]
        ordering = ("-coins", "created_at")

    def __str__(self):
        return f"Q({self.coins}) {self.text[:40]}"


class GoalPledge(models.Model):
    """
    A contribution toward a room's goal. Escrowed like a question stake:
    settles to the host only if the goal is reached, otherwise every pledge
    is refunded automatically — provably, because the coins never left the
    ledger.
    """

    class Status(models.TextChoices):
        ESCROWED = "escrowed"
        SETTLED = "settled"
        REFUNDED = "refunded"

    room = models.ForeignKey(
        "rooms.Room", on_delete=models.CASCADE, related_name="pledges"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pledges"
    )
    coins = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ESCROWED, db_index=True
    )
    idempotency_key = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("room", "status"))]


class LedgerEntry(models.Model):
    """
    Append-only. Money moves ONLY by inserting LedgerEntry rows inside a
    transaction; wallet.balance_coins is updated in the same transaction as a
    cache. Every movement is a balanced set of entries summing to zero —
    double-entry bookkeeping. Escrow is not a flag: held coins really sit in
    the system escrow wallet, so the books balance mid-flight too.
    """

    class Reason(models.TextChoices):
        TOPUP = "topup"
        GIFT_SENT = "gift_sent"
        GIFT_RECEIVED = "gift_received"
        QUESTION_ESCROW = "question_escrow"
        QUESTION_PAID = "question_paid"
        QUESTION_REFUND = "question_refund"
        PLEDGE_ESCROW = "pledge_escrow"
        PLEDGE_SETTLED = "pledge_settled"
        PLEDGE_REFUND = "pledge_refund"

    # reasons that represent coins a creator actually earned
    EARNING_REASONS = ("gift_received", "question_paid", "pledge_settled")

    wallet = models.ForeignKey(
        Wallet, on_delete=models.PROTECT, related_name="entries"
    )
    delta_coins = models.BigIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    gift = models.ForeignKey(
        Gift, null=True, blank=True, on_delete=models.PROTECT, related_name="entries"
    )
    question = models.ForeignKey(
        Question, null=True, blank=True, on_delete=models.PROTECT, related_name="entries"
    )
    pledge = models.ForeignKey(
        GoalPledge, null=True, blank=True, on_delete=models.PROTECT, related_name="entries"
    )
    idempotency_key = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("wallet", "-created_at"))]
        verbose_name_plural = "ledger entries"
