from django.urls import path

from .views import (
    GiftTypeListView,
    RoomGiftListView,
    SendGiftView,
    TopupView,
    WalletView,
)

urlpatterns = [
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
