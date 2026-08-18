from django.conf import settings
from django.db import models
from django.utils import timezone


class Room(models.Model):
    class Status(models.TextChoices):
        LIVE = "live"
        ENDED = "ended"

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_rooms"
    )
    title = models.CharField(max_length=100)
    topic = models.CharField(max_length=50, blank=True, db_index=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.LIVE
    )
    max_seats = models.PositiveSmallIntegerField(default=8)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Goal rooms: pledges are escrowed until the target is hit (settle to the
    # host) or the room ends short (refund everyone).
    goal_coins = models.PositiveIntegerField(null=True, blank=True)
    goal_title = models.CharField(max_length=120, blank=True)
    pledged_coins = models.PositiveIntegerField(default=0)
    goal_reached_at = models.DateTimeField(null=True, blank=True)
    # Denormalised counter, maintained under the same row lock as joins/leaves.
    # Source of truth remains RoomParticipant; this exists so the feed never
    # has to COUNT() per room.
    listener_count = models.PositiveIntegerField(default=0)

    class Meta:
        # the live feed's exact access path: WHERE status='live' ORDER BY started_at
        indexes = [models.Index(fields=("status", "started_at"))]
        ordering = ("-started_at",)

    def __str__(self):
        return f"{self.title} ({self.status})"

    def end(self):
        self.status = self.Status.ENDED
        self.ended_at = timezone.now()
        self.save(update_fields=("status", "ended_at"))
        self.participants.filter(left_at__isnull=True).update(left_at=self.ended_at)


class RoomMessage(models.Model):
    """Live chat, persisted so late joiners get history."""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=("room", "-created_at"))]


class RoomParticipant(models.Model):
    class Role(models.TextChoices):
        HOST = "host"
        SPEAKER = "speaker"
        LISTENER = "listener"

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.LISTENER)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    # Set when this participant gained the stage (host on creation, speaker on
    # promotion). Drives proportional revenue splits for room gifts.
    speaker_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # a user may rejoin a room they left, but can hold only one
            # active (left_at IS NULL) seat per room at a time
            models.UniqueConstraint(
                fields=("room", "user"),
                condition=models.Q(left_at__isnull=True),
                name="one_active_seat_per_room_user",
            )
        ]
        indexes = [models.Index(fields=("room", "left_at"))]

    @property
    def is_active(self):
        return self.left_at is None

    def stage_seconds(self, now=None):
        """Seconds spent on stage — the weight used for revenue splits."""
        if not self.speaker_since:
            return 0
        end = self.left_at or now or timezone.now()
        return max(0, (end - self.speaker_since).total_seconds())
