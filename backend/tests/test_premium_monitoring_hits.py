from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app import models as app_models
from app.config import get_settings
from app.db import SessionLocal
from app.models import NotificationDelivery, NotificationOutbox, School
from app.services.notifications import notification_engine

TARGET_MODEL = getattr(app_models, "PortalUserMonitorTarget", None)
KEYWORD_MODEL = getattr(app_models, "PortalUserMonitorKeyword", None)
HIT_MODEL = getattr(app_models, "PortalUserMonitorHit", None)

pytestmark = pytest.mark.skipif(
    TARGET_MODEL is None or KEYWORD_MODEL is None or HIT_MODEL is None,
    reason="premium monitoring models are not available in this branch",
)


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


def _register_user_and_token(client, username: str) -> tuple[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": f"{username}-nick"},
    )
    assert register.status_code == 200
    user_id = register.json()["user_id"]
    login = client.post("/api/v1/auth/login", json={"username": username, "password": "StrongPass123"})
    assert login.status_code == 200
    return user_id, login.json()["access_token"]


def _column_names(model) -> set[str]:
    return {col.key for col in inspect(model).mapper.column_attrs}


def _create_monitor_target_and_keyword(
    user_id: str,
    *,
    school_name: str,
    keyword: str,
) -> str:
    with SessionLocal() as db:
        school = db.query(School).filter(School.name == school_name).one_or_none()
        if school is None:
            school = School(name=school_name, aliases=[])
            db.add(school)
            db.flush()

        target_cols = _column_names(TARGET_MODEL)
        target_payload = {
            "user_id": user_id,
            "school_id": school.id,
            "scope_type": "school",
            "status": "active",
            "check_interval_minutes": 60,
        }
        target = TARGET_MODEL(**{k: v for k, v in target_payload.items() if k in target_cols})
        db.add(target)
        db.flush()

        keyword_cols = _column_names(KEYWORD_MODEL)
        keyword_payload = {
            "user_id": user_id,
            "monitor_target_id": target.id,
            "target_id": target.id,
            "keyword": keyword,
            "value": keyword,
            "match_mode": "contains",
            "weight": 1,
            "status": "active",
        }
        keyword_row = KEYWORD_MODEL(**{k: v for k, v in keyword_payload.items() if k in keyword_cols})
        db.add(keyword_row)
        db.commit()
        return target.id


def _monitor_outboxes_for_user(db, *, user_id: str) -> list[NotificationOutbox]:
    rows = db.query(NotificationOutbox).filter(NotificationOutbox.event_type == "monitor.hit").all()
    return [row for row in rows if str((row.payload or {}).get("user_id") or "") == user_id]


def test_created_content_creates_hit_and_monitor_outbox(client):
    user_id, _ = _register_user_and_token(client, "pmhit_created")
    target_id = _create_monitor_target_and_keyword(user_id, school_name="电子科技大学", keyword="调剂")

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "电子科技大学调剂通知",
            "body": "2026 年硕士调剂公告发布",
            "summary": "调剂系统开放",
            "school_name": "电子科技大学",
            "source_url": "https://example.com/pm-hit-1",
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200
    content_id = ingest_resp.json()["id"]

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).all()
        assert len(hits) == 1
        hit = hits[0]
        assert str(getattr(hit, "user_id", "")) == user_id
        assert str(getattr(hit, "content_id", "")) == content_id
        hit_target_id = getattr(hit, "monitor_target_id", None)
        if hit_target_id is None:
            hit_target_id = getattr(hit, "target_id", None)
        assert str(hit_target_id or "") == target_id

        outboxes = _monitor_outboxes_for_user(db, user_id=user_id)
        assert len(outboxes) == 1
        payload = dict(outboxes[0].payload or {})
        assert payload["content_id"] == content_id
        assert payload["user_id"] == user_id
        assert payload["target_id"] == target_id
        assert "调剂" in payload["matched_keywords"]


def test_updated_content_does_not_duplicate_hit_or_monitor_outbox(client):
    user_id, _ = _register_user_and_token(client, "pmhit_update")
    _create_monitor_target_and_keyword(user_id, school_name="北京大学", keyword="通知")

    first_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "北京大学通知",
            "body": "第一版通知内容",
            "school_name": "北京大学",
            "source_url": "https://example.com/pm-hit-2",
        },
        headers=_admin_headers(),
    )
    assert first_resp.status_code == 200
    assert first_resp.json()["status"] == "created"

    second_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "北京大学通知",
            "body": "第二版通知内容（updated）",
            "school_name": "北京大学",
            "source_url": "https://example.com/pm-hit-2",
        },
        headers=_admin_headers(),
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["status"] == "updated"

    with SessionLocal() as db:
        assert db.query(HIT_MODEL).count() == 1
        assert len(_monitor_outboxes_for_user(db, user_id=user_id)) == 1


def test_monitor_hit_generates_inapp_delivery_without_subscription(client):
    user_id, token = _register_user_and_token(client, "pmhit_inapp")
    _create_monitor_target_and_keyword(user_id, school_name="浙江大学", keyword="复试")

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "浙江大学复试安排",
            "body": "复试时间已发布",
            "school_name": "浙江大学",
            "source_url": "https://example.com/pm-hit-3",
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed >= 1

    pending = client.get("/api/v1/notifications/pending", headers={"X-User-Token": token})
    assert pending.status_code == 200
    payload = pending.json()
    assert payload["total"] == 1
    assert payload["items"][0]["payload"]["source_url"] == "https://example.com/pm-hit-3"


def test_monitor_hit_generates_bark_delivery_when_enabled(client):
    user_id, token = _register_user_and_token(client, "pmhit_bark")
    _create_monitor_target_and_keyword(user_id, school_name="同济大学", keyword="公告")

    settings = get_settings()
    settings.enable_bark_notifications = True
    settings.bark_server_url = "https://bark.example.com"
    settings.notification_batch_window_seconds = 0

    bark_resp = client.put(
        "/api/v1/auth/me/notifications/bark",
        json={"enabled": True, "bark_key": "bark-key-abc"},
        headers={"X-User-Token": token},
    )
    assert bark_resp.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "同济大学公告",
            "body": "这是新的公告内容",
            "school_name": "同济大学",
            "source_url": "https://example.com/pm-hit-4",
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed >= 1

    with SessionLocal() as db:
        bark_rows = (
            db.query(NotificationDelivery)
            .filter(NotificationDelivery.user_id == user_id, NotificationDelivery.channel == "bark")
            .all()
        )
        assert len(bark_rows) == 1
        assert bark_rows[0].status == "pending"
