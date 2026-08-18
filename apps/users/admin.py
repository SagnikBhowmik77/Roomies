from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("-created_at",)
    list_display = ("id", "phone", "display_name", "country", "is_banned", "created_at")
    list_filter = ("is_banned", "is_staff", "country")
    search_fields = ("phone", "display_name")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Profile", {"fields": ("display_name", "avatar_url", "country")}),
        ("Status", {"fields": ("is_banned", "is_active", "is_staff", "is_superuser")}),
    )
    add_fieldsets = ((None, {"fields": ("phone", "password1", "password2")}),)
    readonly_fields = ()
    filter_horizontal = ()
