"""Time-boxed rooms, live captions, recordings and replay."""

import uuid
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.economy import services
from apps.rooms.models import Caption, Room, RoomMessage, RoomRecording
from apps.rooms.services import expire_due_rooms
from tests.factories import GiftTypeFactory, RoomFactory, UserFactory

pytestmark = pytest.mark.django_db


# --- time-boxed rooms -------------------------------------------------------


def test_creating_a_timeboxed_room_sets_the_clock(auth_client):
    response = auth_client.post(
        "/api/v1/rooms/", {"title": "28 minutes on Rust", "duration_minutes": 28}
    )
    assert response.status_code == 201
    room = Room.objects.get(pk=response.data["id"])
    assert room.duration_minutes == 28
    remaining = (room.ends_at - timezone.now()).total_seconds()
    assert 27 * 60 < remaining <= 28 * 60


def test_rooms_without_a_duration_never_expire(auth_client):
    response = auth_client.post("/api/v1/rooms/", {"title": "Open ended"})
    room = Room.objects.get(pk=response.data["id"])
    assert room.ends_at is None
    assert expire_due_rooms() == 0


def test_expired_room_is_closed_automatically(auth_client):
    room = RoomFactory(duration_minutes=1, ends_at=timezone.now() - timedelta(seconds=1))
    assert expire_due_rooms() == 1
    room.refresh_from_db()
    assert room.status == Room.Status.ENDED
    assert room.ended_at is not None


def test_room_with_time_left_is_untouched(auth_client):
    room = RoomFactory(duration_minutes=30, ends_at=timezone.now() + timedelta(minutes=5))
    assert expire_due_rooms() == 0
    room.refresh_from_db()
    assert room.status == Room.Status.LIVE


def test_expiring_a_room_refunds_escrowed_stakes(auth_client, user):
    """A room running out of time must settle exactly like a manual end."""
    room = RoomFactory(duration_minutes=1)
    services.topup(user=user, coins=200)
    auth_client.post(
        f"/api/v1/rooms/{room.id}/questions/",
        {"text": "Will this refund?", "coins": 60},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 140

    Room.objects.filter(pk=room.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
    expire_due_rooms()

    user.wallet.refresh_from_db()
    assert user.wallet.balance_coins == 200  # stake returned


def test_expired_rooms_drop_out_of_the_live_feed(auth_client):
    room = RoomFactory(duration_minutes=1, ends_at=timezone.now() - timedelta(seconds=1))
    response = auth_client.get("/api/v1/rooms/", {"status": "live"})
    assert room.id not in [r["id"] for r in response.data["results"]]


def test_duration_is_validated(auth_client):
    response = auth_client.post(
        "/api/v1/rooms/", {"title": "Too long", "duration_minutes": 999}
    )
    assert response.status_code == 400


# --- captions ---------------------------------------------------------------


def test_captions_are_persisted_for_the_transcript(auth_client, user):
    room = RoomFactory()
    Caption.objects.create(room=room, user=user, text="hello everyone", language="en-IN")
    response = auth_client.get(f"/api/v1/rooms/{room.id}/replay/")
    captions = [row for row in response.data["timeline"] if row["kind"] == "caption"]
    assert captions[0]["text"] == "hello everyone"
    assert captions[0]["who"] == user.display_name


# --- recordings & replay ----------------------------------------------------


def test_host_can_upload_a_recording(auth_client, user):
    room = RoomFactory(host=user)
    audio = SimpleUploadedFile("room.webm", b"fake-audio-bytes", content_type="audio/webm")
    response = auth_client.post(
        f"/api/v1/rooms/{room.id}/recording/",
        {"audio": audio, "duration": "42"},
        format="multipart",
    )
    assert response.status_code == 201
    recording = RoomRecording.objects.get(room=room)
    assert recording.duration_seconds == 42
    assert response.data["has_recording"] is True


def test_non_host_cannot_upload_a_recording(auth_client):
    room = RoomFactory()
    audio = SimpleUploadedFile("x.webm", b"bytes", content_type="audio/webm")
    response = auth_client.post(
        f"/api/v1/rooms/{room.id}/recording/", {"audio": audio}, format="multipart"
    )
    assert response.status_code == 403


def test_upload_without_a_file_is_rejected(auth_client, user):
    room = RoomFactory(host=user)
    response = auth_client.post(
        f"/api/v1/rooms/{room.id}/recording/", {}, format="multipart"
    )
    assert response.status_code == 400
    assert response.data["code"] == "missing_audio"


def test_replay_merges_every_kind_of_event_in_order(auth_client, user):
    room = RoomFactory(host=user)
    asker = UserFactory()
    services.topup(user=asker, coins=300)
    gift_type = GiftTypeFactory(coins=25)

    RoomMessage.objects.create(room=room, user=user, text="welcome in")
    Caption.objects.create(room=room, user=user, text="lets get started")
    services.send_gift(
        sender=asker, recipient=user, room=room, gift_type=gift_type,
        idempotency_key="replay-gift",
    )
    services.ask_question(
        asker=asker, room=room, text="whats next?", coins=40,
        idempotency_key="replay-q",
    )

    response = auth_client.get(f"/api/v1/rooms/{room.id}/replay/")
    assert response.status_code == 200
    kinds = {row["kind"] for row in response.data["timeline"]}
    assert kinds == {"chat", "caption", "gift", "question"}
    offsets = [row["at"] for row in response.data["timeline"]]
    assert offsets == sorted(offsets)
    assert response.data["audio_url"] is None  # nothing uploaded yet


def test_replay_exposes_the_audio_once_uploaded(auth_client, user):
    room = RoomFactory(host=user)
    auth_client.post(
        f"/api/v1/rooms/{room.id}/recording/",
        {
            "audio": SimpleUploadedFile("r.webm", b"bytes", content_type="audio/webm"),
            "duration": "12",
        },
        format="multipart",
    )
    response = auth_client.get(f"/api/v1/rooms/{room.id}/replay/")
    assert response.data["audio_url"].endswith(".webm")
    assert response.data["duration_seconds"] == 12


def test_room_gift_to_the_stage_renders_in_replay(auth_client, user):
    """Regression: a null recipient must not break anything downstream."""
    room = RoomFactory(host=user)
    sender = UserFactory()
    services.topup(user=sender, coins=200)
    services.send_gift(
        sender=sender, room=room, gift_type=GiftTypeFactory(coins=30),
        idempotency_key="stage-gift",
    )
    response = auth_client.get(f"/api/v1/rooms/{room.id}/replay/")
    gift_rows = [r for r in response.data["timeline"] if r["kind"] == "gift"]
    assert "the stage" in gift_rows[0]["text"]
