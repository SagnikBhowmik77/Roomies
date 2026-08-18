"""
One websocket per (user, room). Carries four kinds of traffic:

- chat        : persisted to RoomMessage, broadcast to the room
- presence    : peer_joined / peer_left, so clients update without polling
- signal      : WebRTC offer/answer/ICE relayed to ONE target peer — the
                server never touches audio, it only brokers the handshake
- speaking/mic/reaction/role : ephemeral UI state, broadcast, never stored
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

MAX_CHAT_LEN = 500


def public_user(user):
    return {"id": user.id, "display_name": user.display_name or str(user)}


class RoomConsumer(AsyncJsonWebsocketConsumer):
    @property
    def group(self):
        return f"room_{self.room_id}"

    def user_group(self, user_id):
        return f"room_{self.room_id}_user_{user_id}"

    async def connect(self):
        self.room_id = int(self.scope["url_route"]["kwargs"]["room_id"])
        self.user = self.scope["user"]
        if not getattr(self.user, "is_authenticated", False):
            await self.close(code=4401)
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.channel_layer.group_add(
            self.user_group(self.user.id), self.channel_name
        )
        await self.accept()
        await self.channel_layer.group_send(
            self.group,
            {"type": "room.event", "event": "peer_joined", "user": public_user(self.user)},
        )

    async def disconnect(self, code):
        if not getattr(self, "room_id", None) or not getattr(self.user, "id", None):
            return
        await self.channel_layer.group_discard(self.group, self.channel_name)
        await self.channel_layer.group_discard(
            self.user_group(self.user.id), self.channel_name
        )
        await self.channel_layer.group_send(
            self.group,
            {"type": "room.event", "event": "peer_left", "user": public_user(self.user)},
        )

    async def receive_json(self, content):
        kind = content.get("type")

        if kind == "chat":
            text = (content.get("text") or "").strip()[:MAX_CHAT_LEN]
            if not text:
                return
            message = await self._save_message(text)
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "room.event",
                    "event": "chat",
                    "user": public_user(self.user),
                    "text": text,
                    "id": message.id,
                    "created_at": message.created_at.isoformat(),
                },
            )

        elif kind == "signal":
            # targeted relay: only the intended peer receives it
            target = content.get("target")
            if target:
                await self.channel_layer.group_send(
                    self.user_group(int(target)),
                    {
                        "type": "room.event",
                        "event": "signal",
                        "from": self.user.id,
                        "data": content.get("data"),
                    },
                )

        elif kind == "caption":
            # Speech-to-text produced in the speaker's own browser. Broadcast
            # immediately for live accessibility; persist so the replay has a
            # transcript.
            text = (content.get("text") or "").strip()[:2000]
            if not text:
                return
            await self._save_caption(text, content.get("language") or "en-IN")
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "room.event",
                    "event": "caption",
                    "user": public_user(self.user),
                    "text": text,
                },
            )

        elif kind in ("speaking", "mic", "reaction"):
            await self.channel_layer.group_send(
                self.group,
                {
                    "type": "room.event",
                    "event": kind,
                    "user": public_user(self.user),
                    "value": content.get("value"),
                },
            )

    async def room_event(self, message):
        payload = {k: v for k, v in message.items() if k != "type"}
        await self.send_json(payload)

    @database_sync_to_async
    def _save_message(self, text):
        from .models import RoomMessage

        return RoomMessage.objects.create(
            room_id=self.room_id, user=self.user, text=text
        )

    @database_sync_to_async
    def _save_caption(self, text, language):
        from .models import Caption

        return Caption.objects.create(
            room_id=self.room_id, user=self.user, text=text, language=language
        )
