from app.db import SessionLocal
from app.models import CrawlJob, WorkflowRun, WorkflowStep
from app.services.school_cold_start import run_family_discovery_job


def test_family_discovery_job_can_handoff_to_v2_with_explicit_seeds():
    with SessionLocal() as db:
        job = CrawlJob(
            category="announcement",
            status="pending",
            query={
                "job_kind": "family_discovery",
                "workflow_handoff": "v2",
                "school_name": "Handoff University",
                "families": ["admissions", "notice"],
                "homepage_url": "https://handoff.example.edu.cn/",
                "seed_urls": ["https://handoff.example.edu.cn/notices/"],
            },
        )
        db.add(job)
        db.flush()
        job_id = job.id

        _content_id, message = run_family_discovery_job(db, job, dict(job.query or {}))
        assert "crawler v2 workflow" in message
        db.commit()

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == job.query["workflow_run_id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == job.query["workflow_step_id"]).one()

        assert job.query["result_state"] == "workflow_handoff"
        assert job.query["result_candidate_urls"] == [
            "https://handoff.example.edu.cn/",
            "https://handoff.example.edu.cn/notices/",
        ]
        assert run.workflow_type == "scope_rebuild"
        assert run.request_payload["families"] == ["admissions", "notice"]
        assert step.input_payload["families"] == ["admissions", "notice"]


def test_family_discovery_job_announcement_uses_canonical_seed_registry_without_explicit_handoff_flag():
    with SessionLocal() as db:
        job = CrawlJob(
            category="announcement",
            status="pending",
            query={
                "job_kind": "family_discovery",
                "school_name": "湖北大学",
                "families": ["admissions", "notice"],
            },
        )
        db.add(job)
        db.flush()
        job_id = job.id

        _content_id, message = run_family_discovery_job(db, job, dict(job.query or {}))
        assert "crawler v2 workflow" in message
        db.commit()

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == job.query["workflow_run_id"]).one()

        assert job.query["homepage_url"] == "https://yz.hubu.edu.cn/"
        assert job.query["seed_urls"] == ["https://yz.hubu.edu.cn/"]
        assert job.query["workflow_handoff"] == "v2"
        assert job.query["result_state"] == "workflow_handoff"
        assert run.request_payload["homepage_url"] == "https://yz.hubu.edu.cn/"
        assert run.request_payload["seed_urls"] == ["https://yz.hubu.edu.cn/"]


def test_family_discovery_job_announcement_without_governed_seed_ends_as_no_candidate():
    with SessionLocal() as db:
        job = CrawlJob(
            category="announcement",
            status="pending",
            query={
                "job_kind": "family_discovery",
                "school_name": "Seedless University",
                "families": ["admissions", "notice"],
            },
        )
        db.add(job)
        db.flush()
        job_id = job.id

        _content_id, message = run_family_discovery_job(db, job, dict(job.query or {}))
        assert "requires governed explicit seeds" in message
        db.commit()

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert job.query["result_state"] == "no_candidate"
        assert job.query["result_candidate_urls"] == []
        assert job.query["result_job_ids"] == []
        assert job.query.get("workflow_run_id") is None
