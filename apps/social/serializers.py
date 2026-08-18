from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer

from .models import Follow, Notification


class FollowerSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(source="follower", read_only=True)

    class Meta:
        model = Follow
        fields = ("user", "created_at")


class FollowingSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(source="following", read_only=True)

    class Meta:
        model = Follow
        fields = ("user", "created_at")


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserPublicSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ("id", "actor", "verb", "room", "is_read", "created_at")
