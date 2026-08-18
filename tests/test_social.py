import pytest

from apps.social.models import Follow
from tests.factories import FollowFactory, UserFactory

pytestmark = pytest.mark.django_db


def follow_url(user_id):
    return f"/api/v1/users/{user_id}/follow/"


def test_follow_creates_edge(auth_client, user, other_user):
    response = auth_client.post(follow_url(other_user.id))
    assert response.status_code == 201
    assert Follow.objects.filter(follower=user, following=other_user).exists()


def test_follow_is_idempotent(auth_client, other_user):
    auth_client.post(follow_url(other_user.id))
    response = auth_client.post(follow_url(other_user.id))
    assert response.status_code == 200
    assert Follow.objects.count() == 1


def test_cannot_follow_self(auth_client, user):
    response = auth_client.post(follow_url(user.id))
    assert response.status_code == 400
    assert response.data["code"] == "self_follow"


def test_unfollow(auth_client, user, other_user):
    FollowFactory(follower=user, following=other_user)
    response = auth_client.delete(follow_url(other_user.id))
    assert response.status_code == 204
    assert Follow.objects.count() == 0


def test_followers_and_following_lists(auth_client, user, other_user):
    third = UserFactory()
    FollowFactory(follower=user, following=other_user)
    FollowFactory(follower=third, following=other_user)

    followers = auth_client.get(f"/api/v1/users/{other_user.id}/followers/")
    assert followers.status_code == 200
    names = {row["user"]["display_name"] for row in followers.data["results"]}
    assert names == {user.display_name, third.display_name}

    following = auth_client.get(f"/api/v1/users/{user.id}/following/")
    assert [row["user"]["display_name"] for row in following.data["results"]] == [
        other_user.display_name
    ]


def test_follow_requires_auth(api_client, other_user):
    assert api_client.post(follow_url(other_user.id)).status_code == 401


def test_follow_missing_user_404(auth_client):
    assert auth_client.post(follow_url(999999)).status_code == 404
