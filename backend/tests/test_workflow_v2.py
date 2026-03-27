from __future__ import annotations

import json

import pytest

from app.db import SessionLocal
from app.models import WorkflowRun, WorkflowStep
from app.services import announcement_foundation
from app.services import workflow_v2


def test_create_idempotent_child_step_allows_multiple_school_enrich_siblings():
    with SessionLocal() as db:
        run = WorkflowRun(
            workflow_type=workflow_v2.WORKFLOW_TYPE_ANNOUNCEMENT_CATALOG_REFRESH,
            scope_type="announcement",
            scope_key="announcement-foundation",
            scope_label="announcement-foundation",
            status="pending",
            request_payload={},
            result_payload={},
        )
        db.add(run)
        db.flush()
        parent = WorkflowStep(
            run_id=run.id,
            step_type=workflow_v2.STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH,
            scope_type="announcement",
            scope_key="announcement-foundation",
            status="pending",
            max_attempts=1,
            timeout_seconds=300,
            available_at=workflow_v2.utcnow(),
            input_payload={},
            result_payload={},
        )
        db.add(parent)
        db.flush()

        first = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={
                "school_code": "1001",
                "school_name": "One",
                "chsi_school_url": "https://yz.chsi.com.cn/sch/1",
            },
        )
        second = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={
                "school_code": "1002",
                "school_name": "Two",
                "chsi_school_url": "https://yz.chsi.com.cn/sch/2",
            },
        )
        first.status = "done"
        db.flush()
        duplicate = workflow_v2._create_idempotent_child_step(
            db,
            run=run,
            parent_step=parent,
            step_type=workflow_v2.STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload={
                "school_code": "1001",
                "school_name": "One",
                "chsi_school_url": "https://yz.chsi.com.cn/sch/1",
            },
        )

        assert first.id != second.id
        assert duplicate.id == first.id
        assert first.input_payload["school_code"] == "1001"
        assert second.input_payload["school_code"] == "1002"


def test_mark_step_deferred_keeps_pending_and_progress_payload():
    with SessionLocal() as db:
        run = WorkflowRun(
            workflow_type=workflow_v2.WORKFLOW_TYPE_ANNOUNCEMENT_CATALOG_REFRESH,
            scope_type="announcement",
            scope_key="announcement-foundation",
            scope_label="announcement-foundation",
            status="running",
            request_payload={},
            result_payload={},
        )
        db.add(run)
        db.flush()
        step = WorkflowStep(
            run_id=run.id,
            step_type=workflow_v2.STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
            scope_type="announcement",
            scope_key="announcement-foundation",
            status="running",
            max_attempts=1,
            timeout_seconds=300,
            available_at=workflow_v2.utcnow(),
            input_payload={},
            result_payload={},
            lease_owner="worker-1",
            leased_at=workflow_v2.utcnow(),
        )
        db.add(step)
        db.flush()

        workflow_v2._mark_step_deferred(
            db,
            step,
            result_payload={"pending_school_count": 1, "succeeded_school_count": 0},
            delay_seconds=15,
        )
        db.refresh(step)

        assert step.status == "pending"
        assert step.result_payload["pending_school_count"] == 1
        assert step.error_type is None
        assert step.error_message is None
        assert step.lease_owner is None


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
            input_payload={
                "school_code": "1002",
                "school_name": "Two",
                "chsi_school_url": "https://yz.chsi.com.cn/sch/2",
            },
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
        failed_child.finished_at = workflow_v2.utcnow()
        db.flush()

        with pytest.raises(workflow_v2.TerminalStepFailure) as exc_info:
            workflow_v2._process_await_chsi_school_enrich_step(db, barrier)

        summary = exc_info.value.result_payload
        assert summary["failed_school_count"] == 1
        assert summary["pending_school_count"] == 0
        assert summary["failed_schools"][0]["school_code"] == "1002"
        assert summary["failed_schools"][0]["school_name"] == "Two"
        assert summary["terminal_reason"] == "chsi_school_enrich_failed"

        workflow_v2._mark_step_failed(
            db,
            barrier,
            exc_info.value,
            result_payload=summary,
        )
        db.refresh(barrier)
        db.refresh(run)

        assert barrier.status == "failed"
        assert run.status == "failed"
        assert barrier.result_payload["failed_schools"][0]["school_code"] == "1002"
        assert run.result_payload["failed_schools"][0]["school_code"] == "1002"


def test_process_build_department_candidates_step_includes_skipped_school_summary(tmp_path, monkeypatch):
    paths = announcement_foundation.foundation_paths(tmp_path)
    paths.school_catalog.write_text(
        json.dumps(
            [
                {
                    "school_code": "1001",
                    "school_name": "Healthy University",
                    "source_meta": {
                        "department_page_url": "https://healthy.example.edu.cn/departments/",
                    },
                }
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", str(tmp_path))

    with SessionLocal() as db:
        run = WorkflowRun(
            workflow_type=workflow_v2.WORKFLOW_TYPE_ANNOUNCEMENT_CATALOG_REFRESH,
            scope_type="announcement",
            scope_key="announcement-foundation",
            scope_label="announcement-foundation",
            status="running",
            request_payload={},
            result_payload={},
        )
        db.add(run)
        db.flush()
        step = WorkflowStep(
            run_id=run.id,
            step_type=workflow_v2.STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES,
            scope_type="announcement",
            scope_key="announcement-foundation",
            status="running",
            max_attempts=2,
            timeout_seconds=600,
            available_at=workflow_v2.utcnow(),
            input_payload={"school_names": [], "dry_run": True, "sources": ["chsi"]},
            result_payload={},
        )
        db.add(step)
        db.flush()

        monkeypatch.setattr(
            "app.services.announcement_foundation.build_department_candidates",
            lambda schools, paths: (
                [],
                [],
                [
                    {
                        "school_code": "1002",
                        "school_name": "Timeout University",
                        "department_page_url": "https://timeout.example.edu.cn/departments/",
                        "error_type": "ReadTimeout",
                        "error_message": "The read operation timed out",
                    }
                ],
            ),
        )

        result = workflow_v2._process_build_department_candidates_step(db, step)

        assert result["department_count"] == 0
        assert result["department_candidate_count"] == 0
        assert result["skipped_school_count"] == 1
        assert result["skipped_schools"][0]["school_code"] == "1002"
        assert result["skipped_schools"][0]["error_type"] == "ReadTimeout"
