from django.apps import AppConfig


class RoomsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rooms"
    label = "rooms"

    def ready(self):
        from . import signals  # noqa: F401
