import pytest

from apps.social.models import Notification
from tests.factories import FollowFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_followers_notified_when_host_goes_live(auth_client, user):
    fan1 = UserFactory()
    fan2 = UserFactory()
    FollowFactory(follower=fan1, following=user)
    FollowFactory(follower=fan2, following=user)

    response = auth_client.post("/api/v1/rooms/", {"title": "Going live"})
    room_id = response.data["id"]

    notified = set(
        Notification.objects.filter(
            verb=Notification.Verb.WENT_LIVE, room_id=room_id
        ).values_list("user_id", flat=True)
    )
    assert notified == {fan1.id, fan2.id}


def test_non_followers_not_notified(auth_client, user, other_user):
    auth_client.post("/api/v1/rooms/", {"title": "Going live"})
    assert not Notification.objects.filter(user=other_user).exists()


def test_notifications_endpoint_lists_own_only(auth_client, user, other_client, other_user):
    FollowFactory(follower=user, following=other_user)
    other_client.post("/api/v1/rooms/", {"title": "Other goes live"})

    mine = auth_client.get("/api/v1/notifications/")
    assert len(mine.data["results"]) == 1
    assert mine.data["results"][0]["verb"] == "went_live"

    others = other_client.get("/api/v1/notifications/")
    assert others.data["results"] == []
