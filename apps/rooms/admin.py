from django.contrib import admin

from .models import Room, RoomParticipant


class RoomParticipantInline(admin.TabularInline):
    model = RoomParticipant
    extra = 0
    raw_id_fields = ("user",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "host", "status", "listener_count", "started_at")
    list_filter = ("status", "topic")
    search_fields = ("title", "host__phone")
    raw_id_fields = ("host",)
    inlines = (RoomParticipantInline,)
