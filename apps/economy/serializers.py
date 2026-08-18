from rest_framework import serializers

from apps.users.serializers import UserPublicSerializer

from .models import Gift, GiftType, LedgerEntry, Wallet


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
    recipient_id = serializers.IntegerField()
    gift_type_id = serializers.IntegerField()


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
