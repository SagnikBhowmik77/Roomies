from rest_framework import mixins, permissions, viewsets

from config.exceptions import APIError

from .models import Report
from .serializers import ReportReviewSerializer, ReportSerializer


class SelfReportError(APIError):
    code = "self_report"
    message = "You cannot report yourself."


class ReportViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Users file reports and see their own; staff see all and can review
    (update status/notes).
    """

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Report.objects.none()
        qs = Report.objects.select_related("reporter", "reported_user")
        if self.request.user.is_staff:
            return qs
        return qs.filter(reporter=self.request.user)

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return ReportReviewSerializer
        return ReportSerializer

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [permissions.IsAdminUser()]
        return super().get_permissions()

    def perform_create(self, serializer):
        if serializer.validated_data["reported_user"] == self.request.user:
            raise SelfReportError()
        serializer.save(reporter=self.request.user)

    def perform_update(self, serializer):
        serializer.save(reviewed_by=self.request.user)
