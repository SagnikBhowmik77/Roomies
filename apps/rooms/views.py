from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.exceptions import APIError
from config.pagination import DefaultCursorPagination

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .cache import room_list_cache_key
from .models import Room, RoomParticipant
from .permissions import IsHostOrReadOnly
from .serializers import (
    RoomMessageSerializer,
    RoomParticipantSerializer,
    RoomSerializer,
)
from .signals import room_ended, room_went_live
from .tasks import notify_followers_of_live_room


class RoomFullError(APIError):
    status_code = 409
    code = "room_full"
    message = "This room is full."


class RoomNotLiveError(APIError):
    code = "room_not_live"
    message = "This room has ended."


class AlreadyEndedError(APIError):
    code = "room_already_ended"
    message = "This room is already ended."


class NotHostError(APIError):
    status_code = 403
    code = "not_host"
    message = "Only the host can manage speakers."


class InvalidRoleError(APIError):
    code = "invalid_role"
    message = "Role must be 'speaker' or 'listener'."


class RoomCursorPagination(DefaultCursorPagination):
    ordering = "-started_at"


class RoomViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Rooms are created live and can only transition live -> ended (no
    update/delete): an audio room is an event, not a document.
    """

    serializer_class = RoomSerializer
    permission_classes = (IsHostOrReadOnly,)
    pagination_class = RoomCursorPagination
    filterset_fields = {"status": ["exact"], "topic": ["exact"]}

    def get_queryset(self):
        # select_related folds the host into the room query (no per-row
        # lookup); the annotate replaces a COUNT() query per room.
        qs = (
            Room.objects.select_related("host")
            .annotate(
                active_participants=Count(
                    "participants", filter=Q(participants__left_at__isnull=True)
                )
            )
        )
        country = self.request.query_params.get("country")
        if country:
            qs = qs.filter(host__country=country.upper())
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(title__icontains=search.strip())
        return qs

    def list(self, request, *args, **kwargs):
        # Cache only the hot path: the live feed. Ended-room history is a
        # long tail not worth cache space.
        cacheable = request.query_params.get("status") == "live"
        key = room_list_cache_key(request.META.get("QUERY_STRING", ""))
        if cacheable:
            cached = cache.get(key)
            if cached is not None:
                return Response(cached)
        response = super().list(request, *args, **kwargs)
        if cacheable:
            cache.set(key, response.data, settings.ROOM_LIST_CACHE_TTL)
        return response

    def perform_create(self, serializer):
        room = serializer.save(host=self.request.user)
        RoomParticipant.objects.create(
            room=room,
            user=self.request.user,
            role=RoomParticipant.Role.HOST,
            speaker_since=timezone.now(),
        )
        room_went_live.send(sender=Room, room=room)
        # Fan-out happens off the request path: creating a room stays O(1)
        # no matter how many followers the host has.
        notify_followers_of_live_room.delay(room.id)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        from apps.economy import services as economy

        room = self.get_object()
        if room.status == Room.Status.ENDED:
            raise AlreadyEndedError()
        room.end()
        # nobody keeps money for work that never happened
        refunded_questions = economy.refund_pending_questions(room)
        refunded_pledges = 0 if room.goal_reached_at else economy.refund_pledges(room)
        room_ended.send(sender=Room, room=room)
        data = RoomSerializer(self._reload(room.pk)).data
        data["refunded_questions"] = refunded_questions
        data["refunded_pledges"] = refunded_pledges
        return Response(data)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        with transaction.atomic():
            # Lock the room row so two concurrent joins can't both pass the
            # capacity check.
            room = get_object_or_404(Room.objects.select_for_update(), pk=pk)
            if room.status != Room.Status.LIVE:
                raise RoomNotLiveError()
            active = room.participants.filter(left_at__isnull=True).count()
            if active >= room.max_seats:
                raise RoomFullError()
            try:
                # savepoint: a unique-constraint hit must not poison the
                # outer transaction
                with transaction.atomic():
                    participant = RoomParticipant.objects.create(
                        room=room, user=request.user
                    )
            except IntegrityError:
                # already seated: idempotent success
                participant = room.participants.get(
                    user=request.user, left_at__isnull=True
                )
                created = False
            else:
                created = True
                room.listener_count = active + 1
                room.save(update_fields=("listener_count",))
        return Response(
            RoomParticipantSerializer(participant).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        with transaction.atomic():
            room = get_object_or_404(Room.objects.select_for_update(), pk=pk)
            updated = room.participants.filter(
                user=request.user, left_at__isnull=True
            ).update(left_at=timezone.now())
            if updated:
                room.listener_count = max(room.listener_count - 1, 0)
                room.save(update_fields=("listener_count",))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def participants(self, request, pk=None):
        qs = (
            self.get_object()
            .participants.filter(left_at__isnull=True)
            .select_related("user")
            .order_by("joined_at")
        )
        return Response(RoomParticipantSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def messages(self, request, pk=None):
        """Last 50 chat messages, oldest first (for direct rendering)."""
        room = self.get_object()
        qs = list(
            room.messages.select_related("user").order_by("-created_at")[:50]
        )[::-1]
        return Response(RoomMessageSerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"participants/(?P<user_id>\d+)/role",
    )
    def set_role(self, request, pk=None, user_id=None):
        """Host promotes a listener to speaker or demotes back."""
        room = self.get_object()
        if room.host_id != request.user.id:
            raise NotHostError()
        role = request.data.get("role")
        if role not in (RoomParticipant.Role.SPEAKER, RoomParticipant.Role.LISTENER):
            raise InvalidRoleError()
        participant = get_object_or_404(
            RoomParticipant.objects.select_related("user"),
            room=room,
            user_id=user_id,
            left_at__isnull=True,
        )
        if participant.role == RoomParticipant.Role.HOST:
            raise InvalidRoleError("The host's role cannot be changed.")
        participant.role = role
        # stage time starts when they're promoted and stops when demoted —
        # this is the weight behind proportional revenue splits
        participant.speaker_since = (
            timezone.now() if role == RoomParticipant.Role.SPEAKER else None
        )
        participant.save(update_fields=("role", "speaker_since"))
        # push the change to everyone connected to the room
        async_to_sync(get_channel_layer().group_send)(
            f"room_{room.id}",
            {
                "type": "room.event",
                "event": "role",
                "user": {
                    "id": participant.user.id,
                    "display_name": participant.user.display_name,
                },
                "value": role,
            },
        )
        return Response(RoomParticipantSerializer(participant).data)

    def _reload(self, pk):
        return self.get_queryset().get(pk=pk)
