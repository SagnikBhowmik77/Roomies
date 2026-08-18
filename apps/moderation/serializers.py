from rest_framework import serializers

from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = (
            "id",
            "reported_user",
            "room",
            "reason",
            "status",
            "notes",
            "created_at",
        )
        read_only_fields = ("status",)


class ReportReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ("status", "notes")
