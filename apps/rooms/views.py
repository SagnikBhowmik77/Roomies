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

from .cache import room_list_cache_key
from .models import Room, RoomParticipant
from .permissions import IsHostOrReadOnly
from .serializers import RoomParticipantSerializer, RoomSerializer
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
            room=room, user=self.request.user, role=RoomParticipant.Role.HOST
        )
        room_went_live.send(sender=Room, room=room)
        # Fan-out happens off the request path: creating a room stays O(1)
        # no matter how many followers the host has.
        notify_followers_of_live_room.delay(room.id)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        room = self.get_object()
        if room.status == Room.Status.ENDED:
            raise AlreadyEndedError()
        room.end()
        room_ended.send(sender=Room, room=room)
        return Response(RoomSerializer(self._reload(room.pk)).data)

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

    def _reload(self, pk):
        return self.get_queryset().get(pk=pk)
