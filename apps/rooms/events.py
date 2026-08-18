"""Push an event to everyone connected to a room's websocket group."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast(room_id, event, **payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:  # pragma: no cover - channels always configured
        return
    async_to_sync(channel_layer.group_send)(
        f"room_{room_id}", {"type": "room.event", "event": event, **payload}
    )
