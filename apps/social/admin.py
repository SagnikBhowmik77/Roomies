from django.contrib import admin

from .models import Follow, Notification


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("id", "follower", "following", "created_at")
    raw_id_fields = ("follower", "following")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "actor", "verb", "is_read", "created_at")
    list_filter = ("verb", "is_read")
    raw_id_fields = ("user", "actor", "room")
