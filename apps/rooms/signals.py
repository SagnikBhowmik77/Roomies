import django.dispatch
from django.dispatch import receiver

from .cache import invalidate_room_list

# Domain signals, fired explicitly from the view layer at the moments the
# feed actually changes (a post_save receiver would also fire on
# listener_count bumps, invalidating the cache far too often).
room_went_live = django.dispatch.Signal()
room_ended = django.dispatch.Signal()


@receiver(room_went_live)
@receiver(room_ended)
def _invalidate_feed(sender, room, **kwargs):
    invalidate_room_list()
