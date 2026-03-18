from app.db import SessionLocal
from app.models import Content, ContentSnapshot, CrawlError, CrawlJob
from app.services.crawler import crawl_engine


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


def test_crawl_job_api_create_list_get(client):
    create_resp = client.post(
        "/api/v1/crawl-jobs",
        json={
            "category": "announcement",
            "query": {"simulate": True, "title": "任务 A", "body": "正文 A"},
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    list_resp = client.get("/api/v1/crawl-jobs", headers=_admin_headers())
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] >= 1
    assert any(item["id"] == job_id for item in payload["items"])

    get_resp = client.get(f"/api/v1/crawl-jobs/{job_id}", headers=_admin_headers())
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id
    assert get_resp.json()["status"] == "pending"


def test_crawl_worker_success_writes_content_and_snapshot(client):
    create_resp = client.post(
        "/api/v1/crawl-jobs",
        json={
            "category": "announcement",
            "query": {
                "simulate": True,
                "title": "电子科大 2026 调剂公告",
                "body": "模拟抓取正文",
                "school_name": "电子科技大学",
                "raw_html": "<html><body><h1>电子科大 2026 调剂公告</h1><p>模拟抓取正文</p></body></html>",
            },
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert job.status == "done"

        content = db.query(Content).filter(Content.source_url == f"crawl-job://{job_id}").one_or_none()
        assert content is not None
        assert content.title == "电子科大 2026 调剂公告"

        snapshot = db.query(ContentSnapshot).filter(ContentSnapshot.content_id == content.id).one_or_none()
        assert snapshot is not None
        assert "电子科大 2026 调剂公告" in (snapshot.raw_html or "")


def test_crawl_worker_failure_writes_crawl_error(client):
    create_resp = client.post(
        "/api/v1/crawl-jobs",
        json={
            "category": "announcement",
            "query": {"source_url": "bad://invalid-url"},
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["job_id"]

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert job.status == "failed"
        assert job.finished_at is not None

        errors = db.query(CrawlError).filter(CrawlError.error_type.is_not(None)).all()
        assert len(errors) == 1
        assert errors[0].payload.get("crawl_job_id") == job_id


def test_crawl_job_list_handles_legacy_completed_status(client):
    with SessionLocal() as db:
        legacy = CrawlJob(
            category="announcement",
            query={"source_url": "https://example.com/legacy"},
            status="completed",
            message="legacy row",
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = legacy.id

    resp = client.get("/api/v1/crawl-jobs?page=1&page_size=10", headers=_admin_headers())
    assert resp.status_code == 200
    item = next(x for x in resp.json()["items"] if x["id"] == legacy_id)
    assert item["status"] == "done"
