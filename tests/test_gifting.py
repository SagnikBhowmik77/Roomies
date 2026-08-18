import uuid

import pytest

from apps.economy import services
from apps.economy.models import Gift, LedgerEntry
from tests.factories import GiftTypeFactory, RoomFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def room(db):
    return RoomFactory()


@pytest.fixture
def gift_type(db):
    return GiftTypeFactory(coins=50)


def gift_url(room):
    return f"/api/v1/rooms/{room.id}/gifts/"


def send(client, room, recipient, gift_type, key=None):
    return client.post(
        gift_url(room),
        {"recipient_id": recipient.id, "gift_type_id": gift_type.id},
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def test_gift_moves_coins_and_writes_double_entry(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    response = send(auth_client, room, room.host, gift_type)
    assert response.status_code == 201

    user.wallet.refresh_from_db()
    room.host.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 150
    assert room.host.wallet.balance_coins == 50

    gift = Gift.objects.get()
    entries = list(gift.entries.all())
    assert len(entries) == 2
    assert sum(e.delta_coins for e in entries) == 0


def test_balance_always_derivable_from_ledger(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    send(auth_client, room, room.host, gift_type)
    for wallet in (user.wallet, room.host.wallet):
        wallet.refresh_from_db()
        ledger_sum = sum(wallet.entries.values_list("delta_coins", flat=True))
        assert wallet.balance_coins == ledger_sum


def test_insufficient_balance_rejected(auth_client, user, room, gift_type):
    services.topup(user=user, coins=10)
    response = send(auth_client, room, room.host, gift_type)
    assert response.status_code == 400
    assert response.data["code"] == "insufficient_balance"
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 10
    assert Gift.objects.count() == 0


def test_missing_idempotency_key_rejected(auth_client, user, room, gift_type):
    response = auth_client.post(
        gift_url(room), {"recipient_id": room.host.id, "gift_type_id": gift_type.id}
    )
    assert response.status_code == 400
    assert response.data["code"] == "missing_idempotency_key"


def test_replay_with_same_key_does_not_double_charge(
    auth_client, user, room, gift_type
):
    services.topup(user=user, coins=200)
    key = "retry-after-timeout"
    first = send(auth_client, room, room.host, gift_type, key=key)
    replay = send(auth_client, room, room.host, gift_type, key=key)

    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.data["id"] == first.data["id"]
    assert Gift.objects.count() == 1
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 150  # charged exactly once


def test_self_gift_rejected(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    response = send(auth_client, room, user, gift_type)
    assert response.status_code == 400
    assert response.data["code"] == "self_gift"


def test_gift_in_ended_room_rejected(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    room.end()
    response = send(auth_client, room, room.host, gift_type)
    assert response.status_code == 400
    assert response.data["code"] == "room_not_live"


def test_inactive_gift_type_rejected(auth_client, user, room):
    inactive = GiftTypeFactory(is_active=False)
    services.topup(user=user, coins=200)
    response = send(auth_client, room, room.host, inactive)
    assert response.status_code == 400
    assert response.data["code"] == "gift_type_inactive"


def test_gift_price_is_frozen_at_send_time(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    send(auth_client, room, room.host, gift_type)
    gift_type.coins = 9999
    gift_type.save()
    assert Gift.objects.get().coins == 50


def test_topup_creates_ledger_entry(user):
    wallet = services.topup(user=user, coins=100)
    assert wallet.balance_coins == 100
    entry = LedgerEntry.objects.get()
    assert entry.reason == LedgerEntry.Reason.TOPUP
    assert entry.delta_coins == 100


def test_topup_replay_with_same_key_credits_once(user):
    services.topup(user=user, coins=100, idempotency_key="topup-retry")
    wallet = services.topup(user=user, coins=100, idempotency_key="topup-retry")
    assert wallet.balance_coins == 100  # not 200
    assert LedgerEntry.objects.count() == 1


def test_topup_endpoint(auth_client, user):
    response = auth_client.post("/api/v1/wallet/topup/", {"coins": 500})
    assert response.status_code == 201
    assert response.data["balance_coins"] == 500


def test_wallet_endpoint_shows_balance_and_entries(auth_client, user, room, gift_type):
    services.topup(user=user, coins=200)
    send(auth_client, room, room.host, gift_type)
    response = auth_client.get("/api/v1/wallet/")
    assert response.data["balance_coins"] == 150
    reasons = {e["reason"] for e in response.data["recent_entries"]}
    assert reasons == {"topup", "gift_sent"}


def test_underfunded_burst_only_succeeds_while_funded(
    auth_client, user, room, gift_type
):
    """10 sequential sends from a wallet holding 3 gifts' worth: exactly 3 land."""
    services.topup(user=user, coins=150)
    statuses = [
        send(auth_client, room, room.host, gift_type).status_code for _ in range(10)
    ]
    assert statuses.count(201) == 3
    assert statuses.count(400) == 7
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 0
