from datetime import timedelta

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

from rest_framework.parsers import MultiPartParser

from .cache import room_list_cache_key
from .models import Room, RoomParticipant, RoomRecording
from .permissions import IsHostOrReadOnly
from .services import close_room, expire_due_rooms
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


class MissingAudioError(APIError):
    code = "missing_audio"
    message = "No audio file was uploaded."


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
        # select_related folds the host and the (reverse one-to-one)
        # recording into the room query — without the latter, the
        # has_recording field would fire one query per row. The annotate
        # replaces a COUNT() query per room.
        qs = (
            Room.objects.select_related("host", "recording")
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
        # A time-boxed room whose clock ran out is no longer live, even if the
        # worker hasn't swept it yet. Excluding it here costs nothing (same
        # WHERE clause) and keeps the feed honest between sweeps; the Celery
        # beat task does the authoritative close and issues the refunds.
        if self.request.query_params.get("status") == Room.Status.LIVE:
            qs = qs.exclude(ends_at__isnull=False, ends_at__lte=timezone.now())
        return qs

    def retrieve(self, request, *args, **kwargs):
        # one room, one cheap check: close it properly before showing it
        room = self.get_object()
        if (
            room.status == Room.Status.LIVE
            and room.ends_at
            and room.ends_at <= timezone.now()
        ):
            close_room(room)
            room = self._reload(room.pk)
        return Response(RoomSerializer(room).data)

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
        duration = serializer.validated_data.get("duration_minutes")
        room = serializer.save(
            host=self.request.user,
            ends_at=(
                timezone.now() + timedelta(minutes=duration) if duration else None
            ),
        )
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
        room = self.get_object()
        if room.status == Room.Status.ENDED:
            raise AlreadyEndedError()
        # nobody keeps money for work that never happened
        refunds = close_room(room)
        data = RoomSerializer(self._reload(room.pk)).data
        data.update(refunds)
        return Response(data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def recording(self, request, pk=None):
        """Host uploads the browser-mixed audio capture of the room."""
        room = self.get_object()
        if room.host_id != request.user.id:
            raise NotHostError()
        audio = request.FILES.get("audio")
        if not audio:
            raise MissingAudioError()
        RoomRecording.objects.update_or_create(
            room=room,
            defaults={
                "audio": audio,
                "uploaded_by": request.user,
                "duration_seconds": int(float(request.data.get("duration") or 0)),
            },
        )
        return Response(
            RoomSerializer(self._reload(room.pk)).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"])
    def replay(self, request, pk=None):
        """
        Everything needed to relive a room: the audio (if it was recorded)
        plus one merged, timestamped timeline of what happened — chat,
        captions, gifts and questions — each with an offset in seconds from
        the moment the room went live.
        """
        room = self.get_object()
        start = room.started_at

        def offset(when):
            return max(0, int((when - start).total_seconds()))

        timeline = []
        for m in room.messages.select_related("user"):
            timeline.append(
                {
                    "kind": "chat",
                    "at": offset(m.created_at),
                    "who": m.user.display_name,
                    "text": m.text,
                }
            )
        for c in room.captions.select_related("user"):
            timeline.append(
                {
                    "kind": "caption",
                    "at": offset(c.created_at),
                    "who": c.user.display_name,
                    "text": c.text,
                }
            )
        for g in room.gifts.select_related("sender", "recipient", "gift_type"):
            timeline.append(
                {
                    "kind": "gift",
                    "at": offset(g.created_at),
                    "who": g.sender.display_name,
                    "text": (
                        f"sent {g.gift_type.name} "
                        f"({g.coins}) to "
                        f"{g.recipient.display_name if g.recipient else 'the stage'}"
                    ),
                }
            )
        for q in room.questions.select_related("asker"):
            timeline.append(
                {
                    "kind": "question",
                    "at": offset(q.created_at),
                    "who": q.asker.display_name,
                    "text": f"[{q.coins} coins] {q.text}",
                }
            )
        timeline.sort(key=lambda row: row["at"])

        recording = getattr(room, "recording", None)
        return Response(
            {
                "room": RoomSerializer(self._reload(room.pk)).data,
                "audio_url": (
                    request.build_absolute_uri(recording.audio.url)
                    if recording
                    else None
                ),
                "duration_seconds": recording.duration_seconds if recording else 0,
                "timeline": timeline,
            }
        )

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
