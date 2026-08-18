from rest_framework import serializers

from .models import User, phone_validator


class RequestOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=16, validators=[phone_validator])


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=16, validators=[phone_validator])
    code = serializers.CharField(max_length=6)


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "display_name", "avatar_url", "country", "created_at")


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "phone",
            "display_name",
            "avatar_url",
            "country",
            "created_at",
        )
        read_only_fields = ("id", "phone", "created_at")
