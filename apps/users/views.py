import secrets

from django.conf import settings
from django.core.cache import cache
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from config.exceptions import APIError

from .models import User
from .serializers import (
    RequestOTPSerializer,
    UserPublicSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)


class BannedError(APIError):
    status_code = 403
    code = "user_banned"
    message = "This account is banned."


class InvalidOTPError(APIError):
    status_code = 400
    code = "invalid_otp"
    message = "Invalid or expired OTP."


def _otp_cache_key(phone):
    return f"otp:{phone}"


class RequestOTPView(APIView):
    """
    Issue a one-time login code for a phone number.

    In production this would hand off to an SMS gateway. In dev (DEBUG=1)
    the code is the fixed DEV_OTP_CODE and is echoed in the response so the
    flow can be exercised without an SMS provider.
    """

    permission_classes = (permissions.AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "otp"

    @extend_schema(request=RequestOTPSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]

        if settings.OTP_DEV_MODE:
            code = settings.DEV_OTP_CODE
        else:
            code = f"{secrets.randbelow(10**6):06d}"
        cache.set(_otp_cache_key(phone), code, settings.OTP_TTL_SECONDS)

        payload = {"detail": "OTP sent."}
        if settings.OTP_DEV_MODE:
            payload["debug_code"] = code
        return Response(payload, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """Trade a valid OTP for a JWT pair, creating the user on first login."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=VerifyOTPSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["code"]

        expected = cache.get(_otp_cache_key(phone))
        if expected is None or code != expected:
            raise InvalidOTPError()
        cache.delete(_otp_cache_key(phone))

        user, created = User.objects.get_or_create(phone=phone)
        if user.is_banned:
            raise BannedError()

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserPublicSerializer
