# CHSI Foundation Enrich Fanout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `announcement_catalog_refresh` so CHSI school-catalog fetch, per-school enrich, and downstream major/department/merge stages are separate workflow stages with strict barrier semantics.

**Architecture:** Keep a single `announcement_catalog_refresh` run. `fetch_chsi_school_catalog` records the base CHSI catalog as a workflow parse artifact, `enqueue_chsi_school_enrich` fans out one `enrich_chsi_school_snapshot` child step per school, and `await_chsi_school_enrich` waits until every child step is terminal before writing the final `school_catalog_snapshot.json` and queueing `fetch_chsi_major_catalog`. Add explicit deferred-step control flow so the barrier can poll progress without being marked failed, and persist failure summaries in the barrier result payload when any child step fails.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, httpx, lxml, JSON foundation artifacts, systemd deployment.

---

## File Map

- Modify `backend/app/services/announcement_foundation.py`
  - Add single-school CHSI enrich helper and final merge helper.
  - Keep `refresh_announcement_foundation()` working by composing the new helpers sequentially.
- Modify `backend/app/services/workflow_v2.py`
  - Add CHSI fanout step constants, payload model, artifact constants, child-step idempotency, deferred-step handling, and the new fetch/enqueue/enrich/await processors.
- Create `backend/tests/test_workflow_v2.py`
  - Add focused tests for child-step dedupe, deferred barrier behavior, and terminal barrier failure summaries.
- Modify `backend/tests/test_announcement_foundation.py`
  - Add unit tests for single-school enrich and final merge behavior.
- Modify `backend/tests/test_crawler_v2_admin.py`
  - Replace the old six-step announcement refresh expectation with the new fanout/barrier chain.
- Modify `docs/backend_and_crawler.md`
  - Document the CHSI fanout/barrier flow and the rule that only the barrier writes `school_catalog_snapshot.json`.
- Optionally modify `docs/handoff_announcement_portal_visibility_2026-03-25.md`
  - Only if rollout or ops expectations changed enough that the current handoff would mislead the next operator.

### Task 1: Split CHSI Foundation Helpers

**Files:**
- Modify: `backend/app/services/announcement_foundation.py`
- Test: `backend/tests/test_announcement_foundation.py`

- [ ] **Step 1: Add the failing unit tests first**

```python
def test_enrich_chsi_school_entry_extracts_seed_and_category_urls(monkeypatch):
    school = {
        "school_code": "1001",
        "school_name": "Example University",
        "chsi_school_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001.dhtml",
        "source_meta": {"source_type": "chsi_school_catalog"},
    }
    detail_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001,categoryId-481347.dhtml">闄㈢郴璁剧疆</a>
      <a href="/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml">涓撲笟浠嬬粛</a>
      <a href="/sch/viewBulletin--infoId-5001,categoryId-481379,schId-1001,mindex-12.dhtml">Example admissions</a>
    </body></html>
    """
    bulletin_html = '<html><body><a href="https://yz.example.edu.cn/">graduate admissions</a></body></html>'
    monkeypatch.setattr(
        announcement_foundation,
        "_fetch_text",
        lambda url, timeout=20: detail_html if "schoolInfo" in url else bulletin_html,
    )

    enriched = announcement_foundation.enrich_chsi_school_entry(school)

    assert enriched["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
    assert enriched["source_meta"]["department_page_url"].endswith("categoryId-481347.dhtml")
    assert enriched["source_meta"]["major_page_url"].endswith("categoryId-692157514.dhtml")


def test_merge_chsi_school_catalog_writes_final_snapshot(tmp_path):
    paths = announcement_foundation.foundation_paths(tmp_path)
    merged = announcement_foundation.merge_chsi_school_catalog(
        [
            {
                "school_code": "1001",
                "school_name": "Example University",
                "source_meta": {"source_type": "chsi_school_catalog"},
            }
        ],
        [
            {
                "school_code": "1001",
                "school_name": "Example University",
                "source_meta": {
                    "seed_hint_urls": ["https://yz.example.edu.cn/"],
                    "department_page_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001,categoryId-481347.dhtml",
                    "major_page_url": "https://yz.chsi.com.cn/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml",
                },
            }
        ],
        paths=paths,
    )

    assert merged[0]["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
    assert json.loads(paths.school_catalog.read_text(encoding="utf-8"))[0]["school_code"] == "1001"
```

