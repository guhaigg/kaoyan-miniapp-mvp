from __future__ import annotations

import pytest
from sqlalchemy import inspect

from app import models as app_models
from app.config import get_settings
from app.db import SessionLocal
from app.models import Department, NotificationDelivery, NotificationOutbox, School, SiteSection
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


def _ensure_scope_assets(
    *,
    school_name: str,
    department_name: str | None = None,
    site_section_name: str | None = None,
) -> tuple[str, str | None, str | None]:
    with SessionLocal() as db:
        school = db.query(School).filter(School.name == school_name).one_or_none()
        if school is None:
            school = School(name=school_name, aliases=[])
            db.add(school)
            db.flush()

        department_id: str | None = None
        if department_name:
            department = (
                db.query(Department)
                .filter(Department.school_id == school.id, Department.name == department_name)
                .one_or_none()
            )
            if department is None:
                department = Department(
                    school_id=school.id,
                    name=department_name,
                    aliases=[],
                    department_type="college",
                    enabled=1,
                )
                db.add(department)
                db.flush()
            department_id = department.id

        section_id: str | None = None
        if site_section_name:
            section = (
                db.query(SiteSection)
                .filter(
                    SiteSection.school_id == school.id,
                    SiteSection.department_id == department_id,
                    SiteSection.name == site_section_name,
                )
                .one_or_none()
            )
            if section is None:
                section = SiteSection(
                    school_id=school.id,
                    department_id=department_id,
                    name=site_section_name,
                    section_type="notice",
                    section_url=f"https://example.com/{school.id}/{department_id or 'none'}/section",
                    discovery_category="announcement",
                    enabled=1,
                    list_selector_config={},
                )
                db.add(section)
                db.flush()
            section_id = section.id

        db.commit()
        return school.id, department_id, section_id


def _create_monitor_target_and_keyword(
    user_id: str,
    *,
    school_name: str,
    keyword: str | None = None,
    scope_type: str = "school",
    department_name: str | None = None,
    site_section_name: str | None = None,
) -> str:
    school_id, department_id, section_id = _ensure_scope_assets(
        school_name=school_name,
        department_name=department_name,
        site_section_name=site_section_name,
    )
    with SessionLocal() as db:
        target_cols = _column_names(TARGET_MODEL)
        target_payload = {
            "user_id": user_id,
            "school_id": school_id,
            "department_id": department_id,
            "site_section_id": section_id,
            "scope_type": scope_type,
            "status": "active",
            "check_interval_minutes": 60,
        }
        target = TARGET_MODEL(**{k: v for k, v in target_payload.items() if k in target_cols})
        db.add(target)
        db.flush()

        if keyword:
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


def test_monitor_hit_matches_alias_keyword_via_system_tags(client):
    user_id, _token = _register_user_and_token(client, "pmhit_alias")
    _create_monitor_target_and_keyword(user_id, school_name="中山大学", keyword="复试线")

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "中山大学2026年硕士研究生招生考试复试基本分数线",
            "body": "现公布复试基本分数线及相关说明，请考生及时查看。",
            "school_name": "中山大学",
            "source_url": "https://example.com/pm-hit-alias",
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).filter(HIT_MODEL.user_id == user_id).all()
        assert len(hits) == 1
        assert "复试线" in (hits[0].matched_keywords or [])


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


def test_scope_only_school_target_generates_hit_without_keywords(client):
    user_id, _token = _register_user_and_token(client, "pmhit_scope_only")
    target_id = _create_monitor_target_and_keyword(user_id, school_name="厦门大学", keyword=None)

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "厦门大学最新公告",
            "body": "这里是最新招生公告正文",
            "school_name": "厦门大学",
            "source_url": "https://example.com/pm-hit-scope-only",
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200
    content_id = ingest_resp.json()["id"]

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).filter(HIT_MODEL.user_id == user_id).all()
        assert len(hits) == 1
        assert str(hits[0].content_id) == content_id
        assert str(hits[0].monitor_target_id) == target_id
        assert hits[0].matched_keywords == []
        assert hits[0].match_score == 1
        assert hits[0].hit_reason == "scope_match:school"

        outboxes = _monitor_outboxes_for_user(db, user_id=user_id)
        assert len(outboxes) == 1
        payload = dict(outboxes[0].payload or {})
        assert payload["target_id"] == target_id
        assert payload["matched_keywords"] == []
        assert payload["scope_type"] == "school"


