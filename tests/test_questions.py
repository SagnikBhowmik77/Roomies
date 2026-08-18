"""
Paid question queue: coins are escrowed on ask and leave escrow exactly
once — to the host on answer, or back to the asker on decline / room end.
"""

import uuid

import pytest

from apps.economy import services
from apps.economy.models import LedgerEntry, Question, Wallet
from tests.factories import RoomFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def room(db):
    return RoomFactory()


def ask(client, room, coins=50, text="How did you get started?", key=None):
    return client.post(
        f"/api/v1/rooms/{room.id}/questions/",
        {"text": text, "coins": coins},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def escrow_balance():
    return Wallet.escrow().balance_coins


def test_asking_escrows_the_stake(auth_client, user, room):
    services.topup(user=user, coins=200)
    response = ask(auth_client, room, coins=50)

    assert response.status_code == 201
    assert response.data["status"] == "pending"

    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 150
    # the coins are not gone — they are sitting in escrow
    assert escrow_balance() == 50
    room.host.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins == 0


def test_answering_releases_escrow_to_host(auth_client, other_client, user, room):
    services.topup(user=user, coins=200)
    question_id = ask(auth_client, room, coins=50).data["id"]

    # the host answers
    host_client = other_client
    host_client.force_authenticate(room.host)
    response = host_client.post(
        f"/api/v1/rooms/{room.id}/questions/{question_id}/answer/"
    )

    assert response.status_code == 200
    assert response.data["status"] == "answered"
    room.host.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins == 50
    assert escrow_balance() == 0


def test_declining_refunds_the_asker(auth_client, other_client, user, room):
    services.topup(user=user, coins=200)
    question_id = ask(auth_client, room, coins=50).data["id"]

    other_client.force_authenticate(room.host)
    response = other_client.post(
        f"/api/v1/rooms/{room.id}/questions/{question_id}/decline/"
    )

    assert response.status_code == 200
    assert response.data["status"] == "refunded"
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 200  # whole stake returned
    assert escrow_balance() == 0
    room.host.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins == 0


def test_ending_the_room_refunds_every_pending_question(
    auth_client, other_client, user, room
):
    services.topup(user=user, coins=300)
    ask(auth_client, room, coins=50)
    ask(auth_client, room, coins=70)

    other_client.force_authenticate(room.host)
    response = other_client.post(f"/api/v1/rooms/{room.id}/end/")

    assert response.data["refunded_questions"] == 2
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 300
    assert escrow_balance() == 0
    assert Question.objects.filter(status="refunded").count() == 2


def test_queue_is_ordered_by_stake(auth_client, user, room):
    services.topup(user=user, coins=500)
    ask(auth_client, room, coins=10, text="cheap")
    ask(auth_client, room, coins=200, text="expensive")
    ask(auth_client, room, coins=50, text="middle")

    response = auth_client.get(f"/api/v1/rooms/{room.id}/questions/")
    assert [q["text"] for q in response.data] == ["expensive", "middle", "cheap"]


def test_cannot_ask_without_enough_coins(auth_client, user, room):
    services.topup(user=user, coins=10)
    response = ask(auth_client, room, coins=500)
    assert response.status_code == 400
    assert response.data["code"] == "insufficient_balance"
    assert Question.objects.count() == 0
    assert escrow_balance() == 0


def test_replayed_key_does_not_double_escrow(auth_client, user, room):
    services.topup(user=user, coins=200)
    key = "same-question"
    first = ask(auth_client, room, coins=50, key=key)
    replay = ask(auth_client, room, coins=50, key=key)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.data["id"] == first.data["id"]
    assert Question.objects.count() == 1
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 150


def test_non_host_cannot_answer(auth_client, other_client, user, room):
    services.topup(user=user, coins=200)
    question_id = ask(auth_client, room, coins=50).data["id"]
    response = other_client.post(
        f"/api/v1/rooms/{room.id}/questions/{question_id}/answer/"
    )
    assert response.status_code == 403
    assert escrow_balance() == 50  # still held


def test_asker_can_withdraw_their_own_question(auth_client, user, room):
    services.topup(user=user, coins=200)
    question_id = ask(auth_client, room, coins=50).data["id"]
    response = auth_client.post(
        f"/api/v1/rooms/{room.id}/questions/{question_id}/decline/"
    )
    assert response.status_code == 200
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 200


def test_question_cannot_be_resolved_twice(auth_client, other_client, user, room):
    services.topup(user=user, coins=200)
    question_id = ask(auth_client, room, coins=50).data["id"]
    other_client.force_authenticate(room.host)
    url = f"/api/v1/rooms/{room.id}/questions/{question_id}/answer/"
    assert other_client.post(url).status_code == 200

    response = other_client.post(url)
    assert response.status_code == 400
    assert response.data["code"] == "question_not_pending"
    room.host.wallet.refresh_from_db()
    assert room.host.wallet.balance_coins == 50  # paid once, not twice


def test_host_cannot_pay_to_ask_themselves(other_client, room):
    services.topup(user=room.host, coins=200)
    other_client.force_authenticate(room.host)
    response = ask(other_client, room, coins=50)
    assert response.status_code == 400
    assert response.data["code"] == "self_question"


def test_ledger_stays_balanced_through_the_whole_lifecycle(
    auth_client, other_client, user, room
):
    """The global invariant: coins are only ever created by top-ups."""
    services.topup(user=user, coins=300)
    q1 = ask(auth_client, room, coins=50).data["id"]
    ask(auth_client, room, coins=70)
    other_client.force_authenticate(room.host)
    other_client.post(f"/api/v1/rooms/{room.id}/questions/{q1}/answer/")
    other_client.post(f"/api/v1/rooms/{room.id}/end/")

    total = sum(LedgerEntry.objects.values_list("delta_coins", flat=True))
    assert total == 300
    user.wallet.refresh_from_db()
    room.host.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 250  # 300 - 50 answered
    assert room.host.wallet.balance_coins == 50
    assert escrow_balance() == 0