- [ ] **Step 2: Run the focused unit tests and confirm the missing-helper failure**

Run: `pytest backend/tests/test_announcement_foundation.py::test_enrich_chsi_school_entry_extracts_seed_and_category_urls backend/tests/test_announcement_foundation.py::test_merge_chsi_school_catalog_writes_final_snapshot -q`

Expected: failure because `enrich_chsi_school_entry` and `merge_chsi_school_catalog` do not exist yet.

- [ ] **Step 3: Implement the single-school enrich helper**

```python
def enrich_chsi_school_entry(school: dict[str, Any]) -> dict[str, Any]:
    detail_url = str(school.get("chsi_school_url") or "").strip()
    if not detail_url:
        return dict(school)
    detail_text = _fetch_text(detail_url)
    detail_doc = html.fromstring(detail_text)
    source_meta = dict(school.get("source_meta") or {})
    source_meta["seed_hint_urls"] = _extract_seed_hint_urls(detail_doc, detail_url)
    source_meta["department_page_url"] = _category_page_url(detail_doc, detail_url, "闄㈢郴璁剧疆")
    source_meta["major_page_url"] = _category_page_url(detail_doc, detail_url, "涓撲笟浠嬬粛")
    return {**dict(school), "source_meta": source_meta}
```

- [ ] **Step 4: Implement the final merge helper and reuse it from the legacy one-shot refresh helper**

```python
def merge_chsi_school_catalog(
    base_schools: list[dict[str, Any]],
    enrich_rows: list[dict[str, Any]],
    *,
    paths: FoundationPaths,
) -> list[dict[str, Any]]:
    enrich_by_code = {
        str(item.get("school_code") or "").strip(): dict(item)
        for item in enrich_rows
        if str(item.get("school_code") or "").strip()
    }
    merged: list[dict[str, Any]] = []
    for school in base_schools:
        school_code = str(school.get("school_code") or "").strip()
        enriched = enrich_by_code.get(school_code, {})
        merged.append(
            {
                **dict(school),
                **{key: value for key, value in enriched.items() if key != "source_meta"},
                "source_meta": {**dict(school.get("source_meta") or {}), **dict(enriched.get("source_meta") or {})},
            }
        )
    _write_json(paths.school_catalog, merged)
    return merged


def refresh_announcement_foundation(*, base_dir=None, school_names=None, dry_run=False, sources=None) -> dict[str, Any]:
    paths = foundation_paths(base_dir)
    schools = fetch_chsi_school_catalog(school_names=school_names)
    enrich_rows = [enrich_chsi_school_entry(school) for school in schools]
    schools = merge_chsi_school_catalog(schools, enrich_rows, paths=paths)
    majors = fetch_chsi_major_catalog(schools, paths=paths)
    official_rows = fetch_official_seed_rosters(paths=paths)
    homepage_rows = fetch_school_homepages(paths=paths)
    departments, candidates = build_department_candidates(schools, paths=paths)
    diff_payload = merge_announcement_seed_registry(paths=paths, dry_run=dry_run)
    return {
        "school_count": len(schools),
        "department_count": len(departments),
        "major_count": len(majors),
        "official_seed_candidate_count": len(official_rows),
        "homepage_count": len(homepage_rows),
        "department_candidate_count": len(candidates),
        "registry_diff": diff_payload,
        "base_dir": str(paths.base_dir),
        "dry_run": dry_run,
    }
```

- [ ] **Step 5: Re-run the foundation tests and commit**

Run: `pytest backend/tests/test_announcement_foundation.py -q`

Expected: `passed`.

```bash
git add backend/app/services/announcement_foundation.py backend/tests/test_announcement_foundation.py
git commit -m "refactor: split chsi school enrich helpers"
```

### Task 2: Add Workflow Fanout Primitives

