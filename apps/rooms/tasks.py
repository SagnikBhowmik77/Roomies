from celery import shared_task


@shared_task
def notify_followers_of_live_room(room_id):
    """Create a WENT_LIVE notification for every follower of the host."""
    from apps.social.models import Follow, Notification

    from .models import Room

    try:
        room = Room.objects.select_related("host").get(pk=room_id)
    except Room.DoesNotExist:
        return 0

    follower_ids = Follow.objects.filter(following=room.host).values_list(
        "follower_id", flat=True
    )
    notifications = [
        Notification(
            user_id=follower_id,
            actor=room.host,
            verb=Notification.Verb.WENT_LIVE,
            room=room,
        )
        for follower_id in follower_ids.iterator()
    ]
    Notification.objects.bulk_create(notifications, batch_size=500)
    return len(notifications)
