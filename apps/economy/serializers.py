from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer

from .models import Gift, GiftType, GoalPledge, LedgerEntry, Question, Wallet


class GiftTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftType
        fields = ("id", "name", "coins")


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ("id", "delta_coins", "reason", "gift", "created_at")


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("balance_coins",)


class SendGiftSerializer(serializers.Serializer):
    # omit recipient_id to send to the room: split across everyone on stage
    recipient_id = serializers.IntegerField(required=False, allow_null=True)
    gift_type_id = serializers.IntegerField()


class QuestionSerializer(serializers.ModelSerializer):
    asker = UserPublicSerializer(read_only=True)

    class Meta:
        model = Question
        fields = ("id", "asker", "text", "coins", "status", "created_at", "resolved_at")


class AskQuestionSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=280)
    coins = serializers.IntegerField(min_value=1, max_value=1_000_000)


class PledgeSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)

    class Meta:
        model = GoalPledge
        fields = ("id", "user", "coins", "status", "created_at")


class CreatePledgeSerializer(serializers.Serializer):
    coins = serializers.IntegerField(min_value=1, max_value=1_000_000)


class GiftSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)
    recipient = UserPublicSerializer(read_only=True)
    gift_type = GiftTypeSerializer(read_only=True)

    class Meta:
        model = Gift
        fields = (
            "id",
            "sender",
            "recipient",
            "room",
            "gift_type",
            "coins",
            "created_at",
        )


class TopupSerializer(serializers.Serializer):
    coins = serializers.IntegerField(min_value=1, max_value=1_000_000)