**Files:**
- Modify: `backend/app/services/workflow_v2.py`
- Create: `backend/tests/test_workflow_v2.py`

- [ ] **Step 1: Add failing tests for idempotent siblings and deferred barriers**

```python
from app.db import SessionLocal
from app.services import workflow_v2


def test_create_idempotent_child_step_allows_multiple_school_enrich_siblings():
    with SessionLocal() as db:
        run, parent = workflow_v2.create_announcement_catalog_refresh_run(
            db,
            actor_username="tester",
            school_names=["One", "Two"],
            dry_run=True,
            sources=["chsi"],
        )
        first = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={"school_code": "1001", "school_name": "One", "chsi_school_url": "https://yz.chsi.com.cn/sch/1"},
        )
        second = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={"school_code": "1002", "school_name": "Two", "chsi_school_url": "https://yz.chsi.com.cn/sch/2"},
        )
        db.commit()

        assert first.id != second.id


def test_mark_step_deferred_keeps_progress_payload_visible():
    with SessionLocal() as db:
        run, parent = workflow_v2.create_announcement_catalog_refresh_run(
            db,
            actor_username="tester",
            school_names=["One"],
            dry_run=True,
            sources=["chsi"],
        )
        step = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
            host_key=None,
            input_payload={"school_names": ["One"], "dry_run": True, "sources": ["chsi"]},
        )
        db.commit()
        workflow_v2._mark_step_deferred(
            db,
            step,
            result_payload={"pending_school_count": 1, "succeeded_school_count": 0},
            delay_seconds=15,
        )
        db.refresh(step)

        assert step.status == "pending"
        assert step.result_payload["pending_school_count"] == 1
        assert step.error_message is None
```

- [ ] **Step 2: Run the new workflow-unit file and confirm the missing-helper failure**

Run: `pytest backend/tests/test_workflow_v2.py -q`

Expected: failure because the new CHSI fanout helpers do not exist yet.

- [ ] **Step 3: Add the new step constants, payload model, artifact constants, and fanout-safe child creation**

```python
STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH = "enqueue_chsi_school_enrich"
STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT = "enrich_chsi_school_snapshot"
STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH = "await_chsi_school_enrich"
PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE = "chsi_school_catalog_base"
PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH = "chsi_school_enrich"


class ChsiSchoolEnrichPayload(WorkflowPayloadModel):
    school_code: str
    school_name: str
    chsi_school_url: str


def _create_idempotent_child_step(db: Session, *, run: WorkflowRun, parent_step: WorkflowStep, step_type: str, host_key: str | None, input_payload: dict[str, Any]) -> WorkflowStep:
    idempotency_key = _step_idempotency_key(
        step_type=step_type,
        scope_key=parent_step.scope_key,
        host_key=host_key,
        input_payload=input_payload,
    )
    existing = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.run_id == run.id,
            WorkflowStep.parent_step_id == parent_step.id,
            WorkflowStep.step_type == step_type,
            WorkflowStep.idempotency_key == idempotency_key,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing
    policy = _step_policy(step_type)
    child = WorkflowStep(
        run_id=run.id,
        parent_step_id=parent_step.id,
        step_type=step_type,
        scope_type=parent_step.scope_type,
        scope_key=parent_step.scope_key,
        host_key=host_key,
        status="pending",
        max_attempts=policy.max_attempts,
        timeout_seconds=policy.timeout_seconds,
        available_at=utcnow(),
        input_payload=input_payload,
        result_payload={},
        idempotency_key=idempotency_key,
    )
    db.add(child)
    db.flush()
    return child
```

- [ ] **Step 4: Add explicit deferred-step and terminal-failure control flow**

```python
class DeferredStep(RuntimeError):
    def __init__(self, *, result_payload: dict[str, Any], delay_seconds: int = 15):
        super().__init__("workflow step deferred")
        self.result_payload = result_payload
        self.delay_seconds = delay_seconds


class TerminalStepFailure(RuntimeError):
    def __init__(self, *, message: str, result_payload: dict[str, Any]):
        super().__init__(message)
        self.result_payload = result_payload


def _mark_step_deferred(db: Session, step: WorkflowStep, *, result_payload: dict[str, Any], delay_seconds: int) -> None:
    step.status = "pending"
    step.result_payload = result_payload
    step.available_at = utcnow() + timedelta(seconds=max(1, delay_seconds))
    step.finished_at = None
    step.error_type = None
    step.error_message = None
    step.lease_owner = None
    step.leased_at = None
    _refresh_run_status(db, step.run_id)
    db.commit()
```

