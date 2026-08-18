import pytest

from apps.rooms.models import Room, RoomParticipant
from tests.factories import RoomFactory, UserFactory

pytestmark = pytest.mark.django_db

ROOMS = "/api/v1/rooms/"


def test_create_room_seats_host(auth_client, user):
    response = auth_client.post(ROOMS, {"title": "Late night lofi", "topic": "music"})
    assert response.status_code == 201
    room = Room.objects.get(pk=response.data["id"])
    assert room.host == user
    assert room.participants.get().role == RoomParticipant.Role.HOST


def test_room_list_filters_by_status(auth_client):
    live = RoomFactory()
    ended = RoomFactory()
    ended.end()
    response = auth_client.get(ROOMS, {"status": "live"})
    ids = [row["id"] for row in response.data["results"]]
    assert live.id in ids and ended.id not in ids


def test_room_list_filters_by_topic_and_country(auth_client):
    music = RoomFactory(topic="music", host__country="IN")
    RoomFactory(topic="tech", host__country="US")
    response = auth_client.get(ROOMS, {"topic": "music", "country": "IN"})
    assert [row["id"] for row in response.data["results"]] == [music.id]


def test_join_room(auth_client, user):
    room = RoomFactory()
    response = auth_client.post(f"{ROOMS}{room.id}/join/")
    assert response.status_code == 201
    assert room.participants.filter(user=user, left_at__isnull=True).exists()


def test_join_full_room_conflicts(auth_client):
    room = RoomFactory(max_seats=2)  # host + 1
    other = UserFactory()
    RoomParticipant.objects.create(room=room, user=other)
    response = auth_client.post(f"{ROOMS}{room.id}/join/")
    assert response.status_code == 409
    assert response.data["code"] == "room_full"


def test_rejoin_is_idempotent(auth_client):
    room = RoomFactory()
    assert auth_client.post(f"{ROOMS}{room.id}/join/").status_code == 201
    response = auth_client.post(f"{ROOMS}{room.id}/join/")
    assert response.status_code == 200
    assert room.participants.filter(left_at__isnull=True).count() == 2  # host + user


def test_join_ended_room_rejected(auth_client):
    room = RoomFactory()
    room.end()
    response = auth_client.post(f"{ROOMS}{room.id}/join/")
    assert response.status_code == 400
    assert response.data["code"] == "room_not_live"


def test_leave_room(auth_client, user):
    room = RoomFactory()
    auth_client.post(f"{ROOMS}{room.id}/join/")
    response = auth_client.post(f"{ROOMS}{room.id}/leave/")
    assert response.status_code == 204
    assert not room.participants.filter(user=user, left_at__isnull=True).exists()


def test_user_can_leave_and_rejoin(auth_client, user):
    room = RoomFactory()
    auth_client.post(f"{ROOMS}{room.id}/join/")
    auth_client.post(f"{ROOMS}{room.id}/leave/")
    assert auth_client.post(f"{ROOMS}{room.id}/join/").status_code == 201
    assert room.participants.filter(user=user).count() == 2  # history kept


def test_host_can_end_room(auth_client, user):
    room = RoomFactory(host=user)
    response = auth_client.post(f"{ROOMS}{room.id}/end/")
    assert response.status_code == 200
    room.refresh_from_db()
    assert room.status == Room.Status.ENDED
    assert room.ended_at is not None
    assert not room.participants.filter(left_at__isnull=True).exists()


def test_non_host_cannot_end_room(auth_client):
    room = RoomFactory()
    response = auth_client.post(f"{ROOMS}{room.id}/end/")
    assert response.status_code == 403


def test_end_twice_rejected(auth_client, user):
    room = RoomFactory(host=user)
    auth_client.post(f"{ROOMS}{room.id}/end/")
    response = auth_client.post(f"{ROOMS}{room.id}/end/")
    assert response.status_code == 400


def test_participants_endpoint(auth_client, user):
    room = RoomFactory()
    auth_client.post(f"{ROOMS}{room.id}/join/")
    response = auth_client.get(f"{ROOMS}{room.id}/participants/")
    roles = {row["user"]["display_name"]: row["role"] for row in response.data}
    assert roles[room.host.display_name] == "host"
    assert roles[user.display_name] == "listener"


def test_cursor_pagination(auth_client):
    for _ in range(25):
        RoomFactory()
    page1 = auth_client.get(ROOMS)
    assert len(page1.data["results"]) == 20
    assert page1.data["next"] is not None
    page2 = auth_client.get(page1.data["next"])
    assert len(page2.data["results"]) == 5
    assert {r["id"] for r in page1.data["results"]}.isdisjoint(
        {r["id"] for r in page2.data["results"]}
    )


def test_room_list_query_count_is_constant(auth_client, django_assert_num_queries):
    """The feed must not do per-room queries (no N+1)."""
    for _ in range(15):
        RoomFactory()
    with django_assert_num_queries(1):
        auth_client.get(ROOMS)
