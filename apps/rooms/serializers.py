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
    goal_reached = serializers.SerializerMethodField()

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
            "goal_coins",
            "goal_title",
            "pledged_coins",
            "goal_reached_at",
            "goal_reached",
        )
        read_only_fields = (
            "status",
            "started_at",
            "ended_at",
            "listener_count",
            "pledged_coins",
            "goal_reached_at",
        )

    def get_goal_reached(self, obj) -> bool:
        return obj.goal_reached_at is not None

    def validate_max_seats(self, value):
        if not 2 <= value <= 50:
            raise serializers.ValidationError("max_seats must be between 2 and 50.")
        return value


class RoomParticipantSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)
    stage_seconds = serializers.SerializerMethodField()

    class Meta:
        model = RoomParticipant
        fields = ("user", "role", "joined_at", "speaker_since", "stage_seconds")

    def get_stage_seconds(self, obj) -> int:
        return int(obj.stage_seconds())