- [ ] **Step 5: Teach the engine loop to catch deferred and terminal-failure outcomes, then commit**

```python
try:
    result = _dispatch_workflow_step(db, step)
    _mark_step_done(db, step, result)
except DeferredStep as exc:
    db.rollback()
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one()
    _mark_step_deferred(db, step, result_payload=exc.result_payload, delay_seconds=exc.delay_seconds)
except TerminalStepFailure as exc:
    db.rollback()
    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one()
    _mark_step_failed(db, step, exc, result_payload=exc.result_payload)
```

Run: `pytest backend/tests/test_workflow_v2.py -q`

Expected: `passed`.

```bash
git add backend/app/services/workflow_v2.py backend/tests/test_workflow_v2.py
git commit -m "feat: add workflow fanout primitives for chsi enrich"
```

### Task 3: Wire the CHSI Fetch -> Enqueue -> Enrich -> Await Chain

**Files:**
- Modify: `backend/app/services/workflow_v2.py`
- Modify: `backend/tests/test_crawler_v2_admin.py`

- [ ] **Step 1: Rewrite the admin refresh regression to expect the new chain**

```python
def test_admin_announcement_foundation_refresh_fans_out_school_enrich_and_merges_after_barrier(client, monkeypatch):
    tmp_path = _temp_dir()
    monkeypatch.setenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", str(tmp_path))
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
                **school["source_meta"],
                "seed_hint_urls": ["https://yz.example.edu.cn/"],
                "department_page_url": "https://example.edu.cn/departments/",
                "major_page_url": "https://example.edu.cn/majors/",
            },
        },
    )
    monkeypatch.setattr("app.services.announcement_foundation.fetch_chsi_major_catalog", lambda schools, paths: [])
    monkeypatch.setattr("app.services.announcement_foundation.fetch_official_seed_rosters", lambda paths: [])
    monkeypatch.setattr("app.services.announcement_foundation.fetch_school_homepages", lambda paths: [])
    monkeypatch.setattr("app.services.announcement_foundation.build_department_candidates", lambda schools, paths: ([], []))
    monkeypatch.setattr(
        "app.services.announcement_foundation.merge_announcement_seed_registry",
        lambda *, paths, dry_run: {
            "added": ["school|ExampleUniversity|"],
            "removed": [],
            "updated": [],
            "department_candidate_count": 0,
            "promoted_count": 0,
            "school_count": 1,
        },
    )

    response = client.post(
        "/api/v1/admin/catalog-refreshes/announcement-foundation",
        json={"school_names": ["Example University"], "dry_run": True, "sources": ["chsi", "official_rosters", "school_homepages"]},
        headers=_admin_headers(),
    )
    assert response.status_code == 200

    for _ in range(9):
        if workflow_engine.process_step_batch(batch_size=4, worker_name="test-worker") == 0:
            break

    with SessionLocal() as db:
        run = db.query(WorkflowRun).filter(WorkflowRun.id == response.json()["workflow_run_id"]).one()
        steps = db.query(WorkflowStep).filter(WorkflowStep.run_id == run.id).order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc()).all()

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
```

- [ ] **Step 2: Run the rewritten regression and confirm it fails before wiring the new processors**

Run: `pytest backend/tests/test_crawler_v2_admin.py::test_admin_announcement_foundation_refresh_fans_out_school_enrich_and_merges_after_barrier -q`

Expected: failure because the new step types and fanout logic are not implemented yet.

- [ ] **Step 3: Wire the fetch and enqueue processors**

