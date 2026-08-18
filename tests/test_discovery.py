"""Discovery features: suggested follows, leaderboard, room search."""

import pytest

from apps.economy import services
from apps.economy.models import Gift
from tests.factories import (
    FollowFactory,
    GiftTypeFactory,
    RoomFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_suggested_excludes_self_and_already_followed(auth_client, user, other_user):
    popular = UserFactory(display_name="Popular")
    for _ in range(3):
        FollowFactory(following=popular)
    FollowFactory(follower=user, following=other_user)  # already followed

    response = auth_client.get("/api/v1/users/suggested/")
    assert response.status_code == 200
    ids = [row["id"] for row in response.data]
    assert popular.id in ids
    assert user.id not in ids
    assert other_user.id not in ids
    assert response.data[0]["id"] == popular.id  # most-followed first
    assert response.data[0]["follower_count"] == 3


def test_leaderboard_ranks_by_coins_received(auth_client, user):
    room = RoomFactory()
    rose = GiftTypeFactory(coins=10)
    crown = GiftTypeFactory(coins=500)
    small_host = UserFactory(display_name="Small")
    big_host = UserFactory(display_name="Big")
    services.topup(user=user, coins=2000)
    for gift_type, recipient, key in (
        (crown, big_host, "lb-1"),
        (rose, small_host, "lb-2"),
    ):
        services.send_gift(
            sender=user,
            recipient=recipient,
            room=room,
            gift_type=gift_type,
            idempotency_key=key,
        )

    response = auth_client.get("/api/v1/leaderboard/")
    assert response.status_code == 200
    assert response.data[0]["display_name"] == "Big"
    assert response.data[0]["coins_received"] == 500
    assert response.data[1]["display_name"] == "Small"
    assert Gift.objects.count() == 2


def test_room_search_matches_title(auth_client):
    lofi = RoomFactory(title="Late night lofi beats")
    RoomFactory(title="Morning cricket talk")
    response = auth_client.get("/api/v1/rooms/", {"search": "lofi"})
    assert [r["id"] for r in response.data["results"]] == [lofi.id]


def test_room_search_is_case_insensitive(auth_client):
    room = RoomFactory(title="Bollywood Bangers")
    response = auth_client.get("/api/v1/rooms/", {"search": "bolly"})
    assert [r["id"] for r in response.data["results"]] == [room.id]
