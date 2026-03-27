import json
import shutil
import uuid
from pathlib import Path

from app.db import SessionLocal
from app.models import (
    Content,
    ContentClassification,
    Department,
    GovernanceAction,
    ParseArtifact,
    PortalEdge,
    PortalHostDecision,
    PortalNode,
    RawArtifact,
    School,
    SiteSection,
    WorkflowRun,
    WorkflowStep,
)
from app.services import announcement_foundation, workflow_v2
from app.services.workflow_v2 import workflow_engine


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


def _temp_dir() -> Path:
    root = Path("backend/tests/.tmp")
    root.mkdir(parents=True, exist_ok=True)
    path = root.resolve() / f"announcement-foundation-admin-{uuid.uuid4().hex}"
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_admin_bootstrap_school_enqueues_workflow_and_worker_persists_v2_graph(client, monkeypatch):
    def _fake_bootstrap(db, **kwargs):
        school = db.query(School).filter(School.name == kwargs["school_name"]).one()
        section = SiteSection(
            school_id=school.id,
            name="Admissions Notices",
            section_type="notice",
            section_url="https://seed.example.edu.cn/notices/",
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
            "seed_urls": list(kwargs["seed_urls"]),
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
            "school_name": "Workflow University",
            "homepage_url": "https://seed.example.edu.cn/",
            "seed_urls": ["https://seed.example.edu.cn/admissions/"],
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
        db.add(
            GovernanceAction(
                entity_type="workflow_run",
                entity_id="foreign-run",
                scope_type="department",
                scope_key=run.scope_key,
                action_type="bootstrap.foreign_scope",
                payload={},
            )
        )
        db.commit()

    detail_response = client.get(f"/api/v1/admin/workflows/{payload['workflow_run_id']}", headers=_admin_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["workflow_run_id"] == payload["workflow_run_id"]
    assert [item["node_type"] for item in detail_payload["portal_nodes"]] == ["homepage", "seed", "section_candidate"]
    assert [item["family"] for item in detail_payload["host_decisions"]] == ["announcement"]
    assert [item["artifact_type"] for item in detail_payload["raw_artifacts"]] == ["bootstrap_input"]
    assert [item["artifact_type"] for item in detail_payload["parse_artifacts"]] == ["section_candidates"]
    assert detail_payload["steps"][0]["step_type"] == "school_portal_discovery"
    assert [item["action_type"] for item in detail_payload["governance_actions"]] == ["bootstrap.completed"]

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == payload["step_id"]).one()
        section = db.query(SiteSection).filter(SiteSection.school.has(name="Workflow University")).one()
        nodes = db.query(PortalNode).filter(PortalNode.scope_key == run.scope_key).all()
        edges = db.query(PortalEdge).all()
        host_decision = db.query(PortalHostDecision).filter(PortalHostDecision.scope_key == run.scope_key).one()
        governance = db.query(GovernanceAction).filter(GovernanceAction.entity_id == run.id).one()
        raw_artifact = db.query(RawArtifact).filter(RawArtifact.workflow_step_id == step.id).one()
        parse_artifact = db.query(ParseArtifact).filter(ParseArtifact.workflow_step_id == step.id).one()

        assert run.status == "done"
        assert step.status == "done"
        assert section.enabled == 0
        assert sorted(node.node_type for node in nodes) == ["homepage", "section_candidate", "seed"]
        assert sorted(edge.relation_type for edge in edges) == ["explicit_seed", "section_candidate"]
        assert host_decision.selected_host == "seed.example.edu.cn"
        assert host_decision.candidate_hosts == ["seed.example.edu.cn"]
        assert governance.action_type == "bootstrap.completed"
        assert raw_artifact.artifact_type == "bootstrap_input"
        assert parse_artifact.artifact_type == "section_candidates"
        assert parse_artifact.payload["candidate_urls"] == ["https://seed.example.edu.cn/notices/"]


def test_admin_workflow_list_filters_and_detail_expose_seed_source_and_step_runtime(client, monkeypatch):
    def _fake_bootstrap(db, **kwargs):
        school = db.query(School).filter(School.name == kwargs["school_name"]).one()
        section = SiteSection(
            school_id=school.id,
            name="Admissions Notices",
            section_type="notice",
            section_url="https://seed.example.edu.cn/notices/",
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
            "seed_urls": list(kwargs["seed_urls"]),
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
            "school_name": "Workflow List University",
            "homepage_url": "https://seed.example.edu.cn/",
            "seed_urls": ["https://seed.example.edu.cn/notices/"],
            "max_sections": 8,
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    assert workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker") == 1

    list_response = client.get(
        "/api/v1/admin/workflows",
        params={
            "family": "notice",
            "scope_type": "school",
            "scope_key": "WorkflowListUniversity",
            "status": "done",
            "workflow_type": "school_portal_discovery",
            "host_key": "seed.example.edu.cn",
            "page": 1,
            "page_size": 10,
        },
        headers=_admin_headers(),
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    item = list_payload["items"][0]
    assert item["workflow_run_id"] == payload["workflow_run_id"]
    assert item["seed_source"] == "payload"
    assert item["families"] == ["admissions", "notice"]
    assert item["host_keys"] == ["seed.example.edu.cn"]
    assert item["latest_step_type"] == "school_portal_discovery"
    assert item["latest_step_status"] == "done"

    detail_response = client.get(f"/api/v1/admin/workflows/{payload['workflow_run_id']}", headers=_admin_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["seed_source"] == "payload"
    assert detail_payload["terminal_reason"] is None
    assert detail_payload["request_payload"]["homepage_url"] == "https://seed.example.edu.cn/"
    assert detail_payload["request_payload"]["seed_urls"] == [
        "https://seed.example.edu.cn/",
        "https://seed.example.edu.cn/notices/",
    ]
    assert detail_payload["steps"][0]["lease_owner"] is None
    assert detail_payload["steps"][0]["leased_at"] is None
    assert detail_payload["steps"][0]["timeout_seconds"] > 0
    assert detail_payload["steps"][0]["max_attempts"] >= 1


def test_department_bootstrap_rejects_school_scoped_sections_and_rolls_back_partial_writes(client, monkeypatch):
    def _fake_bootstrap(db, **kwargs):
        school = db.query(School).filter(School.name == kwargs["school_name"]).one()
        section = SiteSection(
            school_id=school.id,
            department_id=None,
            name="Wrong Scope Notices",
            section_type="notice",
            section_url="https://dept.example.edu.cn/notices/",
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
            "seed_urls": list(kwargs["seed_urls"]),
            "candidate_count": 1,
            "candidate_urls": [section.section_url],
            "created_sections": 1,
            "existing_sections": 0,
            "job_ids": [],
            "items": [section],
        }

    monkeypatch.setattr("app.services.workflow_v2.bootstrap_site_sections", _fake_bootstrap)

    response = client.post(
        "/api/v1/admin/bootstrap/departments",
        json={
            "school_name": "Scope University",
            "department_name": "Computer Science",
            "homepage_url": "https://dept.example.edu.cn/",
            "seed_urls": ["https://dept.example.edu.cn/admissions/"],
            "max_sections": 8,
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    processed = workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker")
    assert processed == 1

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == payload["step_id"]).one()
        department = (
            db.query(Department)
            .join(School, Department.school_id == School.id)
            .filter(School.name == "Scope University", Department.name == "Computer Science")
            .one()
        )

        assert run.status == "failed"
        assert step.status == "failed"
        assert "out-of-scope" in (run.error_message or "")
        assert db.query(SiteSection).filter(SiteSection.department_id == department.id).count() == 0
        assert db.query(PortalNode).filter(PortalNode.scope_key == run.scope_key).count() == 0
        assert db.query(PortalHostDecision).filter(PortalHostDecision.scope_key == run.scope_key).count() == 0
        assert db.query(PortalEdge).count() == 0
        assert db.query(RawArtifact).filter(RawArtifact.workflow_step_id == step.id).count() == 0
        assert db.query(ParseArtifact).filter(ParseArtifact.workflow_step_id == step.id).count() == 0
        assert db.query(GovernanceAction).filter(GovernanceAction.entity_id == run.id).count() == 0


def test_admin_scope_rebuild_uses_canonical_announcement_seed_when_payload_seed_missing(client):
    response = client.post(
        "/api/v1/admin/rebuilds",
        json={
            "scope_type": "school",
            "school_name": "湖北大学",
            "max_sections": 8,
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == payload["step_id"]).one()
        assert run.request_payload["homepage_url"] == "https://yz.hubu.edu.cn/"
        assert run.request_payload["seed_urls"] == ["https://yz.hubu.edu.cn/"]
        assert run.request_payload["seed_source"] == "canonical_registry"
        assert step.input_payload["homepage_url"] == "https://yz.hubu.edu.cn/"
        assert step.input_payload["seed_urls"] == ["https://yz.hubu.edu.cn/"]
        assert step.input_payload["seed_source"] == "canonical_registry"


def test_admin_scope_rebuild_requires_governed_seed_for_school_announcement_scope(client):
    response = client.post(
        "/api/v1/admin/rebuilds",
        json={
            "scope_type": "school",
            "school_name": "Seedless University",
            "max_sections": 8,
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "announcement school rebuild requires explicit seeds or a canonical seed registry entry"

    with SessionLocal() as db:
        assert db.query(WorkflowRun).count() == 0
        assert db.query(WorkflowStep).count() == 0


def test_admin_content_explain_returns_persisted_classification(client):
    create_response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "Explain University 2026 interview notice",
            "body": "Candidates should attend the interview on time.",
            "school_name": "Explain University",
            "source_type": "crawler",
            "source_url": "https://explain.example.edu.cn/notice/1.htm",
            "extra": {
                "portal_scope": "graduate_admissions",
                "channel_label": "Admissions Notice",
                "channel_tier": "core",
                "system_tags": ["notice"],
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
        school = School(name="Reclassify University", aliases=[])
        db.add(school)
        db.flush()
        content = Content(
            school_id=school.id,
            category="announcement",
            title="Reclassify University adjustment notice",
            body="Welcome to apply for adjustment at Reclassify University.",
            summary="Welcome to apply for adjustment at Reclassify University.",
            source_type="crawler",
            source_url="https://reclassify.example.edu.cn/notice/2.htm",
            extra={
                "school_name": "Reclassify University",
                "portal_scope": "graduate_admissions",
                "channel_label": "Adjustment Notice",
                "channel_tier": "core",
                "system_tags": ["adjustment"],
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

    detail_response = client.get(f"/api/v1/admin/workflows/{payload['workflow_run_id']}", headers=_admin_headers())
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["terminal_reason"] == "school_visible"
    assert detail_payload["content_classifications"][0]["content_id"] == content_id
    assert detail_payload["content_classifications"][0]["classification_state"] == "school_visible"


def test_admin_announcement_foundation_refresh_fans_out_school_enrich_and_merges_after_barrier(client, monkeypatch):
    tmp_path = _temp_dir()
    monkeypatch.setenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", str(tmp_path))

    def _fake_major_catalog(schools, paths):
        assert schools[0]["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
        payload = [
            {
                "major_code": "081201",
                "major_name": "Computer Systems Architecture",
                "degree_type": "master",
                "discipline_code": "08",
                "discipline_name": "Engineering",
                "school_refs": [{"school_code": "1001", "school_name": "Example University"}],
                "department_refs": [],
                "source_meta": {},
            }
        ]
        paths.major_catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _fake_official_rosters(paths):
        payload = [
            {
                "school_name": "Example University",
                "homepage_url": "https://yz.example.edu.cn/",
                "seed_urls": ["https://yz.example.edu.cn/"],
                "source_type": "official_roster",
                "confidence": "high",
                "source_meta": {"source_label": "fixture"},
            }
        ]
        paths.official_seed_candidates.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _fake_homepages(paths):
        payload = [{"school_name": "Example University", "official_homepage": "https://www.example.edu.cn/", "source_meta": {}}]
        paths.school_homepages.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _fake_department_candidates(schools, paths):
        assert schools[0]["source_meta"]["department_page_url"] == "https://example.edu.cn/departments/"
        departments = [
            {
                "school_code": "1001",
                "school_name": "Example University",
                "department_code": "dept1",
                "department_name": "School of Computing",
                "aliases": [],
                "major_count": 0,
                "source_meta": {},
            }
        ]
        candidates = [
            {
                "scope_type": "department",
                "school_name": "Example University",
                "department_name": "School of Computing",
                "homepage_url": "https://yz.example.edu.cn/cs/",
                "seed_urls": ["https://yz.example.edu.cn/cs/"],
                "source_type": "department_candidate",
                "confidence": "medium",
                "review_status": "pending",
                "notes": "fixture",
            }
        ]
        paths.department_catalog.write_text(json.dumps(departments, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.department_candidates.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
        return departments, candidates

    def _fake_merge(*, paths, dry_run):
        diff_payload = {
            "added": ["school|ExampleUniversity|"],
            "removed": [],
            "updated": [],
            "department_candidate_count": 1,
            "promoted_count": 0,
            "school_count": 1,
        }
        paths.seed_diff.write_text(json.dumps(diff_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return diff_payload

    monkeypatch.setattr(
        "app.services.announcement_foundation.fetch_chsi_school_catalog",
        lambda school_names=None: [
            {
                "school_code": "1001",
                "school_name": "Example University",
                "aliases": [],
                "province": "Beijing",
                "official_homepage": None,
                "chsi_school_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001.dhtml",
                "source_meta": {"source_type": "chsi_school_catalog"},
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.announcement_foundation.enrich_chsi_school_entry",
        lambda school: {
            **school,
            "source_meta": {
                **dict(school.get("source_meta") or {}),
                "seed_hint_urls": ["https://yz.example.edu.cn/"],
                "department_page_url": "https://example.edu.cn/departments/",
                "major_page_url": "https://example.edu.cn/majors/",
            },
        },
    )
    monkeypatch.setattr("app.services.announcement_foundation.fetch_chsi_major_catalog", _fake_major_catalog)
    monkeypatch.setattr("app.services.announcement_foundation.fetch_official_seed_rosters", _fake_official_rosters)
    monkeypatch.setattr("app.services.announcement_foundation.fetch_school_homepages", _fake_homepages)
    monkeypatch.setattr("app.services.announcement_foundation.build_department_candidates", _fake_department_candidates)
    monkeypatch.setattr("app.services.announcement_foundation.merge_announcement_seed_registry", _fake_merge)

    response = client.post(
        "/api/v1/admin/catalog-refreshes/announcement-foundation",
        json={
            "school_names": ["Example University"],
            "dry_run": True,
            "sources": ["chsi", "official_rosters", "school_homepages"],
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_type"] == "announcement_catalog_refresh"

    for _ in range(12):
        processed = workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker")
        with SessionLocal() as db:
            pending_barriers = (
                db.query(WorkflowStep)
                .filter(
                    WorkflowStep.run_id == payload["workflow_run_id"],
                    WorkflowStep.step_type == "await_chsi_school_enrich",
                    WorkflowStep.status == "pending",
                )
                .all()
            )
            for barrier in pending_barriers:
                barrier.available_at = workflow_v2.utcnow()
            db.commit()
            run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
            if run.status in {"done", "failed"}:
                break
        if processed == 0 and not pending_barriers:
            break

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == payload["workflow_run_id"]).one()
        steps = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.run_id == run.id)
            .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
            .all()
        )
        assert run.status == "done"
        assert [step.step_type for step in steps] == [
            "fetch_chsi_school_catalog",
            "enqueue_chsi_school_enrich",
            "enrich_chsi_school_snapshot",
            "await_chsi_school_enrich",
            "fetch_chsi_major_catalog",
            "fetch_official_seed_rosters",
            "fetch_school_homepages",
            "build_department_candidates",
            "merge_announcement_seed_registry",
        ]
        school_snapshot = json.loads((tmp_path / announcement_foundation.SCHOOL_CATALOG_FILENAME).read_text(encoding="utf-8"))
        assert school_snapshot[0]["school_name"] == "Example University"
        assert school_snapshot[0]["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
        assert run.result_payload["registry_diff"]["added"] == ["school|ExampleUniversity|"]

    shutil.rmtree(tmp_path, ignore_errors=True)
