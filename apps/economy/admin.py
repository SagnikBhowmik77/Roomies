from django.contrib import admin

from .models import Gift, GiftType, GoalPledge, LedgerEntry, Question, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "label", "balance_coins")
    raw_id_fields = ("user",)
    search_fields = ("user__phone", "label")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "asker", "coins", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("room", "asker")


@admin.register(GoalPledge)
class GoalPledgeAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "user", "coins", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("room", "user")


@admin.register(GiftType)
class GiftTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "coins", "is_active")
    list_editable = ("is_active",)


@admin.register(Gift)
class GiftAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "recipient", "room", "coins", "created_at")
    raw_id_fields = ("sender", "recipient", "room")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "wallet", "delta_coins", "reason", "created_at")
    list_filter = ("reason",)
    raw_id_fields = ("wallet", "gift")

    # append-only in the UI too
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