```python
def _process_fetch_chsi_school_catalog_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    schools = fetch_chsi_school_catalog(school_names=payload.school_names or None)
    _record_parse_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type=PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE,
        source_url=CHSI_SCHOOL_CATALOG_URL,
        payload={"schools": schools},
    )
    next_step = _queue_next_announcement_catalog_step(db, step=step, next_step_type=STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH, payload=payload)
    return {"school_count": len(schools), "child_step_id": next_step.id if next_step is not None else None}


def _process_enqueue_chsi_school_enrich_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    base_artifact = (
        db.query(ParseArtifact)
        .filter(ParseArtifact.workflow_step_id == step.parent_step_id, ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE)
        .order_by(ParseArtifact.created_at.desc(), ParseArtifact.id.desc())
        .first()
    )
    base_schools = list((base_artifact.payload or {}).get("schools") or [])
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    child_ids: list[str] = []
    for school in base_schools:
        child = _create_idempotent_child_step(
            db,
            run=run,
            parent_step=step,
            step_type=STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload=ChsiSchoolEnrichPayload(
                school_code=str(school.get("school_code") or ""),
                school_name=str(school.get("school_name") or ""),
                chsi_school_url=str(school.get("chsi_school_url") or ""),
            ).model_dump(),
        )
        child_ids.append(child.id)
    barrier = _create_idempotent_child_step(
        db,
        run=run,
        parent_step=step,
        step_type=STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
        host_key=None,
        input_payload=payload.model_dump(),
    )
    return {"queued_school_count": len(child_ids), "child_step_ids": child_ids, "barrier_step_id": barrier.id}
```

- [ ] **Step 4: Wire the enrich and barrier processors, add policies, then commit**

```python
def _process_enrich_chsi_school_snapshot_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = ChsiSchoolEnrichPayload.model_validate(step.input_payload or {})
    school = enrich_chsi_school_entry(payload.model_dump())
    _record_parse_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type=PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH,
        source_url=payload.chsi_school_url,
        payload=school,
    )
    source_meta = dict(school.get("source_meta") or {})
    return {
        "school_code": payload.school_code,
        "school_name": payload.school_name,
        "seed_hint_count": len(source_meta.get("seed_hint_urls") or []),
        "has_department_page": bool(source_meta.get("department_page_url")),
        "has_major_page": bool(source_meta.get("major_page_url")),
    }


def _process_await_chsi_school_enrich_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    children = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.run_id == step.run_id,
            WorkflowStep.parent_step_id == step.parent_step_id,
            WorkflowStep.step_type == STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
        )
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .all()
    )
    succeeded = [child for child in children if child.status == "done"]
    failed = [child for child in children if child.status == "failed"]
    pending = [child for child in children if child.status in {"pending", "running"}]
    summary = {
        "total_school_count": len(children),
        "succeeded_school_count": len(succeeded),
        "failed_school_count": len(failed),
        "pending_school_count": len(pending),
        "failed_schools": [
            {
                "school_code": child.input_payload.get("school_code"),
                "school_name": child.input_payload.get("school_name"),
                "error_type": child.error_type,
                "error_message": child.error_message,
            }
            for child in failed
        ],
    }
    if pending:
        raise DeferredStep(result_payload=summary, delay_seconds=15)
    if failed:
        raise TerminalStepFailure(message="chsi school enrich barrier failed", result_payload={**summary, "terminal_reason": "chsi_school_enrich_failed"})
    base_artifact = (
        db.query(ParseArtifact)
        .filter(ParseArtifact.workflow_step_id == step.parent_step.parent_step_id, ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE)
        .order_by(ParseArtifact.created_at.desc(), ParseArtifact.id.desc())
        .first()
    )
    enrich_rows = [
        artifact.payload
        for artifact in (
            db.query(ParseArtifact)
            .filter(ParseArtifact.workflow_step_id.in_([child.id for child in succeeded]), ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH)
            .order_by(ParseArtifact.created_at.asc(), ParseArtifact.id.asc())
            .all()
        )
    ]
    merged = merge_chsi_school_catalog(list((base_artifact.payload or {}).get("schools") or []), enrich_rows, paths=foundation_paths())
    next_step = _queue_next_announcement_catalog_step(db, step=step, next_step_type=STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG, payload=payload)
    return {**summary, "school_count": len(merged), "child_step_id": next_step.id if next_step is not None else None}
```

