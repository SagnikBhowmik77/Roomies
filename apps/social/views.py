from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import User
from config.exceptions import APIError

from .models import Follow, Notification
from .serializers import (
    FollowerSerializer,
    FollowingSerializer,
    NotificationSerializer,
)


class SelfFollowError(APIError):
    code = "self_follow"
    message = "You cannot follow yourself."


class FollowView(APIView):
    """POST to follow, DELETE to unfollow. Both idempotent."""

    @extend_schema(request=None, responses={201: OpenApiTypes.OBJECT})
    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk, is_active=True)
        if target == request.user:
            raise SelfFollowError()
        _, created = Follow.objects.get_or_create(
            follower=request.user, following=target
        )
        return Response(
            {"following": True},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk):
        Follow.objects.filter(follower=request.user, following_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FollowersListView(generics.ListAPIView):
    serializer_class = FollowerSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Follow.objects.none()
        return Follow.objects.filter(following_id=self.kwargs["pk"]).select_related(
            "follower"
        )


class FollowingListView(generics.ListAPIView):
    serializer_class = FollowingSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Follow.objects.none()
        return Follow.objects.filter(follower_id=self.kwargs["pk"]).select_related(
            "following"
        )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user).select_related(
            "actor"
        )
