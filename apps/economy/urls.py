from django.urls import path

from .views import (
    GiftTypeListView,
    HostStatsView,
    LeaderboardView,
    PledgeView,
    QuestionListCreateView,
    ResolveQuestionView,
    RoomGiftListView,
    SendGiftView,
    TopupView,
    WalletView,
)

urlpatterns = [
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("users/<int:pk>/stats/", HostStatsView.as_view(), name="host-stats"),
    path(
        "rooms/<int:room_pk>/questions/",
        QuestionListCreateView.as_view(),
        name="questions",
    ),
    path(
        "rooms/<int:room_pk>/questions/<int:pk>/<str:action>/",
        ResolveQuestionView.as_view(),
        name="resolve-question",
    ),
    path("rooms/<int:room_pk>/pledges/", PledgeView.as_view(), name="pledges"),
    path("wallet/", WalletView.as_view(), name="wallet"),
    path("wallet/topup/", TopupView.as_view(), name="wallet-topup"),
    path("gift-types/", GiftTypeListView.as_view(), name="gift-types"),
    path("rooms/<int:room_pk>/gifts/", SendGiftView.as_view(), name="send-gift"),
    path(
        "rooms/<int:room_pk>/gifts/history/",
        RoomGiftListView.as_view(),
        name="room-gifts",
    ),
]
