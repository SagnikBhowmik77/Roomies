import factory
from factory.django import DjangoModelFactory

from apps.economy.models import GiftType
from apps.rooms.models import Room, RoomParticipant
from apps.social.models import Follow
from apps.users.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    phone = factory.Sequence(lambda n: f"+9198{n:08d}")
    display_name = factory.Sequence(lambda n: f"user{n}")
    country = "IN"


class RoomFactory(DjangoModelFactory):
    class Meta:
        model = Room
        skip_postgeneration_save = True

    host = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Room {n}")
    topic = "music"
    max_seats = 8

    @factory.post_generation
    def seat_host(obj, create, extracted, **kwargs):
        if create:
            RoomParticipant.objects.create(
                room=obj, user=obj.host, role=RoomParticipant.Role.HOST
            )


class GiftTypeFactory(DjangoModelFactory):
    class Meta:
        model = GiftType

    name = factory.Sequence(lambda n: f"gift{n}")
    coins = 50


class FollowFactory(DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory(UserFactory)
    following = factory.SubFactory(UserFactory)
