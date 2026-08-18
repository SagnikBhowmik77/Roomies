from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsHostOrReadOnly(BasePermission):
    """Anyone can view a room; only its host can mutate it (e.g. end it)."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.host_id == request.user.id
