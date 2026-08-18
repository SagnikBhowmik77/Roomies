import pytest
from rest_framework.test import APIClient

from apps.moderation.models import Report
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

REPORTS = "/api/v1/reports/"


@pytest.fixture
def staff_client(db):
    staff = UserFactory(is_staff=True)
    client = APIClient()
    client.force_authenticate(staff)
    return client


def test_create_report(auth_client, user, other_user):
    response = auth_client.post(
        REPORTS, {"reported_user": other_user.id, "reason": "spam"}
    )
    assert response.status_code == 201
    report = Report.objects.get()
    assert report.reporter == user
    assert report.status == Report.Status.OPEN


def test_cannot_report_self(auth_client, user):
    response = auth_client.post(REPORTS, {"reported_user": user.id, "reason": "spam"})
    assert response.status_code == 400
    assert response.data["code"] == "self_report"


def test_users_see_only_their_own_reports(auth_client, user, other_user):
    Report.objects.create(reporter=user, reported_user=other_user, reason="spam")
    Report.objects.create(
        reporter=other_user, reported_user=user, reason="harassment"
    )
    response = auth_client.get(REPORTS)
    assert len(response.data["results"]) == 1


def test_staff_see_all_reports(staff_client, user, other_user):
    Report.objects.create(reporter=user, reported_user=other_user, reason="spam")
    Report.objects.create(
        reporter=other_user, reported_user=user, reason="harassment"
    )
    response = staff_client.get(REPORTS)
    assert len(response.data["results"]) == 2


def test_staff_can_review_report(staff_client, user, other_user):
    report = Report.objects.create(
        reporter=user, reported_user=other_user, reason="spam"
    )
    response = staff_client.patch(
        f"{REPORTS}{report.id}/", {"status": "actioned", "notes": "banned"}
    )
    assert response.status_code == 200
    report.refresh_from_db()
    assert report.status == Report.Status.ACTIONED
    assert report.reviewed_by is not None


def test_non_staff_cannot_review(auth_client, user, other_user):
    report = Report.objects.create(
        reporter=user, reported_user=other_user, reason="spam"
    )
    response = auth_client.patch(f"{REPORTS}{report.id}/", {"status": "actioned"})
    assert response.status_code == 403
