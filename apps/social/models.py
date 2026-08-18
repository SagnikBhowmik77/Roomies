from django.conf import settings
from django.db import models


class Follow(models.Model):
    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_set"
    )
    following = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_set"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("follower", "following"), name="unique_follow"
            ),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("following")),
                name="no_self_follow",
            ),
        ]
        # both directions are hot paths: "who do I follow" and "who follows me"
        indexes = [
            models.Index(fields=("follower", "created_at")),
            models.Index(fields=("following", "created_at")),
        ]

    def __str__(self):
        return f"{self.follower_id} -> {self.following_id}"


class Notification(models.Model):
    """Fan-out target for Celery: 'host you follow went live'."""

    class Verb(models.TextChoices):
        WENT_LIVE = "went_live"
        NEW_FOLLOWER = "new_follower"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    verb = models.CharField(max_length=20, choices=Verb.choices)
    room = models.ForeignKey(
        "rooms.Room", null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("user", "-created_at"))]
