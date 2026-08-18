from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.rooms.models import Room, RoomParticipant
from apps.users.models import User
from apps.users.serializers import UserPublicSerializer
from config.exceptions import APIError

from apps.rooms.events import broadcast

from . import services
from .models import Gift, GiftType, GoalPledge, LedgerEntry, Question, Wallet
from .serializers import (
    AskQuestionSerializer,
    CreatePledgeSerializer,
    GiftSerializer,
    GiftTypeSerializer,
    LedgerEntrySerializer,
    PledgeSerializer,
    QuestionSerializer,
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


class SelfQuestionError(APIError):
    code = "self_question"
    message = "You cannot pay to ask yourself a question."


class NotRoomHostError(APIError):
    status_code = 403
    code = "not_host"
    message = "Only the host can resolve questions."


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

        recipient_id = serializer.validated_data.get("recipient_id")
        recipient = None
        if recipient_id:
            recipient = get_object_or_404(User, pk=recipient_id, is_active=True)
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


class LeaderboardView(APIView):
    """
    Top earners across every income stream — gifts, answered questions, and
    settled pledges. Computed from the ledger rather than the Gift table, so
    split room-gifts and question payouts all count correctly.
    """

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        rows = (
            LedgerEntry.objects.filter(
                reason__in=LedgerEntry.EARNING_REASONS, wallet__user__isnull=False
            )
            .values("wallet__user")
            .annotate(coins_received=Sum("delta_coins"), gift_count=Count("id"))
            .order_by("-coins_received")[:5]
        )
        users = {
            u.id: u
            for u in User.objects.filter(id__in=[r["wallet__user"] for r in rows])
        }
        return Response(
            [
                {
                    **UserPublicSerializer(users[r["wallet__user"]]).data,
                    "coins_received": r["coins_received"],
                    "gift_count": r["gift_count"],
                }
                for r in rows
                if r["wallet__user"] in users
            ]
        )


class QuestionListCreateView(APIView):
    """
    The paid question queue.

    GET  — pending questions, highest stake first (that ordering is the whole
           point: money buys queue position, not a louder voice).
    POST — stake coins on a question; they are escrowed immediately.
    """

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "gifts"

    @extend_schema(responses={200: QuestionSerializer(many=True)})
    def get(self, request, room_pk):
        qs = (
            Question.objects.filter(room_id=room_pk)
            .select_related("asker")
            .order_by("status", "-coins", "created_at")
        )
        return Response(QuestionSerializer(qs, many=True).data)

    @extend_schema(
        request=AskQuestionSerializer,
        responses={201: QuestionSerializer},
        parameters=[
            OpenApiParameter(
                name="Idempotency-Key",
                location=OpenApiParameter.HEADER,
                required=True,
                type=str,
            )
        ],
    )
    def post(self, request, room_pk):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or len(idempotency_key) > 64:
            raise MissingIdempotencyKeyError()

        serializer = AskQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room = get_object_or_404(Room, pk=room_pk)
        if room.status != Room.Status.LIVE:
            raise RoomNotLiveError()
        if room.host_id == request.user.id:
            raise SelfQuestionError()

        question, created = services.ask_question(
            asker=request.user,
            room=room,
            text=serializer.validated_data["text"],
            coins=serializer.validated_data["coins"],
            idempotency_key=idempotency_key,
        )
        if created:
            broadcast(room.id, "question", action="asked")
        return Response(
            QuestionSerializer(question).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ResolveQuestionView(APIView):
    """Host answers a question (stake released) or declines it (refunded)."""

    def post(self, request, room_pk, pk, action):
        question = get_object_or_404(
            Question.objects.select_related("room", "asker"), pk=pk, room_id=room_pk
        )
        is_host = question.room.host_id == request.user.id
        if action == "answer":
            if not is_host:
                raise NotRoomHostError()
            resolved = services.answer_question(question)
        else:
            # the asker may withdraw their own question; the host may decline
            if not is_host and question.asker_id != request.user.id:
                raise NotRoomHostError()
            resolved = services.refund_question(question)
        broadcast(room_pk, "question", action=action)
        return Response(QuestionSerializer(resolved).data)


class PledgeView(APIView):
    """Contribute toward a room's goal. Escrowed until it settles or refunds."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "gifts"

    @extend_schema(responses={200: PledgeSerializer(many=True)})
    def get(self, request, room_pk):
        qs = GoalPledge.objects.filter(room_id=room_pk).select_related("user")
        return Response(PledgeSerializer(qs, many=True).data)

    @extend_schema(request=CreatePledgeSerializer, responses={201: PledgeSerializer})
    def post(self, request, room_pk):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key or len(idempotency_key) > 64:
            raise MissingIdempotencyKeyError()

        serializer = CreatePledgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room = get_object_or_404(Room, pk=room_pk)
        if room.status != Room.Status.LIVE:
            raise RoomNotLiveError()

        record, created = services.pledge(
            user=request.user,
            room=room,
            coins=serializer.validated_data["coins"],
            idempotency_key=idempotency_key,
        )
        if created:
            broadcast(room.id, "goal", action="pledged")
        return Response(
            PledgeSerializer(record).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class HostStatsView(APIView):
    """
    Public, verifiable reputation for a host — the page they put in their bio.
    Every number here is derived from the ledger or from room records, never
    from a counter someone could inflate.
    """

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk, is_active=True)
        rooms = Room.objects.filter(host=user)

        # listener-minutes across every room they've hosted
        now = timezone.now()
        spans = RoomParticipant.objects.filter(room__host=user).exclude(
            user=user
        ).values_list("joined_at", "left_at")
        listener_seconds = sum(
            ((left or now) - joined).total_seconds() for joined, left in spans
        )

        earned = (
            LedgerEntry.objects.filter(
                wallet__user=user, reason__in=LedgerEntry.EARNING_REASONS
            ).aggregate(total=Sum("delta_coins"))["total"]
            or 0
        )
        supporters = (
            LedgerEntry.objects.filter(
                wallet__user=user, reason__in=LedgerEntry.EARNING_REASONS
            )
            .exclude(gift__isnull=True)
            .values("gift__sender")
            .annotate(coins=Sum("delta_coins"))
            .order_by("-coins")[:3]
        )
        supporter_users = {
            u.id: u
            for u in User.objects.filter(id__in=[s["gift__sender"] for s in supporters])
        }

        return Response(
            {
                "user": UserPublicSerializer(user).data,
                "rooms_hosted": rooms.count(),
                "live_now": rooms.filter(status=Room.Status.LIVE).exists(),
                "listener_minutes": int(listener_seconds // 60),
                "coins_earned": earned,
                "questions_answered": Question.objects.filter(
                    room__host=user, status=Question.Status.ANSWERED
                ).count(),
                "followers": user.follower_set.count(),
                "top_supporters": [
                    {
                        **UserPublicSerializer(supporter_users[s["gift__sender"]]).data,
                        "coins": s["coins"],
                    }
                    for s in supporters
                    if s["gift__sender"] in supporter_users
                ],
            }
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
