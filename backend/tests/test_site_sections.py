from app.db import SessionLocal
from app.models import ContentFile, CrawlError, CrawlJob, SiteSection, SiteSectionLink
from app.services.crawler import crawl_engine


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


class _DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_site_section_create_and_discover_job_creation(client):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "研究生院通知公告",
            "section_type": "notice",
            "section_url": "https://example.com/notices/",
            "school_name": "电子科技大学",
            "department_name": "研究生院",
            "department_type": "graduate_school",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "电子科技大学", "department_name": "研究生院"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200
    payload = discover_resp.json()
    assert payload["total_sections"] == 1
    assert len(payload["job_ids"]) == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == payload["job_ids"][0]).one()
        assert job.query["site_section_id"] == section_id
        assert job.query["job_kind"] == "site_section_discovery"


def test_site_section_discovery_creates_html_jobs_and_pdf_records(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "学院公告",
            "section_type": "notice",
            "section_url": "https://example.com/college/notices/",
            "school_name": "电子科技大学",
            "department_name": "计算机学院",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.services.crawler.httpx.get",
        lambda *args, **kwargs: _DummyResponse(
            """
            <html><body>
              <a href="/detail/notice-1.html">关于复试安排的通知</a>
              <a href="files/notice-1.pdf">复试细则 PDF</a>
            </body></html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"department_name": "计算机学院"},
        headers=_admin_headers(),
    )
    job_id = discover_resp.json()["job_ids"][0]

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        section = db.query(SiteSection).filter(SiteSection.id == section_id).one()
        assert section.last_discovery_status == "done"

        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 2
        html_link = next(link for link in links if link.link_type == "html")
        pdf_link = next(link for link in links if link.link_type == "pdf")
        assert html_link.status == "enqueued"
        assert pdf_link.status == "file_recorded"

        child_job = db.query(CrawlJob).filter(CrawlJob.id == html_link.crawl_job_id).one()
        assert child_job.query["source_url"] == "https://example.com/detail/notice-1.html"
        assert child_job.query["site_section_id"] == section_id
        assert child_job.query["site_section_link_id"] == html_link.id

        file_record = db.query(ContentFile).filter(ContentFile.site_section_link_id == pdf_link.id).one()
        assert file_record.file_url == "https://example.com/college/notices/files/notice-1.pdf"
        assert file_record.file_type == "pdf"
        assert file_record.parse_status == "pending"

        parent_job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert parent_job.status == "done"

    links_resp = client.get(f"/api/v1/site-sections/{section_id}/links", headers=_admin_headers())
    assert links_resp.status_code == 200
    assert links_resp.json()["total"] == 2


def test_site_section_discovery_failure_writes_crawl_error(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "失败栏目",
            "section_type": "notice",
            "section_url": "https://example.com/failure/",
            "school_name": "测试大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    def _raise_http_error(*args, **kwargs):
        raise RuntimeError("network boom")

    monkeypatch.setattr("app.services.crawler.httpx.get", _raise_http_error)

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "测试大学"},
        headers=_admin_headers(),
    )
    job_id = discover_resp.json()["job_ids"][0]

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert job.status == "failed"

        section = db.query(SiteSection).filter(SiteSection.id == section_id).one()
        assert section.last_discovery_status == "failed"
        assert "network boom" in (section.last_error or "")

        errors = db.query(CrawlError).all()
        assert len(errors) == 1
        assert errors[0].payload["crawl_job_id"] == job_id
