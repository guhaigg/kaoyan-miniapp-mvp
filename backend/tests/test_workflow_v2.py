from __future__ import annotations

from app.db import SessionLocal
from app.models import WorkflowRun, WorkflowStep
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
