import httpx

from app.config import get_settings
from app.db import SessionLocal
from app.models import NotificationDelivery
from app.services.notifications import notification_engine


def _access_token(client, username: str = "notify_user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": "通知用户"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_outbox_to_delivery_flow(client):
    token = _access_token(client)
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "电子科技大学调剂通知",
            "body": "2026 年硕士调剂公告发布",
            "summary": "请关注系统开放时间",
            "school_name": "电子科技大学",
            "source_url": "https://example.com/notice-1",
        },
        headers=admin_headers,
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed == 1

    pending_resp = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_resp.status_code == 200
    payload = pending_resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["payload"]["title"] == "电子科技大学调剂通知"

    pending_again = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_again.status_code == 200
    assert pending_again.json()["total"] == 0


def test_bark_delivery_flow(client, monkeypatch):
    token = _access_token(client, username="bark_user")
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    settings = get_settings()
    settings.enable_bark_notifications = True
    settings.bark_server_url = "https://bark.example.com"
    settings.notification_batch_window_seconds = 0

    bark_resp = client.put(
        "/api/v1/auth/me/notifications/bark",
        json={"enabled": True, "bark_key": "device-key-123"},
        headers=user_headers,
    )
    assert bark_resp.status_code == 200
    assert bark_resp.json()["enabled"] is True
    assert bark_resp.json()["bark_key_configured"] is True

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "电子科技大学调剂通知",
            "body": "2026 年硕士调剂公告发布",
            "summary": "请关注系统开放时间",
            "school_name": "电子科技大学",
            "source_url": "https://example.com/notice-2",
        },
        headers=admin_headers,
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed == 1

    requests = []

    def fake_get(url, params=None, timeout=0):
        requests.append({"url": url, "params": params, "timeout": timeout})
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.services.notifications.httpx.get", fake_get)

    delivery_processed = notification_engine.process_delivery_batch()
    assert delivery_processed == 1
    assert requests
    assert requests[0]["url"].startswith("https://bark.example.com/device-key-123/")
    assert requests[0]["params"]["url"] == "https://example.com/notice-2"

    with SessionLocal() as db:
        bark_row = (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.user_id.is_not(None), NotificationDelivery.channel == "bark")
            .one()
        )
        assert bark_row.status == "sent"

        inapp_row = (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.user_id.is_not(None), NotificationDelivery.channel == "inapp")
            .one()
        )
        assert inapp_row.status == "pending"


def test_bark_delivery_failure_marks_retry_or_failed(client, monkeypatch):
    token = _access_token(client, username="bark_retry_user")
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    settings = get_settings()
    settings.enable_bark_notifications = True
    settings.bark_server_url = "https://bark.example.com"
    settings.notification_batch_window_seconds = 0
    settings.notification_max_attempts = 1

    bark_resp = client.put(
        "/api/v1/auth/me/notifications/bark",
        json={"enabled": True, "bark_key": "device-key-456"},
        headers=user_headers,
    )
    assert bark_resp.status_code == 200

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "北京大学", "category": "all"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "北京大学公告",
            "body": "最新通知",
            "school_name": "北京大学",
            "source_url": "https://example.com/notice-3",
        },
        headers=admin_headers,
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed == 1

    def fake_get(_url, params=None, timeout=0):
        raise RuntimeError(f"bark send failed: {params}")

    monkeypatch.setattr("app.services.notifications.httpx.get", fake_get)

    delivery_processed = notification_engine.process_delivery_batch()
    assert delivery_processed == 1

    with SessionLocal() as db:
        bark_row = db.query(NotificationDelivery).filter(NotificationDelivery.channel == "bark").one()
        assert bark_row.status == "failed"
        assert "bark send failed" in (bark_row.last_error or "")