Run: `pytest backend/tests/test_workflow_v2.py backend/tests/test_crawler_v2_admin.py::test_admin_announcement_foundation_refresh_fans_out_school_enrich_and_merges_after_barrier -q`

Expected: `passed`.

```bash
git add backend/app/services/workflow_v2.py backend/tests/test_crawler_v2_admin.py backend/tests/test_workflow_v2.py
git commit -m "feat: fan out chsi school enrich workflow steps"
```

### Task 4: Lock Down Barrier Failure Semantics

**Files:**
- Modify: `backend/tests/test_workflow_v2.py`
- Modify: `backend/app/services/workflow_v2.py`

- [ ] **Step 1: Add failing tests for barrier failure summaries**

```python
def test_await_chsi_school_enrich_barrier_reports_failed_school_summary():
    with SessionLocal() as db:
        run, fetch_step = workflow_v2.create_announcement_catalog_refresh_run(
            db,
            actor_username="tester",
            school_names=["One", "Two"],
            dry_run=True,
            sources=["chsi"],
        )
        enqueue_step = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=fetch_step,
            step_type=workflow_v2.STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH,
            host_key=None,
            input_payload={"school_names": ["One", "Two"], "dry_run": True, "sources": ["chsi"]},
        )
        failed_child = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=enqueue_step,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={"school_code": "1002", "school_name": "Two", "chsi_school_url": "https://yz.chsi.com.cn/sch/2"},
        )
        barrier = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=enqueue_step,
            step_type=workflow_v2.STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
            host_key=None,
            input_payload={"school_names": ["One", "Two"], "dry_run": True, "sources": ["chsi"]},
        )
        failed_child.status = "failed"
        failed_child.error_type = "ReadTimeout"
        failed_child.error_message = "ReadTimeout"
        db.commit()

        workflow_v2._mark_step_failed(
            db,
            barrier,
            RuntimeError("chsi school enrich barrier failed"),
            result_payload={
                "failed_school_count": 1,
                "pending_school_count": 0,
                "succeeded_school_count": 0,
                "failed_schools": [{"school_code": "1002", "school_name": "Two"}],
                "terminal_reason": "chsi_school_enrich_failed",
            },
        )
        db.refresh(barrier)
        db.refresh(run)

        assert barrier.status == "failed"
        assert run.status == "failed"
        assert run.result_payload["failed_schools"][0]["school_code"] == "1002"
```

- [ ] **Step 2: Extend `_mark_step_failed()` so terminal barrier failures preserve explicit result payloads**

```python
def _mark_step_failed(db: Session, step: WorkflowStep, exc: Exception, *, result_payload: dict[str, Any] | None = None) -> None:
    policy = _step_policy(step.step_type)
    step.error_type = type(exc).__name__
    step.error_message = str(exc)[:2000]
    if result_payload is not None:
        step.result_payload = result_payload
    step.lease_owner = None
    step.leased_at = None
    retryable = not isinstance(exc, ValueError)
    if retryable and int(step.attempt_count or 0) < int(max(1, step.max_attempts or policy.max_attempts)):
        step.status = "pending"
        step.available_at = utcnow() + timedelta(seconds=max(1, policy.retry_backoff_seconds * int(step.attempt_count or 1)))
        step.finished_at = None
    else:
        step.status = "failed"
        step.finished_at = utcnow()
    _refresh_run_status(db, step.run_id)
    db.commit()
```

- [ ] **Step 3: Re-run the focused workflow-unit file and commit**

Run: `pytest backend/tests/test_workflow_v2.py -q`

Expected: `passed`.

```bash
git add backend/app/services/workflow_v2.py backend/tests/test_workflow_v2.py
git commit -m "test: cover strict chsi enrich barrier behavior"
```

### Task 5: Document, Verify, and Roll Out

**Files:**
- Modify: `docs/backend_and_crawler.md`
- Optionally modify: `docs/handoff_announcement_portal_visibility_2026-03-25.md`

