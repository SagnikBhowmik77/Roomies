from django.urls import path

from .views import (
    FollowersListView,
    FollowingListView,
    FollowView,
    NotificationListView,
    SuggestedUsersView,
)

urlpatterns = [
    path("users/suggested/", SuggestedUsersView.as_view(), name="suggested-users"),
    path("users/<int:pk>/follow/", FollowView.as_view(), name="follow"),
    path("users/<int:pk>/followers/", FollowersListView.as_view(), name="followers"),
    path("users/<int:pk>/following/", FollowingListView.as_view(), name="following"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
]
