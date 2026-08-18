"""Websocket layer: auth, chat persistence, targeted signaling, roles."""

import pytest
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from apps.rooms.models import RoomMessage, RoomParticipant
from config.asgi import application
from tests.factories import RoomFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


def ws_path(room, user):
    token = str(AccessToken.for_user(user))
    return f"/ws/rooms/{room.id}/?token={token}"


async def connect(room, user):
    communicator = WebsocketCommunicator(application, ws_path(room, user))
    connected, _ = await communicator.connect()
    assert connected
    # swallow own peer_joined broadcast
    joined = await communicator.receive_json_from()
    assert joined["event"] == "peer_joined"
    return communicator


@pytest.mark.asyncio
async def test_anonymous_connection_rejected():
    from asgiref.sync import sync_to_async

    room = await sync_to_async(RoomFactory)()
    communicator = WebsocketCommunicator(application, f"/ws/rooms/{room.id}/")
    connected, _ = await communicator.connect()
    assert not connected


@pytest.mark.asyncio
async def test_chat_is_broadcast_and_persisted():
    from asgiref.sync import sync_to_async

    room = await sync_to_async(RoomFactory)()
    alice = await sync_to_async(UserFactory)(display_name="Alice")
    bob = await sync_to_async(UserFactory)(display_name="Bob")

    a = await connect(room, alice)
    b = await connect(room, bob)
    await a.receive_json_from()  # bob's join, seen by alice

    await a.send_json_to({"type": "chat", "text": "hello room"})
    seen_by_bob = await b.receive_json_from()
    assert seen_by_bob["event"] == "chat"
    assert seen_by_bob["text"] == "hello room"
    assert seen_by_bob["user"]["display_name"] == "Alice"

    count = await sync_to_async(RoomMessage.objects.filter(room=room).count)()
    assert count == 1

    await a.disconnect()
    await b.disconnect()


@pytest.mark.asyncio
async def test_signal_is_relayed_only_to_target():
    from asgiref.sync import sync_to_async

    room = await sync_to_async(RoomFactory)()
    alice = await sync_to_async(UserFactory)()
    bob = await sync_to_async(UserFactory)()
    carol = await sync_to_async(UserFactory)()

    a = await connect(room, alice)
    b = await connect(room, bob)
    c = await connect(room, carol)
    # drain join broadcasts
    await a.receive_json_from()
    await a.receive_json_from()
    await b.receive_json_from()

    await a.send_json_to(
        {"type": "signal", "target": bob.id, "data": {"sdp": "offer-blob"}}
    )
    relayed = await b.receive_json_from()
    assert relayed["event"] == "signal"
    assert relayed["from"] == alice.id
    assert relayed["data"] == {"sdp": "offer-blob"}
    assert await c.receive_nothing()

    for comm in (a, b, c):
        await comm.disconnect()


def test_chat_history_endpoint(auth_client, user):
    room = RoomFactory()
    for i in range(3):
        RoomMessage.objects.create(room=room, user=user, text=f"msg {i}")
    response = auth_client.get(f"/api/v1/rooms/{room.id}/messages/")
    assert response.status_code == 200
    assert [m["text"] for m in response.data] == ["msg 0", "msg 1", "msg 2"]


def test_host_can_promote_and_demote(auth_client, user, other_user):
    room = RoomFactory(host=user)
    RoomParticipant.objects.create(room=room, user=other_user)
    url = f"/api/v1/rooms/{room.id}/participants/{other_user.id}/role/"

    response = auth_client.post(url, {"role": "speaker"})
    assert response.status_code == 200
    assert response.data["role"] == "speaker"

    response = auth_client.post(url, {"role": "listener"})
    assert response.data["role"] == "listener"


def test_non_host_cannot_change_roles(other_client, user, other_user):
    room = RoomFactory(host=user)
    RoomParticipant.objects.create(room=room, user=other_user)
    url = f"/api/v1/rooms/{room.id}/participants/{other_user.id}/role/"
    # blocked by IsHostOrReadOnly (object permission) before the view runs
    response = other_client.post(url, {"role": "speaker"})
    assert response.status_code == 403


def test_host_role_cannot_be_changed(auth_client, user):
    room = RoomFactory(host=user)
    url = f"/api/v1/rooms/{room.id}/participants/{user.id}/role/"
    response = auth_client.post(url, {"role": "listener"})
    assert response.status_code == 400
