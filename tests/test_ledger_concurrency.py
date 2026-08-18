"""
The Day-3 guarantee: money cannot be created or destroyed under concurrent
load. These tests need real row locking (select_for_update), which SQLite
does not implement, so they run only against Postgres — which is exactly
what CI uses. Locally: docker compose up db, set POSTGRES_HOST, run pytest.
"""

import threading

import pytest
from django.db import connection, connections

from apps.economy import services
from apps.economy.models import LedgerEntry
from apps.economy.services import InsufficientBalanceError
from tests.factories import GiftTypeFactory, RoomFactory, UserFactory

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="select_for_update is a no-op on SQLite; run against Postgres (CI does)",
)

pytestmark = [pytest.mark.django_db(transaction=True), requires_postgres]


def test_concurrent_gifts_from_underfunded_wallet_never_overspend():
    sender = UserFactory()
    room = RoomFactory()
    gift_type = GiftTypeFactory(coins=50)
    services.topup(user=sender, coins=150)  # room for exactly 3 gifts

    results = []
    barrier = threading.Barrier(10)

    def fire(i):
        try:
            barrier.wait()
            services.send_gift(
                sender=sender,
                recipient=room.host,
                room=room,
                gift_type=gift_type,
                idempotency_key=f"concurrent-{i}",
            )
            results.append("ok")
        except InsufficientBalanceError:
            results.append("insufficient")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=fire, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 3
    assert results.count("insufficient") == 7

    sender.wallet.refresh_from_db()
    room.host.wallet.refresh_from_db()
    assert sender.wallet.balance_coins == 0
    assert room.host.wallet.balance_coins == 150
    # global invariant: the coin supply equals topups; gifts net to zero
    assert (
        sum(LedgerEntry.objects.values_list("delta_coins", flat=True)) == 150
    )


def test_concurrent_identical_requests_charge_once():
    """Same Idempotency-Key raced from 5 threads -> exactly one gift."""
    sender = UserFactory()
    room = RoomFactory()
    gift_type = GiftTypeFactory(coins=50)
    services.topup(user=sender, coins=500)

    barrier = threading.Barrier(5)
    gifts = []

    def fire():
        try:
            barrier.wait()
            gift, _ = services.send_gift(
                sender=sender,
                recipient=room.host,
                room=room,
                gift_type=gift_type,
                idempotency_key="same-key-raced",
            )
            gifts.append(gift.id)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=fire) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(gifts)) == 1
    sender.wallet.refresh_from_db()
    assert sender.wallet.balance_coins == 450  # charged exactly once
