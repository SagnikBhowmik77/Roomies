from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.rooms.models import Room
from apps.users.models import User
from config.exceptions import APIError

from . import services
from .models import Gift, GiftType, LedgerEntry, Wallet
from .serializers import (
    GiftSerializer,
    GiftTypeSerializer,
    LedgerEntrySerializer,
    SendGiftSerializer,
    TopupSerializer,
    WalletSerializer,
)


class MissingIdempotencyKeyError(APIError):
    code = "missing_idempotency_key"
    message = "The Idempotency-Key header is required."


class RoomNotLiveError(APIError):
    code = "room_not_live"
    message = "Gifts can only be sent in live rooms."


class SelfGiftError(APIError):
    code = "self_gift"
    message = "You cannot send a gift to yourself."


class WalletView(APIView):
    """Current balance plus the most recent ledger entries."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        # fresh query, not request.user.wallet: the reverse one-to-one cache
        # on the user instance can hold a stale balance
        wallet = Wallet.objects.get(user=request.user)
        entries = wallet.entries.order_by("-created_at")[:20]
        return Response(
            {
                **WalletSerializer(wallet).data,
                "recent_entries": LedgerEntrySerializer(entries, many=True).data,
            }
        )


class TopupView(APIView):
    """
    Dev/demo stand-in for a payment-gateway webhook. In production this
    endpoint would not exist; the gateway's signed callback would call
    services.topup instead.
    """

    @extend_schema(request=TopupSerializer, responses={201: WalletSerializer})
    def post(self, request):
        serializer = TopupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = services.topup(
            user=request.user,
            coins=serializer.validated_data["coins"],
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)


class GiftTypeListView(generics.ListAPIView):
    queryset = GiftType.objects.filter(is_active=True).order_by("coins")
    serializer_class = GiftTypeSerializer
    pagination_class = None


class SendGiftView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "gifts"

    @extend_schema(
        request=SendGiftSerializer,
        responses={201: GiftSerializer},
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
                description="Client-generated key making retries safe.",
            )
        ],
    )
    def post(self, request, room_pk):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or len(idempotency_key) > 64:
            raise MissingIdempotencyKeyError()

        serializer = SendGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room = get_object_or_404(Room, pk=room_pk)
        if room.status != Room.Status.LIVE:
            raise RoomNotLiveError()
        recipient = get_object_or_404(
            User, pk=serializer.validated_data["recipient_id"], is_active=True
        )
        if recipient == request.user:
            raise SelfGiftError()
        gift_type = get_object_or_404(
            GiftType, pk=serializer.validated_data["gift_type_id"]
        )

        gift, created = services.send_gift(
            sender=request.user,
            recipient=recipient,
            room=room,
            gift_type=gift_type,
            idempotency_key=idempotency_key,
        )
        return Response(
            GiftSerializer(gift).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RoomGiftListView(generics.ListAPIView):
    serializer_class = GiftSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Gift.objects.none()
        return (
            Gift.objects.filter(room_id=self.kwargs["room_pk"])
            .select_related("sender", "recipient", "gift_type")
        )
