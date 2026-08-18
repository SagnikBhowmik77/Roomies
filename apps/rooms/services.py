"""Room lifecycle. Ending a room is one path, whoever triggers it."""

from django.db import transaction
from django.utils import timezone

from .models import Room


def close_room(room):
    """
    End a room and settle everything it was holding: unanswered question
    stakes and (unless the goal was funded) every pledge go back to the
    people who staked them. Returns the refund counts.
    """
    from apps.economy import services as economy

    from .signals import room_ended

    with transaction.atomic():
        room.end()
    refunded_questions = economy.refund_pending_questions(room)
    refunded_pledges = 0 if room.goal_reached_at else economy.refund_pledges(room)
    room_ended.send(sender=Room, room=room)
    return {
        "refunded_questions": refunded_questions,
        "refunded_pledges": refunded_pledges,
    }


def expire_due_rooms():
    """
    Close time-boxed rooms whose clock has run out.

    Called opportunistically when the feed is read and from a Celery beat
    task, so a room ends on time even if nobody is looking at it.
    """
    due = Room.objects.filter(
        status=Room.Status.LIVE, ends_at__isnull=False, ends_at__lte=timezone.now()
    )
    closed = 0
    for room in due:
        close_room(room)
        closed += 1
    return closed