- [ ] **Step 1: Document the final CHSI fanout flow**

```md
## Announcement Foundation CHSI Fanout

The CHSI stage now runs as:

1. `fetch_chsi_school_catalog`
2. `enqueue_chsi_school_enrich`
3. `enrich_chsi_school_snapshot` (one child step per school)
4. `await_chsi_school_enrich`
5. `fetch_chsi_major_catalog`

Only `await_chsi_school_enrich` writes `school_catalog_snapshot.json`. Base CHSI rows and per-school enrich rows stay in workflow parse artifacts until the barrier confirms that every school step is terminal.
```

- [ ] **Step 2: Run targeted tests and then the required backend suite**

Run: `pytest backend/tests/test_announcement_foundation.py backend/tests/test_workflow_v2.py backend/tests/test_crawler_v2_admin.py -q`

Expected: `passed`.

Run: `npm run test:backend`

Expected: backend suite passes.

- [ ] **Step 3: Commit the finished implementation and push**

```bash
git status --short
git add backend/app/services/announcement_foundation.py backend/app/services/workflow_v2.py backend/tests/test_announcement_foundation.py backend/tests/test_workflow_v2.py backend/tests/test_crawler_v2_admin.py docs/backend_and_crawler.md docs/handoff_announcement_portal_visibility_2026-03-25.md
git commit -m "feat: add chsi foundation enrich fanout barrier"
git push origin main
```

If `docs/handoff_announcement_portal_visibility_2026-03-25.md` did not change, remove it from `git add`.

- [ ] **Step 4: Package and deploy the production bundle with a fast-forward merge**

```bash
sha=$(git rev-parse --short HEAD)
bundle="deploy-$sha.bundle"
git bundle create "$bundle" main
scp "$bundle" root@38.76.215.159:/root/
ssh root@38.76.215.159 "cd /root/code/kaoyan-miniapp-mvp && git fetch /root/$bundle main:bundle-deploy-$sha && git checkout main && git merge --ff-only bundle-deploy-$sha && systemctl restart kaoyan-backend && systemctl restart kaoyan-crawler-v2 && curl -fsS https://api.gewujl.cloud/api/v1/health"
```

Expected: health contains `"status":"ok"` and `"db":"up"`. If `redis` still reports `"down"` and that matches the current baseline, note it in the delivery summary instead of blocking the deploy.

- [ ] **Step 5: Validate the new runtime shape on production**

```bash
workflow_response=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/admin/catalog-refreshes/announcement-foundation \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run":true,"sources":["chsi","official_rosters","school_homepages"],"school_names":["北京大学"]}')
workflow_run_id=$(printf '%s' "$workflow_response" | python -c 'import json,sys; print(json.load(sys.stdin)["workflow_run_id"])')
curl -sS "http://127.0.0.1:8000/api/v1/admin/workflows/$workflow_run_id" -H "X-Admin-Token: $ADMIN_TOKEN"
```

Expected: the run shows `fetch_chsi_school_catalog`, `enqueue_chsi_school_enrich`, `enrich_chsi_school_snapshot`, `await_chsi_school_enrich`, and the barrier payload contains `total_school_count`, `succeeded_school_count`, `failed_school_count`, and `pending_school_count`.

After the scoped dry-run passes, trigger one full `school_names=[]` dry-run and confirm the CHSI stage advances through the new barriered pipeline instead of stalling inside a single long-running step.

---

## Self-Review Checklist

- Spec coverage
  - Fanout step split is covered in Tasks 2 and 3.
  - Strict barrier semantics are covered in Tasks 3 and 4.
  - Production validation and docs are covered in Task 5.
- Placeholder scan
  - No unresolved placeholder markers or angle-bracket placeholders remain.
- Type consistency
  - Step names are consistent: `enqueue_chsi_school_enrich`, `enrich_chsi_school_snapshot`, `await_chsi_school_enrich`.
  - Helper names are consistent: `enrich_chsi_school_entry`, `merge_chsi_school_catalog`, `_create_idempotent_child_step`, `_mark_step_deferred`, `DeferredStep`, `TerminalStepFailure`.
