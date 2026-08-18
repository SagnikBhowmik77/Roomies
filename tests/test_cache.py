import pytest

from tests.factories import RoomFactory

pytestmark = pytest.mark.django_db

LIVE = "/api/v1/rooms/?status=live"


def test_live_list_is_served_from_cache(auth_client, django_assert_num_queries):
    RoomFactory()
    auth_client.get(LIVE)  # warm
    with django_assert_num_queries(0):
        response = auth_client.get(LIVE)
    assert len(response.data["results"]) == 1


def test_cache_invalidated_when_room_goes_live(auth_client):
    RoomFactory()
    assert len(auth_client.get(LIVE).data["results"]) == 1
    auth_client.post("/api/v1/rooms/", {"title": "New room"})
    assert len(auth_client.get(LIVE).data["results"]) == 2


def test_cache_invalidated_when_room_ends(auth_client, user):
    room = RoomFactory(host=user)
    assert len(auth_client.get(LIVE).data["results"]) == 1
    auth_client.post(f"/api/v1/rooms/{room.id}/end/")
    assert auth_client.get(LIVE).data["results"] == []


def test_ended_history_is_not_cached(auth_client, user):
    """Only the hot live feed is cached; other queries hit the DB."""
    room = RoomFactory(host=user)
    room.end()
    auth_client.get("/api/v1/rooms/?status=ended")
    RoomFactory(host=user).end()
    response = auth_client.get("/api/v1/rooms/?status=ended")
    assert len(response.data["results"]) == 2