def test_scope_only_section_target_matches_site_section_id(client):
    user_id, _token = _register_user_and_token(client, "pmhit_section_scope")
    _create_monitor_target_and_keyword(
        user_id,
        school_name="华南理工大学",
        department_name="材料学院",
        site_section_name="材料学院通知公告",
        scope_type="section",
        keyword=None,
    )
    _school_id, _department_id, section_id = _ensure_scope_assets(
        school_name="华南理工大学",
        department_name="材料学院",
        site_section_name="材料学院通知公告",
    )

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "材料学院招生公告",
            "body": "栏目级命中测试",
            "school_name": "华南理工大学",
            "source_url": "https://example.com/pm-hit-section-scope",
            "extra": {
                "department_name": "材料学院",
                "site_section_id": section_id,
                "site_section_name": "材料学院通知公告",
            },
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).filter(HIT_MODEL.user_id == user_id).all()
        assert len(hits) == 1
        assert str(hits[0].site_section_id or "") == section_id
        assert hits[0].hit_reason == "scope_match:section"

        outboxes = _monitor_outboxes_for_user(db, user_id=user_id)
        assert len(outboxes) == 1
        payload = dict(outboxes[0].payload or {})
        assert payload["site_section_id"] == section_id
        assert payload["site_section_name"] == "材料学院通知公告"
        assert payload["department_name"] == "材料学院"


def test_manual_content_resolves_department_name_to_department_id_for_scope_match(client):
    user_id, _token = _register_user_and_token(client, "pmhit_manual_department_scope")
    target_id = _create_monitor_target_and_keyword(
        user_id,
        school_name="苏州大学",
        department_name="计算机科学与技术学院",
        scope_type="department",
        keyword=None,
    )
    school_id, department_id, _section_id = _ensure_scope_assets(
        school_name="苏州大学",
        department_name="计算机科学与技术学院",
    )

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "苏州大学计算机学院通知",
            "body": "这是手工录入的学院公告",
            "school_name": "苏州大学",
            "source_type": "manual",
            "source_url": "https://example.com/manual-department-scope",
            "extra": {
                "department_name": "计算机科学与技术学院",
            },
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200
    content_id = ingest_resp.json()["id"]

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).filter(HIT_MODEL.user_id == user_id).all()
        assert len(hits) == 1
        assert str(hits[0].monitor_target_id) == target_id
        assert str(hits[0].content_id) == content_id
        assert hits[0].hit_reason == "scope_match:department"

        content = db.query(app_models.Content).filter(app_models.Content.id == content_id).one()
        extra = dict(content.extra or {})
        assert str(content.school_id or "") == school_id
        assert str(extra.get("school_id") or "") == school_id
        assert str(extra.get("department_id") or "") == department_id
        assert extra.get("department_name") == "计算机科学与技术学院"


def test_manual_content_resolves_site_section_name_to_site_section_id_for_scope_match(client):
    user_id, _token = _register_user_and_token(client, "pmhit_manual_section_scope")
    _create_monitor_target_and_keyword(
        user_id,
        school_name="云南大学",
        department_name="信息学院",
        site_section_name="信息学院通知公告",
        scope_type="section",
        keyword=None,
    )
    school_id, department_id, section_id = _ensure_scope_assets(
        school_name="云南大学",
        department_name="信息学院",
        site_section_name="信息学院通知公告",
    )

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "云南大学信息学院手工公告",
            "body": "这是手工录入的栏目公告",
            "school_name": "云南大学",
            "source_type": "manual",
            "source_url": "https://example.com/manual-section-scope",
            "extra": {
                "department_name": "信息学院",
                "site_section_name": "信息学院通知公告",
            },
        },
        headers=_admin_headers(),
    )
    assert ingest_resp.status_code == 200
    content_id = ingest_resp.json()["id"]

    with SessionLocal() as db:
        hits = db.query(HIT_MODEL).filter(HIT_MODEL.user_id == user_id).all()
        assert len(hits) == 1
        assert str(hits[0].content_id) == content_id
        assert str(hits[0].site_section_id or "") == section_id
        assert hits[0].hit_reason == "scope_match:section"

        content = db.query(app_models.Content).filter(app_models.Content.id == content_id).one()
        extra = dict(content.extra or {})
        assert str(content.school_id or "") == school_id
        assert str(extra.get("department_id") or "") == department_id
        assert str(extra.get("site_section_id") or "") == section_id
        assert extra.get("site_section_name") == "信息学院通知公告"
