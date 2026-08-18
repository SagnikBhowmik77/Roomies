from django.conf import settings
from django.db import models


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open"
        REVIEWED = "reviewed"
        ACTIONED = "actioned"

    class Reason(models.TextChoices):
        HARASSMENT = "harassment"
        SPAM = "spam"
        HATE_SPEECH = "hate_speech"
        IMPERSONATION = "impersonation"
        OTHER = "other"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made"
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_against",
    )
    room = models.ForeignKey(
        "rooms.Room", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("status", "created_at"))]
