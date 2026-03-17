import re

import pytest

from app.config import get_settings
from app.services.wechat import WechatService


def _extract_cookie(response, cookie_name: str) -> str | None:
    set_cookie = response.headers.get("set-cookie", "")
    match = re.search(rf"{cookie_name}=([^;]+);", set_cookie)
    if not match:
        return None
    return match.group(1)


def test_silent_login_returns_shadow_account(client):
    response = client.post("/api/v1/auth/silent-login", json={"code": "abc123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_state"] == "shadow"
    assert payload["visitor_token"]
    assert payload["user_id"]


def test_user_register_login_refresh_logout_flow(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "student_a", "password": "StrongPass123", "nickname": "同学A"},
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload["username"] == "student_a"
    assert register_payload["status"] == "active"

    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={"username": "student_a", "password": "StrongPass123", "nickname": "同学A"},
    )
    assert duplicate_response.status_code == 409

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "student_a", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload["username"] == "student_a"
    assert login_payload["access_token"]
    assert login_payload["token_type"] == "bearer"
    assert login_payload["refresh_expires_in"] > login_payload["expires_in"]
    login_refresh_token = _extract_cookie(login_response, "gw_user_refresh")
    assert login_refresh_token

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "student_a"

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": login_refresh_token})
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["username"] == "student_a"
    assert refresh_payload["access_token"] != login_payload["access_token"]
    rotated_refresh_token = _extract_cookie(refresh_response, "gw_user_refresh")
    assert rotated_refresh_token
    assert rotated_refresh_token != login_refresh_token

    reused_refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": login_refresh_token})
    assert reused_refresh_response.status_code == 401

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": rotated_refresh_token})
    assert logout_response.status_code == 200
    assert logout_response.json()["status"] == "ok"

    refresh_after_logout = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated_refresh_token})
    assert refresh_after_logout.status_code == 401


def test_user_me_requires_login(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_wechat_service_requires_credentials_when_mock_disabled(monkeypatch):
    monkeypatch.setenv("USE_MOCK_WECHAT", "false")
    monkeypatch.setenv("WECHAT_APPID", "")
    monkeypatch.setenv("WECHAT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="WECHAT_APPID and WECHAT_SECRET are required"):
        WechatService().exchange_code_for_openid("abc123")

    get_settings.cache_clear()
