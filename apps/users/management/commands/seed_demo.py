"""Populate a fresh database with believable demo data in one command."""

import random
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.economy import services
from apps.economy.models import GiftType
from apps.economy.services import InsufficientBalanceError
from apps.rooms.models import Room, RoomParticipant
from apps.social.models import Follow
from apps.users.models import User

FIRST_NAMES = [
    "Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana",
    "Vikram", "Zara", "Ishaan", "Priya", "Arjun", "Nisha",
]
TOPICS = ["music", "tech", "gaming", "comedy", "bollywood", "cricket"]
GIFT_CATALOG = [("Rose", 10), ("Clap", 25), ("Rocket", 100), ("Crown", 500)]


class Command(BaseCommand):
    help = "Seed demo users, follows, live rooms, wallets and gifts."

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)

        gift_types = [
            GiftType.objects.get_or_create(name=name, defaults={"coins": coins})[0]
            for name, coins in GIFT_CATALOG
        ]

        users = []
        for i, name in enumerate(FIRST_NAMES):
            user, _ = User.objects.get_or_create(
                phone=f"+9198765000{i:02d}",
                defaults={"display_name": name, "country": "IN"},
            )
            users.append(user)

        for follower in users:
            for following in random.sample(users, 4):
                if follower != following:
                    Follow.objects.get_or_create(
                        follower=follower, following=following
                    )

        for user in users:
            services.topup(
                user=user,
                coins=random.choice([500, 1000, 2000]),
                idempotency_key=f"seed-topup-{user.phone}",
            )

        # only gift in rooms created THIS run, so reseeding an already
        # seeded database is a clean no-op
        new_rooms = []
        for i, host in enumerate(users[:6]):
            room, created = Room.objects.get_or_create(
                host=host,
                title=f"{host.display_name}'s {TOPICS[i]} room",
                defaults={"topic": TOPICS[i], "max_seats": 10},
            )
            if created:
                RoomParticipant.objects.create(
                    room=room, user=host, role=RoomParticipant.Role.HOST
                )
                listeners = [u for u in users if u != host]
                for listener in random.sample(listeners, 4):
                    RoomParticipant.objects.create(room=room, user=listener)
                room.listener_count = 4
                room.save(update_fields=("listener_count",))
                new_rooms.append(room)

        gift_count = 0
        for room in new_rooms:
            senders = room.participants.exclude(user=room.host).select_related("user")
            for participant in senders:
                if random.random() < 0.6:
                    try:
                        services.send_gift(
                            sender=participant.user,
                            recipient=room.host,
                            room=room,
                            gift_type=random.choice(gift_types),
                            idempotency_key=f"seed-{uuid.uuid4()}",
                        )
                    except InsufficientBalanceError:
                        continue  # seeded wallet ran dry; skip, don't abort
                    gift_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users, {Follow.objects.count()} follows, "
                f"{len(new_rooms)} new live rooms, {gift_count} gifts. "
                f"Log in with any seeded phone (e.g. +919876500000) and OTP 123456."
            )
        )
