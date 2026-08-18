"""Revenue splits for co-hosts, goal rooms, and portable host stats."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.economy import services
from apps.economy.models import GoalPledge, LedgerEntry, Wallet
from apps.economy.services import split_shares
from apps.rooms.models import Room, RoomParticipant
from tests.factories import GiftTypeFactory, RoomFactory, UserFactory

pytestmark = pytest.mark.django_db


def escrow_balance():
    return Wallet.escrow().balance_coins


# --- split maths ------------------------------------------------------------


@pytest.mark.parametrize(
    "total,weights",
    [(100, [1, 1, 1]), (7, [5, 3]), (1, [1, 1]), (999, [10, 3, 3, 1]), (50, [0, 0])],
)
def test_split_shares_never_creates_or_destroys_coins(total, weights):
    shares = split_shares(total, weights)
    assert sum(shares) == total
    assert all(s >= 0 for s in shares)


def test_split_shares_is_proportional():
    assert split_shares(100, [3, 1]) == [75, 25]


# --- room gifts split across the stage --------------------------------------


@pytest.fixture
def room_with_cohost(db):
    """Host + co-host, both on stage for exactly the same duration."""
    room = RoomFactory()
    cohost = UserFactory(display_name="Cohost")
    on_stage_since = timezone.now() - timedelta(minutes=10)
    RoomParticipant.objects.create(
        room=room,
        user=cohost,
        role=RoomParticipant.Role.SPEAKER,
        speaker_since=on_stage_since,
    )
    # pin the host's clock too: the factory seats them a moment earlier, and
    # splits are proportional to real time on stage
    room.participants.filter(user=room.host).update(speaker_since=on_stage_since)
    return room, cohost


def test_room_gift_splits_across_everyone_on_stage(auth_client, user, room_with_cohost):
    room, cohost = room_with_cohost
    services.topup(user=user, coins=500)
    gift_type = GiftTypeFactory(coins=100)

    # equal stage time -> equal split
    response = auth_client.post(
        f"/api/v1/rooms/{room.id}/gifts/",
        {"gift_type_id": gift_type.id},  # no recipient_id = gift to the room
        headers={"Idempotency-Key": "split-1"},
    )
    assert response.status_code == 201

    room.host.wallet.refresh_from_db()
    cohost.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins + cohost.wallet.balance_coins == 100
    assert room.host.wallet.balance_coins == 50
    assert cohost.wallet.balance_coins == 50


def test_split_is_weighted_by_stage_time(auth_client, user, room_with_cohost):
    room, cohost = room_with_cohost
    # host has been on stage 3x longer than the co-host
    host_seat = room.participants.get(user=room.host)
    host_seat.speaker_since = timezone.now() - timedelta(minutes=30)
    host_seat.save(update_fields=("speaker_since",))
    cohost_seat = room.participants.get(user=cohost)
    cohost_seat.speaker_since = timezone.now() - timedelta(minutes=10)
    cohost_seat.save(update_fields=("speaker_since",))

    services.topup(user=user, coins=500)
    gift_type = GiftTypeFactory(coins=100)
    auth_client.post(
        f"/api/v1/rooms/{room.id}/gifts/",
        {"gift_type_id": gift_type.id},
        headers={"Idempotency-Key": "split-weighted"},
    )

    room.host.wallet.refresh_from_db()
    cohost.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins == 75
    assert cohost.wallet.balance_coins == 25


def test_listeners_are_not_paid(auth_client, user, room_with_cohost):
    room, cohost = room_with_cohost
    listener = UserFactory()
    RoomParticipant.objects.create(room=room, user=listener)  # role=listener
    services.topup(user=user, coins=500)
    gift_type = GiftTypeFactory(coins=100)
    auth_client.post(
        f"/api/v1/rooms/{room.id}/gifts/",
        {"gift_type_id": gift_type.id},
        headers={"Idempotency-Key": "split-listener"},
    )
    listener.wallet.refresh_from_db()
    assert listener.wallet.balance_coins == 0


def test_direct_gifts_still_go_to_one_person(auth_client, user, room_with_cohost):
    room, cohost = room_with_cohost
    services.topup(user=user, coins=500)
    gift_type = GiftTypeFactory(coins=100)
    auth_client.post(
        f"/api/v1/rooms/{room.id}/gifts/",
        {"gift_type_id": gift_type.id, "recipient_id": cohost.id},
        headers={"Idempotency-Key": "direct-1"},
    )
    cohost.wallet.refresh_from_db()
    room.host.wallet.refresh_from_db()
    assert cohost.wallet.balance_coins == 100
    assert room.host.wallet.balance_coins == 0


# --- goal rooms -------------------------------------------------------------


@pytest.fixture
def goal_room(db):
    return RoomFactory(goal_coins=100, goal_title="Full acoustic set")


def pledge(client, room, coins, key=None):
    return client.post(
        f"/api/v1/rooms/{room.id}/pledges/",
        {"coins": coins},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def test_pledges_are_escrowed_until_the_goal_is_hit(auth_client, user, goal_room):
    services.topup(user=user, coins=200)
    response = pledge(auth_client, goal_room, 40)

    assert response.status_code == 201
    assert response.data["status"] == "escrowed"
    goal_room.refresh_from_db()
    assert goal_room.pledged_coins == 40
    assert goal_room.goal_reached_at is None
    assert escrow_balance() == 40
    goal_room.host.wallet.refresh_from_db()
    assert goal_room.host.wallet.balance_coins == 0  # host paid nothing yet


def test_reaching_the_goal_settles_every_pledge(auth_client, other_client, user, goal_room):
    backer = UserFactory()
    services.topup(user=user, coins=200)
    services.topup(user=backer, coins=200)
    other_client.force_authenticate(backer)

    pledge(auth_client, goal_room, 60)
    pledge(other_client, goal_room, 40)  # crosses the 100 goal

    goal_room.refresh_from_db()
    assert goal_room.goal_reached_at is not None
    goal_room.host.wallet.refresh_from_db()
    assert goal_room.host.wallet.balance_coins == 100
    assert escrow_balance() == 0
    assert GoalPledge.objects.filter(status="settled").count() == 2


def test_ending_short_of_the_goal_refunds_everyone(
    auth_client, other_client, user, goal_room
):
    services.topup(user=user, coins=200)
    pledge(auth_client, goal_room, 60)

    other_client.force_authenticate(goal_room.host)
    response = other_client.post(f"/api/v1/rooms/{goal_room.id}/end/")

    assert response.data["refunded_pledges"] == 1
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 200  # fully refunded
    goal_room.host.wallet.refresh_from_db()
    assert goal_room.host.wallet.balance_coins == 0
    assert escrow_balance() == 0


def test_settled_pledges_are_not_refunded_when_the_room_ends(
    auth_client, other_client, user, goal_room
):
    services.topup(user=user, coins=200)
    pledge(auth_client, goal_room, 100)  # hits the goal immediately

    other_client.force_authenticate(goal_room.host)
    response = other_client.post(f"/api/v1/rooms/{goal_room.id}/end/")

    assert response.data["refunded_pledges"] == 0
    goal_room.host.wallet.refresh_from_db()
    assert goal_room.host.wallet.balance_coins == 100
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 100


def test_cannot_pledge_to_a_room_without_a_goal(auth_client, user):
    plain_room = RoomFactory()
    services.topup(user=user, coins=200)
    response = pledge(auth_client, plain_room, 50)
    assert response.status_code == 400
    assert response.data["code"] == "no_goal"


def test_goal_room_ledger_stays_balanced(auth_client, other_client, user, goal_room):
    services.topup(user=user, coins=200)
    pledge(auth_client, goal_room, 60)
    other_client.force_authenticate(goal_room.host)
    other_client.post(f"/api/v1/rooms/{goal_room.id}/end/")
    assert sum(LedgerEntry.objects.values_list("delta_coins", flat=True)) == 200


def test_room_create_accepts_a_goal(auth_client):
    response = auth_client.post(
        "/api/v1/rooms/",
        {"title": "Charity stream", "goal_coins": 500, "goal_title": "For the shelter"},
    )
    assert response.status_code == 201
    room = Room.objects.get(pk=response.data["id"])
    assert room.goal_coins == 500
    assert response.data["goal_reached"] is False


# --- portable host reputation ------------------------------------------------


def test_host_stats_are_derived_from_real_activity(auth_client, other_client, user):
    host = UserFactory(display_name="Star Host")
    room = RoomFactory(host=host)
    services.topup(user=user, coins=500)
    gift_type = GiftTypeFactory(coins=100)

    auth_client.post(
        f"/api/v1/rooms/{room.id}/gifts/",
        {"gift_type_id": gift_type.id, "recipient_id": host.id},
        headers={"Idempotency-Key": "stats-gift"},
    )
    question_id = auth_client.post(
        f"/api/v1/rooms/{room.id}/questions/",
        {"text": "Whats your setup?", "coins": 50},
        headers={"Idempotency-Key": "stats-q"},
    ).data["id"]
    other_client.force_authenticate(host)
    other_client.post(f"/api/v1/rooms/{room.id}/questions/{question_id}/answer/")

    response = auth_client.get(f"/api/v1/users/{host.id}/stats/")
    assert response.status_code == 200
    assert response.data["rooms_hosted"] == 1
    assert response.data["live_now"] is True
    assert response.data["coins_earned"] == 150  # gift + answered question
    assert response.data["questions_answered"] == 1
    assert response.data["top_supporters"][0]["display_name"] == user.display_name
    assert response.data["top_supporters"][0]["coins"] == 100


def test_stats_are_public_for_any_user(auth_client):
    stranger = UserFactory()
    response = auth_client.get(f"/api/v1/users/{stranger.id}/stats/")
    assert response.status_code == 200
    assert response.data["rooms_hosted"] == 0
    assert response.data["coins_earned"] == 0
