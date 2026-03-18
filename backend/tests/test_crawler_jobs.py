from datetime import timedelta

from app.db import SessionLocal
from app.models import Content, ContentSnapshot, CrawlError, CrawlJob, SiteSection, utcnow
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
        assert "tags" in (content.extra or {})
        assert any(tag in (content.extra or {}).get("tags", []) for tag in ["调剂", "电子信息", "复试"])
        assert content.summary


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


def test_crawl_worker_uses_readability_fallback_for_detail_page(client, monkeypatch):
    class _FakeResponse:
        text = """
        <html>
          <head><title>电子科技大学 2026 年电子信息调剂复试公告</title></head>
          <body>
            <nav>首页 友情链接 联系我们</nav>
            <div class="wrapper">
              <div class="article-body">
                <p>电子科技大学 2026 年电子信息调剂复试公告。</p>
                <p>欢迎 0854 方向考生参加复试，拟录取名单后续公布。</p>
              </div>
            </div>
          </body>
        </html>
        """

    monkeypatch.setattr("app.services.crawler._fetch_with_retry", lambda _url: _FakeResponse())

    with SessionLocal() as db:
        section = SiteSection(
            name="电子科大研招公告",
            section_type="notice",
            section_url="https://example.com/list",
            discovery_category="announcement",
            detail_selector_config={"css_selector": ".missing-body", "fallback_to_full_text": True},
        )
        db.add(section)
        db.commit()
        db.refresh(section)
        section_id = section.id

    create_resp = client.post(
        "/api/v1/crawl-jobs",
        json={
            "category": "announcement",
            "query": {
                "source_url": "https://example.com/detail-1",
                "site_section_id": section_id,
                "school_name": "电子科技大学",
            },
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        content = db.query(Content).filter(Content.source_url == "https://example.com/detail-1").one()
        assert "0854" in content.body
        assert content.extra["detail_extraction_method"] == "readability"
        assert "调剂" in content.extra["tags"]
        assert "复试" in content.extra["tags"]


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


def test_crawl_worker_requeues_stale_running_job(client):
    with SessionLocal() as db:
        stale_job = CrawlJob(
            category="announcement",
            query={"simulate": True, "title": "回收任务", "body": "stale body"},
            status="running",
            message="stuck",
            requested_at=utcnow() - timedelta(hours=1),
            started_at=utcnow() - timedelta(minutes=2),
            updated_at=utcnow() - timedelta(minutes=20),
        )
        db.add(stale_job)
        db.commit()
        stale_job_id = stale_job.id

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == stale_job_id).one()
        assert job.status == "done"
        assert job.finished_at is not None
        assert job.query["_lease_reclaim_count"] == 1


def test_crawl_worker_does_not_reclaim_fresh_running_job(client):
    with SessionLocal() as db:
        fresh_job = CrawlJob(
            category="announcement",
            query={"simulate": True, "title": "新鲜任务", "body": "fresh body"},
            status="running",
            message="still processing",
            requested_at=utcnow() - timedelta(minutes=5),
            started_at=utcnow() - timedelta(minutes=5),
            updated_at=utcnow() - timedelta(minutes=1),
        )
        db.add(fresh_job)
        db.commit()
        fresh_job_id = fresh_job.id

    processed = crawl_engine.process_job_batch()
    assert processed == 0

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == fresh_job_id).one()
        assert job.status == "running"
        assert job.finished_at is None
