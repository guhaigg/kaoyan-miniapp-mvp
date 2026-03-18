import re

import pytest

from app.db import SessionLocal
from app.models import NotificationDelivery, NotificationOutbox
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
    assert payload["bind_required"] is True
    assert payload["visitor_token"]
    assert payload["user_id"]
    assert payload["access_token"] is None


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
    assert login_payload["refresh_token"]
    assert login_payload["token_type"] == "bearer"
    assert login_payload["refresh_expires_in"] > login_payload["expires_in"]
    login_refresh_token = _extract_cookie(login_response, "gw_user_refresh")
    assert login_refresh_token

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["username"] == "student_a"
    assert me_payload["is_admin"] is False
    assert me_payload["is_premium"] is False
    assert me_payload["role"] == "user"
    assert "premium_expires_at" in me_payload

    identities_response = client.get(
        "/api/v1/auth/me/identities",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert identities_response.status_code == 200
    identities_payload = identities_response.json()
    assert identities_payload["total"] == 1
    assert identities_payload["items"][0]["identity_type"] == "password"
    assert identities_payload["items"][0]["login_name"] == "student_a"

    account_response = client.get(
        "/api/v1/auth/me/account",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )
    assert account_response.status_code == 200
    account_payload = account_response.json()
    assert account_payload["username"] == "student_a"
    assert account_payload["role"] == "user"
    assert len(account_payload["identities"]) == 1
    assert account_payload["identities"][0]["identity_type"] == "password"
    assert account_payload["roles"] == []
    assert account_payload["entitlements"] == []

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": login_refresh_token})
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["username"] == "student_a"
    assert refresh_payload["access_token"] != login_payload["access_token"]
    assert refresh_payload["refresh_token"]
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


def test_current_user_can_change_password(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "change_pass_user", "password": "StrongPass123", "nickname": "改密用户"},
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "change_pass_user", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    change_response = client.post(
        "/api/v1/auth/me/change-password",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"old_password": "StrongPass123", "new_password": "NewStrongPass123"},
    )
    assert change_response.status_code == 200
    assert change_response.json()["status"] == "ok"

    stale_login = client.post(
        "/api/v1/auth/login",
        json={"username": "change_pass_user", "password": "StrongPass123"},
    )
    assert stale_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "change_pass_user", "password": "NewStrongPass123"},
    )
    assert new_login.status_code == 200


