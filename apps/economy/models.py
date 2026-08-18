from django.conf import settings
from django.db import models


class Wallet(models.Model):
    """
    balance_coins is a cache, not the source of truth: the balance is always
    derivable as SUM(ledger.delta_coins). The DB-level check constraint is the
    last line of defence — even buggy code cannot persist a negative balance.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    balance_coins = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance_coins__gte=0), name="wallet_balance_non_negative"
            )
        ]

    def __str__(self):
        return f"wallet<{self.user_id}>: {self.balance_coins}"


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
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gifts_received",
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


class LedgerEntry(models.Model):
    """
    Append-only. Money moves ONLY by inserting LedgerEntry rows inside a
    transaction; wallet.balance_coins is updated in the same transaction as a
    cache. A gift produces exactly two entries (debit + credit) summing to
    zero — double-entry bookkeeping.
    """

    class Reason(models.TextChoices):
        TOPUP = "topup"
        GIFT_SENT = "gift_sent"
        GIFT_RECEIVED = "gift_received"

    wallet = models.ForeignKey(
        Wallet, on_delete=models.PROTECT, related_name="entries"
    )
    delta_coins = models.BigIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    gift = models.ForeignKey(
        Gift, null=True, blank=True, on_delete=models.PROTECT, related_name="entries"
    )
    idempotency_key = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("wallet", "-created_at"))]
        verbose_name_plural = "ledger entries"
