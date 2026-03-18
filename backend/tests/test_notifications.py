import httpx
from datetime import timedelta

from app.config import get_settings
from app.db import SessionLocal
from app.models import NotificationDelivery, PortalUser
from app.models import PortalUserSubscription
from app.models import utcnow
from app.services.account_access import ENTITLEMENT_SOURCE_ADMIN_GRANT, upsert_premium_entitlement
from app.services.notifications import notification_engine


def _access_token(client, username: str = "notify_user", *, premium: bool = False) -> str:
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": "通知用户"},
    )
    if premium:
        with SessionLocal() as db:
            user = db.query(PortalUser).filter(PortalUser.username == username).one()
            upsert_premium_entitlement(
                db,
                user_id=user.id,
                operator_account_id=None,
                expires_at=None,
                source=ENTITLEMENT_SOURCE_ADMIN_GRANT,
            )
            db.commit()
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_outbox_to_delivery_flow(client):
    token = _access_token(client, premium=True)
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
    assert "调剂" in payload["items"][0]["payload"]["tags"]

    pending_again = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_again.status_code == 200
    assert pending_again.json()["total"] == 0


def test_bark_delivery_flow(client, monkeypatch):
    token = _access_token(client, username="bark_user", premium=True)
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
    token = _access_token(client, username="bark_retry_user", premium=True)
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


def test_expired_premium_user_school_subscription_is_recycled_and_no_school_delivery(client):
    token = _access_token(client, username="expired_notify_user", premium=True)
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "南京大学", "category": "all"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    with SessionLocal() as db:
        user = db.query(PortalUser).filter(PortalUser.username == "expired_notify_user").one()
        entitlement = next(x for x in user.entitlements if x.status == "active")
        entitlement.expires_at = utcnow() - timedelta(days=1)
        db.commit()

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "南京大学公告更新",
            "body": "有新的招生公告",
            "summary": "测试到期回收逻辑",
            "school_name": "南京大学",
            "source_url": "https://example.com/notice-expired-school",
        },
        headers=admin_headers,
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed == 1

    pending_resp = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_resp.status_code == 200
    assert pending_resp.json()["total"] == 0

    with SessionLocal() as db:
        user = db.query(PortalUser).filter(PortalUser.username == "expired_notify_user").one()
        assert not any(x.status == "active" for x in user.entitlements)
        sub = (
            db.query(PortalUserSubscription)
            .filter(
                PortalUserSubscription.user_id == user.id,
                PortalUserSubscription.subscription_type == "school",
            )
            .one()
        )
        assert sub.status == "deleted"


def test_keyword_subscription_matches_system_tag_aliases(client):
    token = _access_token(client, username="notify_alias_user")
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "keyword", "value": "复试线", "category": "announcement"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "中山大学2026年硕士研究生招生考试复试基本分数线",
            "body": "现公布复试基本分数线及相关说明，请考生及时查看。",
            "school_name": "中山大学",
            "source_url": "https://example.com/notice-keyword-alias",
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
    assert payload["items"][0]["payload"]["title"] == "中山大学2026年硕士研究生招生考试复试基本分数线"
