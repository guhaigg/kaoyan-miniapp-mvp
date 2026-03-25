from app.db import SessionLocal
from app.models import Content, ContentClassification, School, SiteSection, WorkflowRun, WorkflowStep
from app.services.workflow_v2 import workflow_engine


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


def test_admin_bootstrap_school_enqueues_workflow_and_worker_creates_recommended_sections(client, monkeypatch):
    def _fake_bootstrap(db, **kwargs):
        school = db.query(School).filter(School.name == kwargs["school_name"]).one()
        section = SiteSection(
            school_id=school.id,
            name="通知公告",
            section_type="notice",
            section_url="https://seed.example.edu.cn/tzgg/",
            discovery_category="announcement",
            enabled=0,
            list_selector_config={},
            detail_selector_config={},
        )
        db.add(section)
        db.flush()
        return {
            "school": school,
            "homepage_url": kwargs["homepage_url"],
            "seed_urls": [kwargs["homepage_url"]],
            "candidate_count": 1,
            "candidate_urls": [section.section_url],
            "created_sections": 1,
            "existing_sections": 0,
            "job_ids": [],
            "items": [section],
        }

    monkeypatch.setattr("app.services.workflow_v2.bootstrap_site_sections", _fake_bootstrap)

    response = client.post(
        "/api/v1/admin/bootstrap/schools",
        json={
            "school_name": "工作流大学",
            "homepage_url": "https://seed.example.edu.cn/",
            "seed_urls": [],
            "max_sections": 8,
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_type"] == "school_portal_discovery"

    processed = workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker")
    assert processed == 1

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == payload["step_id"]).one()
        section = db.query(SiteSection).filter(SiteSection.school.has(name="工作流大学")).one()
        assert run.status == "done"
        assert step.status == "done"
        assert section.enabled == 0


def test_admin_content_explain_returns_persisted_classification(client):
    create_response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "说明大学2026年硕士研究生复试通知",
            "body": "请考生按时参加复试。",
            "school_name": "说明大学",
            "source_type": "crawler",
            "source_url": "https://explain.example.edu.cn/notice/1.htm",
            "extra": {
                "portal_scope": "graduate_admissions",
                "channel_label": "通知公告",
                "channel_tier": "core",
                "system_tags": ["通知公告"],
            },
        },
        headers=_admin_headers(),
    )
    assert create_response.status_code == 200
    content_id = create_response.json()["id"]

    explain_response = client.get(f"/api/v1/admin/contents/{content_id}/explain", headers=_admin_headers())
    assert explain_response.status_code == 200
    payload = explain_response.json()
    assert payload["content_id"] == content_id
    assert payload["classification_state"] == "school_visible"
    assert payload["scope_type"] == "school"


def test_admin_content_reclassify_queues_workflow_step(client):
    with SessionLocal() as db:
        school = School(name="重分类大学", aliases=[])
        db.add(school)
        db.flush()
        content = Content(
            school_id=school.id,
            category="announcement",
            title="重分类大学2026年调剂公告",
            body="欢迎报考重分类大学。",
            summary="欢迎报考重分类大学。",
            source_type="crawler",
            source_url="https://reclassify.example.edu.cn/notice/2.htm",
            extra={
                "school_name": "重分类大学",
                "portal_scope": "graduate_admissions",
                "channel_label": "调剂公告",
                "channel_tier": "core",
                "system_tags": ["调剂公告"],
            },
        )
        db.add(content)
        db.commit()
        content_id = content.id

    response = client.post(f"/api/v1/admin/contents/{content_id}/reclassify", headers=_admin_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_type"] == "content_reclassify"

    processed = workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker")
    assert processed == 1

    with SessionLocal() as db:
        row = db.query(ContentClassification).filter(ContentClassification.content_id == content_id).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == payload["step_id"]).one()
        assert row.classification_state == "school_visible"
        assert step.status == "done"
