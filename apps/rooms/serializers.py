from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer

from .models import Room, RoomMessage, RoomParticipant


class RoomMessageSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = RoomMessage
        fields = ("id", "user", "text", "created_at")


class RoomSerializer(serializers.ModelSerializer):
    host = UserPublicSerializer(read_only=True)
    active_participants = serializers.IntegerField(read_only=True)

    class Meta:
        model = Room
        fields = (
            "id",
            "host",
            "title",
            "topic",
            "status",
            "max_seats",
            "started_at",
            "ended_at",
            "listener_count",
            "active_participants",
        )
        read_only_fields = ("status", "started_at", "ended_at", "listener_count")

    def validate_max_seats(self, value):
        if not 2 <= value <= 50:
            raise serializers.ValidationError("max_seats must be between 2 and 50.")
        return value


class RoomParticipantSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = RoomParticipant
        fields = ("user", "role", "joined_at")
