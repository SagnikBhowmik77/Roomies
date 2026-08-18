from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "reported_user",
        "reason",
        "status",
        "created_at",
    )
    list_filter = ("status", "reason")
    raw_id_fields = ("reporter", "reported_user", "room", "reviewed_by")