def test_current_user_notification_history_lists_deliveries(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "notify_user", "password": "StrongPass123", "nickname": "通知用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "notify_user", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    with SessionLocal() as db:
        outbox = NotificationOutbox(
            content_id="content-1",
            event_type="content.upsert",
            payload={"title": "新公告", "school_name": "测试大学"},
            status="sent",
        )
        db.add(outbox)
        db.flush()
        delivery = NotificationDelivery(
            outbox_id=outbox.id,
            user_id=user_id,
            channel="bark",
            status="sent",
            payload={"title": "新公告", "school_name": "测试大学"},
        )
        db.add(delivery)
        db.commit()

    history_response = client.get(
        "/api/v1/auth/me/notifications/history?limit=5",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["channel"] == "bark"
    assert payload["items"][0]["status"] == "sent"
    assert payload["items"][0]["payload"]["title"] == "新公告"
    assert payload["items"][0]["payload"]["school_name"] == "测试大学"


def test_user_me_requires_login(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_wechat_bind_links_shadow_identity_to_portal_account(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "bind_user", "password": "StrongPass123", "nickname": "绑定用户"},
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "bind_user", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    silent_response = client.post("/api/v1/auth/silent-login", json={"code": "bind-code-1"})
    assert silent_response.status_code == 200
    silent_payload = silent_response.json()
    visitor_token = silent_payload["visitor_token"]
    assert silent_payload["user_state"] == "shadow"

    bind_response = client.post(
        "/api/v1/auth/wechat/bind",
        headers={
            "X-Visitor-Token": visitor_token,
            "Authorization": f"Bearer {access_token}",
        },
    )
    assert bind_response.status_code == 200
    bind_payload = bind_response.json()
    assert bind_payload["status"] == "ok"
    assert bind_payload["username"] == "bind_user"
    assert bind_payload["identity_type"] == "wechat_miniapp"
    assert bind_payload["access_token"]
    assert bind_payload["refresh_token"]
    assert bind_payload["role"] == "user"

    rebound_response = client.post("/api/v1/auth/silent-login", json={"code": "bind-code-1"})
    assert rebound_response.status_code == 200
    rebound_payload = rebound_response.json()
    assert rebound_payload["user_state"] == "bound"
    assert rebound_payload["bind_required"] is False
    assert rebound_payload["linked_portal_user_id"] == register_response.json()["user_id"]
    assert rebound_payload["access_token"]
    assert rebound_payload["refresh_token"]
    assert rebound_payload["username"] == "bind_user"
    assert rebound_payload["role"] == "user"


def test_wechat_bind_code_claim_links_shadow_identity_to_portal_account(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "code_bind_user", "password": "StrongPass123", "nickname": "码绑定用户"},
    )
    assert register_response.status_code == 200

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "code_bind_user", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    code_response = client.post(
        "/api/v1/auth/wechat/bind-code",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert code_response.status_code == 200
    code_payload = code_response.json()
    assert code_payload["status"] == "ok"
    assert len(code_payload["code"]) == 8
    assert code_payload["expires_in"] > 0

    silent_response = client.post("/api/v1/auth/silent-login", json={"code": "bind-code-ticket"})
    assert silent_response.status_code == 200
    visitor_token = silent_response.json()["visitor_token"]

    claim_response = client.post(
        "/api/v1/auth/wechat/bind-code/claim",
        json={"code": code_payload["code"]},
        headers={"X-Visitor-Token": visitor_token},
    )
    assert claim_response.status_code == 200
    claim_payload = claim_response.json()
    assert claim_payload["username"] == "code_bind_user"
    assert claim_payload["identity_type"] == "wechat_miniapp"

    identities_response = client.get(
        "/api/v1/auth/me/identities",
        headers={"Authorization": f"Bearer {claim_payload['access_token']}"},
    )
    assert identities_response.status_code == 200
    identities_payload = identities_response.json()
    assert identities_payload["total"] == 2
    assert {item["identity_type"] for item in identities_payload["items"]} == {"password", "wechat_miniapp"}


def test_wechat_bind_code_claim_rejects_invalid_code(client):
    silent_response = client.post("/api/v1/auth/silent-login", json={"code": "bind-code-missing"})
    visitor_token = silent_response.json()["visitor_token"]

    claim_response = client.post(
        "/api/v1/auth/wechat/bind-code/claim",
        json={"code": "INVALID99"},
        headers={"X-Visitor-Token": visitor_token},
    )
    assert claim_response.status_code == 404


def test_wechat_bind_rejects_identity_already_bound_to_other_account(client):
    first = client.post(
        "/api/v1/auth/register",
        json={"username": "wechat_bind_first", "password": "StrongPass123", "nickname": "first"},
    )
    second = client.post(
        "/api/v1/auth/register",
        json={"username": "wechat_bind_second", "password": "StrongPass123", "nickname": "second"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    first_login = client.post("/api/v1/auth/login", json={"username": "wechat_bind_first", "password": "StrongPass123"})
    second_login = client.post("/api/v1/auth/login", json={"username": "wechat_bind_second", "password": "StrongPass123"})
    assert first_login.status_code == 200
    assert second_login.status_code == 200

    silent_response = client.post("/api/v1/auth/silent-login", json={"code": "bind-code-conflict"})
    visitor_token = silent_response.json()["visitor_token"]

    first_bind = client.post(
        "/api/v1/auth/wechat/bind",
        headers={
            "X-Visitor-Token": visitor_token,
            "Authorization": f"Bearer {first_login.json()['access_token']}",
        },
    )
    assert first_bind.status_code == 200
    assert first_bind.json()["access_token"]

    conflict_bind = client.post(
        "/api/v1/auth/wechat/bind",
        headers={
            "X-Visitor-Token": visitor_token,
            "Authorization": f"Bearer {second_login.json()['access_token']}",
        },
    )
    assert conflict_bind.status_code == 409


def test_wechat_service_requires_credentials_when_mock_disabled(monkeypatch):
    monkeypatch.setenv("USE_MOCK_WECHAT", "false")
    monkeypatch.setenv("WECHAT_APPID", "")
    monkeypatch.setenv("WECHAT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="WECHAT_APPID and WECHAT_SECRET are required"):
        WechatService().exchange_code_for_openid("abc123")

    get_settings.cache_clear()
