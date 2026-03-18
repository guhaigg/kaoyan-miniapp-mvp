from app.db import SessionLocal
from app.models import Content, ContentFile, CrawlError, CrawlJob, SiteSection, SiteSectionLink
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
        assert pdf_link.crawl_job_id is not None
        pdf_job = db.query(CrawlJob).filter(CrawlJob.id == pdf_link.crawl_job_id).one()
        assert pdf_job.query["job_kind"] == "file_parse"
        assert pdf_job.query["content_file_id"] == file_record.id

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


def test_site_section_discovery_applies_list_selector_config_filters_noise(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "研究生院通知公告",
            "section_type": "notice",
            "section_url": "https://example.com/gs/notices/",
            "school_name": "过滤大学",
            "list_selector_config": {
                "same_host_only": True,
                "allowed_path_prefixes": ["/gs/notices/", "/gs/article/"],
                "exclude_text_keywords": ["首页", "下一页"],
                "exclude_url_keywords": ["search", "login"],
            },
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
              <a href="/gs/notices/detail-1.html">关于复试安排的通知</a>
              <a href="/gs/notices/index.html">首页</a>
              <a href="/search?q=notice">站内搜索</a>
              <a href="https://other.example.com/notice.html">外站广告</a>
              <a href="/library/file.docx">附件下载</a>
            </body></html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "过滤大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/gs/notices/detail-1.html"


def test_site_section_discovery_supports_css_selector_for_list_page(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "选择器栏目",
            "section_type": "notice",
            "section_url": "https://example.com/selector/",
            "school_name": "选择器大学",
            "list_selector_config": {
                "css_selector": ".article-list a",
                "fallback_to_all_links": False,
            },
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
              <footer><a href="/about.html">关于我们</a></footer>
              <div class="article-list">
                <a href="/selector/detail-1.html">调剂公告一</a>
              </div>
            </body></html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "选择器大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 1
        assert links[0].title == "调剂公告一"
        assert links[0].link_url == "https://example.com/selector/detail-1.html"


def test_site_section_discovery_supports_xpath_selector_for_list_page(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "XPath 栏目",
            "section_type": "notice",
            "section_url": "https://example.com/xpath/",
            "school_name": "XPath大学",
            "list_selector_config": {
                "xpath_selector": "//ul[@class='news-list']//a",
                "fallback_to_all_links": False,
            },
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
              <div class="sidebar"><a href="/friend-link.html">友情链接</a></div>
              <ul class="news-list">
                <li><a href="/xpath/detail-1.html">拟录取公告</a></li>
              </ul>
            </body></html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "XPath大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 1
        assert links[0].link_url == "https://example.com/xpath/detail-1.html"


def test_site_section_detail_selector_limits_body_text(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "详情选择器栏目",
            "section_type": "notice",
            "section_url": "https://example.com/detail-selector/",
            "school_name": "详情大学",
            "list_selector_config": {
                "css_selector": ".article-list a",
                "fallback_to_all_links": False,
            },
            "detail_selector_config": {
                "css_selector": ".article-body",
                "fallback_to_full_text": False,
            },
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    def _fake_get(url, *args, **kwargs):
        if url == "https://example.com/detail-selector/":
            return _DummyResponse(
                """
                <html><body>
                  <div class="article-list">
                    <a href="/detail-selector/detail-1.html">复试公告</a>
                  </div>
                </body></html>
                """
            )
        if url == "https://example.com/detail-selector/detail-1.html":
            return _DummyResponse(
                """
                <html><body>
                  <div class="sidebar">友情链接 广告位</div>
                  <div class="article-body">
                    <h1>复试公告</h1>
                    <p>真正正文保留。</p>
                  </div>
                </body></html>
                """
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr("app.services.crawler.httpx.get", _fake_get)

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "详情大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        child_job = next(
            job for job in db.query(CrawlJob).all() if (job.query or {}).get("job_kind") == "detail_fetch"
        )
        assert child_job.status == "done"

        links = db.query(SiteSectionLink).all()
        assert len(links) == 1

        content = db.query(Content).filter(Content.source_url == "https://example.com/detail-selector/detail-1.html").one()
        assert "真正正文保留" in content.body
        assert "友情链接" not in content.body


def test_short_detail_page_with_target_link_becomes_link_notice(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "链接型公告栏目",
            "section_type": "notice",
            "section_url": "https://example.com/link-notice/",
            "school_name": "链接大学",
            "list_selector_config": {
                "css_selector": ".article-list a",
                "fallback_to_all_links": False,
            },
            "detail_selector_config": {
                "css_selector": ".article-body",
                "fallback_to_full_text": True,
            },
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    def _fake_get(url, *args, **kwargs):
        if url == "https://example.com/link-notice/":
            return _DummyResponse(
                """
                <html><body>
                  <div class="article-list">
                    <a href="/link-notice/detail-1.html">复试工作说明</a>
                  </div>
                </body></html>
                """
            )
        if url == "https://example.com/link-notice/detail-1.html":
            return _DummyResponse(
                """
                <html><body>
                  <div class="article-body">
                    <p>详见附件。</p>
                    <a href="/files/review-guide.pdf">点击查看原文件</a>
                  </div>
                </body></html>
                """
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr("app.services.crawler.httpx.get", _fake_get)

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "链接大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        content = db.query(Content).filter(Content.source_url == "https://example.com/link-notice/detail-1.html").one()
        assert "链接型公告" in content.body
        assert "建议优先打开下列目标地址查看完整公告" in content.body
        assert "https://example.com/files/review-guide.pdf" in content.body
        assert (content.extra or {}).get("notice_kind") == "link_notice"
        outbound_links = (content.extra or {}).get("outbound_links") or []
        assert len(outbound_links) == 1
        assert outbound_links[0]["url"] == "https://example.com/files/review-guide.pdf"
        assert "核心内容在附件中" in (content.summary or "")


def test_pdf_file_parse_ingests_text_based_pdf(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "PDF 栏目",
            "section_type": "notice",
            "section_url": "https://example.com/pdf/",
            "school_name": "PDF大学",
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
              <a href="/pdf/notice-1.pdf">2026年复试细则 PDF</a>
            </body></html>
            """
        ),
    )
    monkeypatch.setattr(
        "app.services.crawler._download_binary_with_retry",
        lambda _url: (b"%PDF-1.4 fake", "application/pdf"),
    )
    monkeypatch.setattr(
        "app.services.crawler._extract_pdf_text_from_bytes",
        lambda _bytes: "PDF大学 2026 年硕士研究生复试细则，复试安排如下，请考生按时参加复试，并按要求准备资格审查材料、身份证明、成绩单和复试设备。",
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "PDF大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        section_links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(section_links) == 1
        link = section_links[0]
        assert link.link_type == "pdf"
        assert link.status == "parsed"

        file_record = db.query(ContentFile).filter(ContentFile.site_section_link_id == link.id).one()
        assert file_record.parse_status == "done"
        assert "复试细则" in (file_record.text_extracted or "")
        assert file_record.content_id is not None

        content = db.query(Content).filter(Content.id == file_record.content_id).one()
        assert content.source_url == "https://example.com/pdf/notice-1.pdf"
        assert "复试安排如下" in content.body
        assert "复试" in (content.extra or {}).get("tags", [])


def test_pdf_file_parse_falls_back_to_placeholder_when_text_is_too_short(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "扫描 PDF 栏目",
            "section_type": "notice",
            "section_url": "https://example.com/pdf-scan/",
            "school_name": "扫描大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    monkeypatch.setattr(
        "app.services.crawler.httpx.get",
        lambda *args, **kwargs: _DummyResponse(
            """
            <html><body>
              <a href="/pdf-scan/notice-2.pdf">拟录取名单 PDF</a>
            </body></html>
            """
        ),
    )
    monkeypatch.setattr(
        "app.services.crawler._download_binary_with_retry",
        lambda _url: (b"%PDF-1.4 fake scan", "application/pdf"),
    )
    monkeypatch.setattr(
        "app.services.crawler._extract_pdf_text_from_bytes",
        lambda _bytes: "名单",
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "扫描大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    with SessionLocal() as db:
        file_record = db.query(ContentFile).one()
        assert file_record.parse_status == "needs_ocr"
        assert file_record.ocr_status == "skipped_mvp"
        assert file_record.content_id is not None

        content = db.query(Content).filter(Content.id == file_record.content_id).one()
        assert "判断该文件更像图片型或扫描件" in content.body
        assert "MVP 阶段暂不进行 OCR" in content.body
        assert content.source_url == "https://example.com/pdf-scan/notice-2.pdf"
        assert "拟录取" in (content.extra or {}).get("tags", [])


def test_content_file_admin_list_and_retry_reuses_existing_pending_job(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "待重试 PDF 栏目",
            "section_type": "notice",
            "section_url": "https://example.com/pdf-retry/",
            "school_name": "重试学校",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    monkeypatch.setattr(
        "app.services.crawler.httpx.get",
        lambda *args, **kwargs: _DummyResponse(
            """
            <html><body>
              <a href="/pdf-retry/notice-1.pdf">复试 PDF</a>
            </body></html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "重试学校"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    list_resp = client.get("/api/v1/site-sections/content-files", headers=_admin_headers())
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["parse_status"] == "pending"
    assert item["school_name"] == "重试学校"

    retry_resp = client.post(f"/api/v1/site-sections/content-files/{item['id']}/retry-parse", headers=_admin_headers())
    assert retry_resp.status_code == 200
    retry_payload = retry_resp.json()
    assert retry_payload["status"] == "existing"

    with SessionLocal() as db:
        jobs = [job for job in db.query(CrawlJob).all() if (job.query or {}).get("job_kind") == "file_parse"]
        assert len(jobs) == 1


def test_content_file_retry_creates_new_job_after_needs_ocr(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "OCR 重试栏目",
            "section_type": "notice",
            "section_url": "https://example.com/pdf-requeue/",
            "school_name": "OCR大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    monkeypatch.setattr(
        "app.services.crawler.httpx.get",
        lambda *args, **kwargs: _DummyResponse(
            """
            <html><body>
              <a href="/pdf-requeue/notice-2.pdf">拟录取名单 PDF</a>
            </body></html>
            """
        ),
    )
    monkeypatch.setattr(
        "app.services.crawler._download_binary_with_retry",
        lambda _url: (b"%PDF-1.4 fake scan", "application/pdf"),
    )
    monkeypatch.setattr(
        "app.services.crawler._extract_pdf_text_from_bytes",
        lambda _bytes: "名单",
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "OCR大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200
    processed = crawl_engine.process_job_batch()
    assert processed == 1
    processed = crawl_engine.process_job_batch()
    assert processed == 1

    list_resp = client.get(
        "/api/v1/site-sections/content-files",
        headers=_admin_headers(),
        params={"parse_status": "needs_ocr"},
    )
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]

    retry_resp = client.post(f"/api/v1/site-sections/content-files/{item['id']}/retry-parse", headers=_admin_headers())
    assert retry_resp.status_code == 200
    retry_payload = retry_resp.json()
    assert retry_payload["status"] == "queued"

    with SessionLocal() as db:
        file_record = db.query(ContentFile).filter(ContentFile.id == item["id"]).one()
        assert file_record.parse_status == "pending"
        assert file_record.ocr_status == "not_started"
        queued_job = db.query(CrawlJob).filter(CrawlJob.id == retry_payload["job_id"]).one()
        assert queued_job.status == "pending"
        assert queued_job.query["job_kind"] == "file_parse"


def test_site_section_discovery_retries_temporary_fetch_failure(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "重试栏目",
            "section_type": "notice",
            "section_url": "https://example.com/retry/",
            "school_name": "重试大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    attempts = {"count": 0}

    def _flaky_get(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary boom")
        return _DummyResponse('<html><body><a href="/retry/detail-1.html">恢复成功</a></body></html>')

    monkeypatch.setattr("app.services.crawler.httpx.get", _flaky_get)

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "重试大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    processed = crawl_engine.process_job_batch()
    assert processed == 1
    assert attempts["count"] == 3


def test_site_section_update_and_backfill_selector_config(client):
    with SessionLocal() as db:
        section = SiteSection(
            name="待回填栏目",
            section_type="notice",
            section_url="https://example.com/backfill/",
            discovery_category="announcement",
            enabled=1,
            list_selector_config={},
            detail_selector_config={},
        )
        db.add(section)
        db.commit()
        db.refresh(section)
        section_id = section.id

    backfill_resp = client.post(
        "/api/v1/site-sections/backfill-selector-config",
        json={"school_name": None, "overwrite_existing": False},
        headers=_admin_headers(),
    )
    assert backfill_resp.status_code == 200
    assert backfill_resp.json()["updated_sections"] == 1

    patch_resp = client.patch(
        f"/api/v1/site-sections/{section_id}",
        json={
            "list_selector_config": {
                "same_host_only": True,
                "include_text_keywords": ["复试", "调剂"],
            },
            "detail_selector_config": {
                "css_selector": ".article-body",
                "xpath_selector": "",
            },
        },
        headers=_admin_headers(),
    )
    assert patch_resp.status_code == 200
    payload = patch_resp.json()
    assert payload["list_selector_config"]["same_host_only"] is True
    assert payload["list_selector_config"]["include_text_keywords"] == ["复试", "调剂"]
    assert "exclude_text_keywords" in payload["list_selector_config"]
    assert payload["detail_selector_config"]["css_selector"] == ".article-body"
    assert "fallback_to_full_text" in payload["detail_selector_config"]


def test_site_section_selector_preview_returns_list_and_detail_preview(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "预览栏目",
            "section_type": "notice",
            "section_url": "https://example.com/preview/",
            "school_name": "预览大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    def _fake_fetch(url: str):
        if url == "https://example.com/preview/":
            return _DummyResponse(
                """
                <html><body>
                  <footer><a href="/about.html">关于我们</a></footer>
                  <div class="article-list">
                    <a href="/preview/detail-1.html">复试名单公示</a>
                  </div>
                </body></html>
                """
            )
        if url == "https://example.com/preview/detail-1.html":
            return _DummyResponse(
                """
                <html><body>
                  <nav>全站导航</nav>
                  <div class="article-body">这里是需要保留的正文内容，包含复试名单、学院要求和时间安排。</div>
                </body></html>
                """
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.routers.site_sections.crawler_service._fetch_with_retry", _fake_fetch)

    preview_resp = client.post(
        f"/api/v1/site-sections/{section_id}/preview-selectors",
        json={
            "list_selector_config": {
                "css_selector": ".article-list a",
                "fallback_to_all_links": False,
            },
            "detail_selector_config": {
                "css_selector": ".article-body",
                "fallback_to_full_text": False,
            },
        },
        headers=_admin_headers(),
    )
    assert preview_resp.status_code == 200
    payload = preview_resp.json()
    assert payload["list_match_count"] == 1
    assert payload["list_preview_items"][0]["url"] == "https://example.com/preview/detail-1.html"
    assert payload["detail_preview_url"] == "https://example.com/preview/detail-1.html"
    assert payload["detail_extraction_method"] == "selector"
    assert "这里是需要保留的正文内容" in payload["detail_excerpt"]
    assert payload["warnings"] == []


def test_site_section_selector_preview_warns_when_no_list_match(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "空预览栏目",
            "section_type": "notice",
            "section_url": "https://example.com/empty-preview/",
            "school_name": "空预览大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.routers.site_sections.crawler_service._fetch_with_retry",
        lambda *_args, **_kwargs: _DummyResponse("<html><body><div>没有公告列表</div></body></html>"),
    )

    preview_resp = client.post(
        f"/api/v1/site-sections/{section_id}/preview-selectors",
        json={
            "list_selector_config": {
                "css_selector": ".news-list a",
                "fallback_to_all_links": False,
            },
        },
        headers=_admin_headers(),
    )
    assert preview_resp.status_code == 200
    payload = preview_resp.json()
    assert payload["list_match_count"] == 0
    assert payload["list_preview_items"] == []
    assert "当前规则没有匹配到可用列表链接。" in payload["warnings"]
