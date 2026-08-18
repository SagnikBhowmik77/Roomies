import pytest
from django.urls import reverse

from apps.users.models import User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

REQUEST_OTP = reverse("request-otp")
VERIFY_OTP = reverse("verify-otp")
REFRESH = reverse("token-refresh")
ME = reverse("me")

PHONE = "+919000000001"
DEV_CODE = "123456"


def request_and_verify(client, phone=PHONE):
    client.post(REQUEST_OTP, {"phone": phone})
    return client.post(VERIFY_OTP, {"phone": phone, "code": DEV_CODE})


def test_request_otp_returns_debug_code_in_dev(api_client):
    response = api_client.post(REQUEST_OTP, {"phone": PHONE})
    assert response.status_code == 200
    assert response.data["debug_code"] == DEV_CODE


def test_request_otp_rejects_bad_phone(api_client):
    response = api_client.post(REQUEST_OTP, {"phone": "not-a-phone"})
    assert response.status_code == 400


def test_verify_otp_creates_user_and_returns_tokens(api_client):
    response = request_and_verify(api_client)
    assert response.status_code == 201
    assert "access" in response.data and "refresh" in response.data
    assert User.objects.filter(phone=PHONE).exists()


def test_verify_otp_existing_user_returns_200(api_client):
    UserFactory(phone=PHONE)
    response = request_and_verify(api_client)
    assert response.status_code == 200
    assert response.data["created"] is False


def test_verify_otp_wrong_code_rejected(api_client):
    api_client.post(REQUEST_OTP, {"phone": PHONE})
    response = api_client.post(VERIFY_OTP, {"phone": PHONE, "code": "000000"})
    assert response.status_code == 400
    assert response.data["code"] == "invalid_otp"
    assert not User.objects.filter(phone=PHONE).exists()


def test_otp_is_single_use(api_client):
    request_and_verify(api_client)
    response = api_client.post(VERIFY_OTP, {"phone": PHONE, "code": DEV_CODE})
    assert response.status_code == 400


def test_banned_user_cannot_login(api_client):
    UserFactory(phone=PHONE, is_banned=True)
    response = request_and_verify(api_client)
    assert response.status_code == 403
    assert response.data["code"] == "user_banned"


def test_refresh_returns_new_access_token(api_client):
    tokens = request_and_verify(api_client).data
    response = api_client.post(REFRESH, {"refresh": tokens["refresh"]})
    assert response.status_code == 200
    assert "access" in response.data


def test_me_requires_auth(api_client):
    assert api_client.get(ME).status_code == 401


def test_me_returns_and_updates_profile(auth_client, user):
    assert auth_client.get(ME).data["phone"] == user.phone
    response = auth_client.patch(ME, {"display_name": "Neo", "country": "IN"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.display_name == "Neo"
