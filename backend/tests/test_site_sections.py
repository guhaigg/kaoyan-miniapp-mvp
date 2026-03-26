from datetime import datetime, timezone

from app.config import get_settings
from app.db import SessionLocal
from app.models import Content, ContentFile, CrawlError, CrawlJob, School, SiteSection, SiteSectionLink, Source, WorkflowRun, WorkflowStep
from app.services.crawler import crawl_engine
from app.services.workflow_v2 import workflow_engine
from app.services.site_section_bootstrap import _discover_entry_pages, bootstrap_site_sections
from app.services.site_section_probe import probe_section_page


def _admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}


class _DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def _process_announcement_discovery_handoff() -> int:
    assert crawl_engine.process_job_batch() == 1
    return workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker")


def _drain_workflow_steps(max_rounds: int = 5) -> list[int]:
    processed_batches: list[int] = []
    for _ in range(max_rounds):
        processed = workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker")
        if processed == 0:
            break
        processed_batches.append(processed)
    return processed_batches


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


def test_bootstrap_site_sections_accepts_sibling_subdomain_and_skips_detail_pages(monkeypatch):
    pages = {
        "https://web.example.edu.cn/main.htm": (
            """
            <html><body>
              <a href="https://yjs.example.edu.cn/">研究生院</a>
            </body></html>
            """,
            "学校主页",
        ),
        "https://yjs.example.edu.cn/": (
            """
            <html><body>
              <a href="https://yjs.example.edu.cn/17205/list.htm">博士研究生招生信息</a>
              <a href="https://yjs.example.edu.cn/ea/79/c17243a846457/page.htm">【博士招生】资格审核结果查询</a>
            </body></html>
            """,
            "研究生院",
        ),
        "https://yjs.example.edu.cn/17205/list.htm": (
            """
            <html><body>
              <h2>博士研究生招生信息</h2>
              <table class="ArticleList">
                <tr><td><a href="/ea/79/c17243a846457/page.htm">【博士招生】资格审核结果查询</a></td></tr>
                <tr><td><a href="/eb/aa/c17243a846762/page.htm">【博士招生】综合考核考生须知</a></td></tr>
              </table>
            </body></html>
            """,
            "博士研究生招生信息",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="跨子域大学",
            homepage_url="https://web.example.edu.cn/main.htm",
            department_name=None,
            department_type="graduate_school",
            seed_urls=[],
            enabled=True,
            queue_discovery=False,
            max_sections=8,
        )
        urls = [item.section_url for item in result["items"]]
    assert "https://yjs.example.edu.cn/17205/list.htm" in urls
    assert "https://yjs.example.edu.cn/ea/79/c17243a846457/page.htm" not in urls


def test_bootstrap_site_sections_persists_portal_metadata_in_list_selector_config(monkeypatch):
    homepage_url = "https://portal.example.edu.cn/"
    section_url = "https://portal.example.edu.cn/sszs.htm"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="/sszs.htm">硕士招生</a>
            </body></html>
            """,
            "示例大学研究生招生网",
        ),
        section_url: (
            """
            <html><body>
              <h2>硕士招生</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1001/2001.htm">示例大学2026年硕士招生简章</a></td></tr>
                <tr><td><a href="/info/1001/2002.htm">示例大学2026年复试安排</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士招生-示例大学研究生招生网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="示例大学",
            homepage_url=homepage_url,
            department_name=None,
            department_type="graduate_school",
            seed_urls=[section_url],
            enabled=True,
            queue_discovery=False,
            max_sections=4,
            families={"notice", "admissions"},
            portal_entry_url=homepage_url,
            portal_scope="graduate_admissions",
        )
        section_id = result["items"][0].id
        section = db.query(SiteSection).filter(SiteSection.id == section_id).one()
        list_config = dict(section.list_selector_config or {})

    assert result["created_sections"] == 1
    assert section.section_url == section_url
    assert list_config["portal_scope"] == "graduate_admissions"
    assert list_config["portal_entry_url"] == homepage_url
    assert list_config["channel_label"] == "硕士招生"
    assert list_config["channel_tier"] == "core"
    assert "硕士招生" in list_config["channel_keywords"]
    assert list_config["portal_path_evidence"]["section_url"] == section_url
    assert list_config["portal_path_evidence"]["channel_label"] == "硕士招生"
    assert list_config["portal_path_evidence"]["channel_tier"] == "core"


def test_discover_entry_pages_uses_breadcrumbs_from_generic_gateway_targets(monkeypatch):
    homepage_url = "https://portal.example.edu.cn/"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="/zsxy.htm">招生学院</a>
            </body></html>
            """,
            "示例大学研究生招生信息网",
        ),
        "https://portal.example.edu.cn/zsxy.htm": (
            """
            <html><body>
              <a href="/channels/101/list.htm">更多&gt;&gt;</a>
            </body></html>
            """,
            "招生学院-示例大学研究生招生信息网",
        ),
        "https://portal.example.edu.cn/channels/101/list.htm": (
            """
            <html><body>
              <div class="breadcrumb">当前位置: <a href="/index.htm">网站首页</a> >> <a href="/zsxy.htm">招生学院</a> >> <a href="/channels/101/list.htm">硕士招生</a></div>
              <h2>列表页</h2>
            </body></html>
            """,
            "列表页-示例大学研究生招生信息网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    entry_pages = _discover_entry_pages(homepage_urls=[homepage_url], max_extra_pages=6)

    assert "https://portal.example.edu.cn/channels/101/list.htm" in entry_pages


def test_bootstrap_site_sections_follows_admissions_gateway_pages_backed_by_breadcrumbs(monkeypatch):
    homepage_url = "https://portal.example.edu.cn/"
    gateway_url = "https://portal.example.edu.cn/zsxy.htm"
    masters_url = "https://portal.example.edu.cn/zsxy/sszs.htm"
    notices_url = "https://portal.example.edu.cn/zsxy/tzgg.htm"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="/zsxy.htm">招生学院</a>
            </body></html>
            """,
            "示例大学研究生招生信息网",
        ),
        gateway_url: (
            """
            <html><body>
              <div class="daqaar">当前位置: <a href="index.htm">网站首页</a> >> <a href="zsxy.htm">招生学院</a></div>
              <div class="lane"><a href="zsxy/sszs.htm">硕士招生</a></div>
              <div class="lane"><a href="zsxy/tzgg.htm">通知公告</a></div>
            </body></html>
            """,
            "招生学院-示例大学研究生招生信息网",
        ),
        masters_url: (
            """
            <html><body>
              <div class="daqaar">当前位置: <a href="../index.htm">网站首页</a> >> <a href="../zsxy.htm">招生学院</a> >> <a href="sszs.htm">硕士招生</a></div>
              <h2>硕士招生</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1011/2001.htm">示例大学2026年硕士研究生招生简章</a></td></tr>
                <tr><td><a href="/info/1011/2002.htm">示例大学2026年硕士研究生复试办法</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士招生-示例大学研究生招生信息网",
        ),
        notices_url: (
            """
            <html><body>
              <div class="daqaar">当前位置: <a href="../index.htm">网站首页</a> >> <a href="../zsxy.htm">招生学院</a> >> <a href="tzgg.htm">通知公告</a></div>
              <h2>通知公告</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1012/3001.htm">示例大学2026年报名须知</a></td></tr>
                <tr><td><a href="/info/1012/3002.htm">示例大学2026年复试公告</a></td></tr>
              </table>
            </body></html>
            """,
            "通知公告-示例大学研究生招生信息网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="示例大学",
            homepage_url=homepage_url,
            department_name=None,
            department_type="graduate_school",
            seed_urls=[],
            enabled=True,
            queue_discovery=False,
            max_sections=4,
            families={"notice", "admissions"},
            portal_entry_url=homepage_url,
            portal_scope="graduate_admissions",
        )
        urls = [item.section_url for item in result["items"]]

    assert masters_url in urls
    assert notices_url in urls


def test_bootstrap_site_sections_persists_only_leaf_container_from_hybrid_page(monkeypatch):
    pages = {
        "https://hybrid.example.edu.cn/yjs/": (
            """
            <html>
              <body>
                <div class="quick-link">
                  <a href="/yjs/zsjz/list.htm">招生简章</a>
                  <a href="/yjs/tzgg/list.htm">通知公告</a>
                </div>
                <section>
                  <h2>调剂公告</h2>
                  <ul class="news-list">
                    <li><a href="/yjs/info/2026/tj-1.htm">2026年计算机学院调剂公告</a></li>
                    <li><a href="/yjs/info/2026/tj-2.htm">2026年材料学院调剂公告</a></li>
                  </ul>
                </section>
              </body>
            </html>
            """,
            "研究生招生",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="混合大学",
            homepage_url="https://hybrid.example.edu.cn/yjs/",
            department_name=None,
            department_type="graduate_school",
            seed_urls=[],
            enabled=True,
            queue_discovery=False,
            max_sections=8,
        )

    assert result["created_sections"] == 1
    section = result["items"][0]
    assert section.section_url == "https://hybrid.example.edu.cn/yjs/"
    assert section.section_type == "adjustment"
    assert section.list_selector_config["probe_role"] == "leaf"
    assert section.list_selector_config["container_signature"]
    assert section.list_selector_config["probe_family"] == "adjustment"


def test_bootstrap_site_sections_rejects_channel_prefix_pages_as_leaf_sections(monkeypatch):
    pages = {
        "https://yzb.jxau.edu.cn/": (
            """
            <html><body>
              <a href="/sszs.htm">硕士招生</a>
              <a href="/info/1021/">通知公告频道</a>
            </body></html>
            """,
            "江西农业大学研究生招生网",
        ),
        "https://yzb.jxau.edu.cn/sszs.htm": (
            """
            <html><body>
              <h2>硕士研究生招生信息</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1001/2001.htm">江西农业大学2026年硕士招生简章</a></td></tr>
                <tr><td><a href="/info/1001/2002.htm">江西农业大学2026年硕士研究生复试通知</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士研究生招生信息-江西农业大学研究生招生网",
        ),
        "https://yzb.jxau.edu.cn/info/1021/": (
            """
            <html><body>
              <h2>通知公告</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1021/3001.htm">关于复试工作的公告</a></td></tr>
              </table>
            </body></html>
            """,
            "通知公告-江西农业大学研究生招生网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="江西农业大学",
            homepage_url="https://yzb.jxau.edu.cn/",
            department_name=None,
            department_type="graduate_school",
            seed_urls=[
                "https://yzb.jxau.edu.cn/sszs.htm",
                "https://yzb.jxau.edu.cn/info/1021/",
            ],
            enabled=True,
            queue_discovery=False,
            max_sections=8,
            families={"notice", "admissions"},
        )
        urls = [item.section_url for item in result["items"]]

    assert "https://yzb.jxau.edu.cn/sszs.htm" in urls
    assert "https://yzb.jxau.edu.cn/info/1021/" not in urls


def test_bootstrap_site_sections_prioritizes_core_announcement_channels_over_supplemental_news(monkeypatch):
    homepage_url = "https://rank.example.edu.cn/"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="/sszs.htm">硕士招生</a>
              <a href="/notices.htm">通知公告</a>
              <a href="/news.htm">工作动态</a>
            </body></html>
            """,
            "排序大学研究生招生网",
        ),
        "https://rank.example.edu.cn/sszs.htm": (
            """
            <html><body>
              <h2>硕士招生</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1001/2001.htm">排序大学2026年硕士招生简章</a></td></tr>
                <tr><td><a href="/info/1001/2002.htm">排序大学2026年硕士招生复试安排</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士招生-排序大学研究生招生网",
        ),
        "https://rank.example.edu.cn/notices.htm": (
            """
            <html><body>
              <h2>通知公告</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1002/2001.htm">排序大学2026年报名公告</a></td></tr>
                <tr><td><a href="/info/1002/2002.htm">排序大学2026年复试通知</a></td></tr>
              </table>
            </body></html>
            """,
            "通知公告-排序大学研究生招生网",
        ),
        "https://rank.example.edu.cn/news.htm": (
            """
            <html><body>
              <h2>工作动态</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1003/2001.htm">排序大学2026年复试工作动态一</a></td></tr>
                <tr><td><a href="/info/1003/2002.htm">排序大学2026年复试工作动态二</a></td></tr>
                <tr><td><a href="/info/1003/2003.htm">排序大学2026年复试工作动态三</a></td></tr>
                <tr><td><a href="/info/1003/2004.htm">排序大学2026年复试工作动态四</a></td></tr>
                <tr><td><a href="/info/1003/2005.htm">排序大学2026年复试工作动态五</a></td></tr>
              </table>
            </body></html>
            """,
            "工作动态-排序大学研究生招生网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="排序大学",
            homepage_url=homepage_url,
            department_name=None,
            department_type="graduate_school",
            seed_urls=[],
            enabled=True,
            queue_discovery=False,
            max_sections=1,
            families={"notice", "admissions"},
            portal_entry_url=homepage_url,
            portal_scope="graduate_admissions",
        )

    assert result["items"][0].section_url == "https://rank.example.edu.cn/sszs.htm"


def test_bootstrap_site_sections_prefers_sections_on_preferred_portal_hosts(monkeypatch):
    homepage_url = "https://gs.rankhost.edu.cn/"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="https://yz.rankhost.edu.cn/sszs.htm">硕士招生</a>
              <a href="/news.htm">工作动态</a>
            </body></html>
            """,
            "排序大学研究生院",
        ),
        "https://yz.rankhost.edu.cn/sszs.htm": (
            """
            <html><body>
              <h2>硕士招生</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1001/2001.htm">排序大学2026年硕士招生简章</a></td></tr>
                <tr><td><a href="/info/1001/2002.htm">排序大学2026年硕士招生复试安排</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士招生-排序大学研究生招生网",
        ),
        "https://gs.rankhost.edu.cn/news.htm": (
            """
            <html><body>
              <h2>工作动态</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1003/2001.htm">排序大学2026年复试工作动态一</a></td></tr>
                <tr><td><a href="/info/1003/2002.htm">排序大学2026年复试工作动态二</a></td></tr>
                <tr><td><a href="/info/1003/2003.htm">排序大学2026年复试工作动态三</a></td></tr>
                <tr><td><a href="/info/1003/2004.htm">排序大学2026年复试工作动态四</a></td></tr>
                <tr><td><a href="/info/1003/2005.htm">排序大学2026年复试工作动态五</a></td></tr>
              </table>
            </body></html>
            """,
            "工作动态-排序大学研究生院",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="排序大学",
            homepage_url=homepage_url,
            department_name=None,
            department_type="graduate_school",
            seed_urls=[],
            enabled=True,
            queue_discovery=False,
            max_sections=1,
            families={"notice", "admissions"},
            portal_entry_url=homepage_url,
            portal_scope="graduate_admissions",
            preferred_hosts={"yz.rankhost.edu.cn"},
        )

    assert result["items"][0].section_url == "https://yz.rankhost.edu.cn/sszs.htm"


def test_bootstrap_site_sections_drops_nonpreferred_host_sections(monkeypatch):
    homepage_url = "https://yz.rankhost.edu.cn/"
    pages = {
        homepage_url: (
            """
            <html><body>
              <a href="/sszs.htm">硕士招生</a>
            </body></html>
            """,
            "排序大学研究生招生网",
        ),
        "https://yz.rankhost.edu.cn/sszs.htm": (
            """
            <html><body>
              <h2>硕士招生</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1001/2001.htm">排序大学2026年硕士招生简章</a></td></tr>
                <tr><td><a href="/info/1001/2002.htm">排序大学2026年硕士招生复试安排</a></td></tr>
              </table>
            </body></html>
            """,
            "硕士招生-排序大学研究生招生网",
        ),
        "https://gs.rankhost.edu.cn/news.htm": (
            """
            <html><body>
              <h2>工作动态</h2>
              <table class="ArticleList">
                <tr><td><a href="/info/1003/2001.htm">排序大学2026年复试工作动态一</a></td></tr>
                <tr><td><a href="/info/1003/2002.htm">排序大学2026年复试工作动态二</a></td></tr>
              </table>
            </body></html>
            """,
            "工作动态-排序大学研究生院",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="排序大学",
            homepage_url=homepage_url,
            department_name=None,
            department_type="graduate_school",
            seed_urls=["https://gs.rankhost.edu.cn/news.htm"],
            enabled=True,
            queue_discovery=False,
            max_sections=3,
            families={"notice", "admissions"},
            portal_entry_url=homepage_url,
            portal_scope="graduate_admissions",
            preferred_hosts={"yz.rankhost.edu.cn"},
        )

    assert result["items"]
    assert all(item.section_url.startswith("https://yz.rankhost.edu.cn/") for item in result["items"])


def test_bootstrap_site_sections_handles_comment_nodes_before_list_content(monkeypatch):
    pages = {
        "https://yzb.jxau.edu.cn/": (
            """
            <html><body>
              <a href="/sszs.htm">硕士招生</a>
            </body></html>
            """,
            "江西农业大学研究生招生网",
        ),
        "https://yzb.jxau.edu.cn/sszs.htm": (
            """
            <html>
              <body>
                <div class="cbox-top">
                  <div class="cbox-title"><span class="Column_Name">硕士招生</span></div>
                </div>
                <!-- cms comment before list -->
                <div class="list-content">
                  <ul class="wp_article_list">
                    <li><a href="/info/1021/3561.htm">关于提供2026年硕士研究生入学考试初试成绩加分证明材料的通知</a></li>
                    <li><a href="/info/1021/3541.htm">关于我校2026年全国硕士研究生招生入学考试成绩查询的通知</a></li>
                  </ul>
                </div>
              </body>
            </html>
            """,
            "硕士招生-研究生招生网",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.site_section_bootstrap._fetch_html", _fake_fetch_html)

    with SessionLocal() as db:
        result = bootstrap_site_sections(
            db,
            school_name="江西农业大学",
            homepage_url="https://yzb.jxau.edu.cn/",
            department_name=None,
            department_type="graduate_school",
            seed_urls=["https://yzb.jxau.edu.cn/sszs.htm"],
            enabled=True,
            queue_discovery=False,
            max_sections=8,
            families={"notice", "admissions"},
        )
        urls = [item.section_url for item in result["items"]]

    assert "https://yzb.jxau.edu.cn/sszs.htm" in urls


def test_probe_section_page_keeps_general_admissions_scope_when_doctoral_articles_dominate():
    result = probe_section_page(
        "https://example.edu.cn/zhaosheng/dongtai/list.htm",
        raw_html="""
        <html>
          <head><title>招生动态</title></head>
          <body>
            <div class="breadcrumb">当前位置：研究生招生 / 招生动态</div>
            <ul class="news-list">
              <li><a href="/zhaosheng/dongtai/2026/1.htm">【博士招生】2026年博士研究生综合考核通知</a></li>
              <li><a href="/zhaosheng/dongtai/2026/2.htm">【博士招生】2026年博士研究生资格审核结果</a></li>
            </ul>
          </body>
        </html>
        """,
        page_title="招生动态",
        allow_browser=False,
    )

    leaf = next(candidate for candidate in result.candidates if candidate.role == "leaf")
    assert leaf.family == "admissions"
    assert leaf.audience_scope == "general"


def test_probe_section_page_detects_doctoral_scope_from_stable_structure():
    result = probe_section_page(
        "https://example.edu.cn/17205/list.htm",
        raw_html="""
        <html>
          <head><title>博士研究生招生信息</title></head>
          <body>
            <div class="breadcrumb">当前位置：研究生招生 / 博士研究生招生信息</div>
            <h2>博士研究生招生信息</h2>
            <table class="ArticleList">
              <tr><td><a href="/ea/79/c17205a846457/page.htm">2026年博士研究生报考资格审核结果查询</a></td></tr>
              <tr><td><a href="/eb/aa/c17205a846762/page.htm">2026年博士研究生综合考核考生须知</a></td></tr>
            </table>
          </body>
        </html>
        """,
        page_title="博士研究生招生信息",
        allow_browser=False,
    )

    leaf = next(candidate for candidate in result.candidates if candidate.role == "leaf")
    assert leaf.family == "admissions"
    assert leaf.audience_scope == "doctoral"


def test_probe_section_page_ignores_comment_siblings_before_list_containers():
    result = probe_section_page(
        "https://yzb.jxau.edu.cn/sszs.htm",
        raw_html="""
        <html>
          <head><title>硕士招生-研究生招生网</title></head>
          <body>
            <div class="cbox-top">
              <div class="cbox-title"><span class="Column_Name">硕士招生</span></div>
            </div>
            <!-- comment node inserted by CMS before the list -->
            <div class="list-content">
              <ul class="wp_article_list">
                <li><a href="/info/1021/3561.htm">关于提供2026年硕士研究生入学考试初试成绩加分证明材料的通知</a></li>
                <li><a href="/info/1021/3541.htm">关于我校2026年全国硕士研究生招生入学考试成绩查询的通知</a></li>
              </ul>
            </div>
          </body>
        </html>
        """,
        page_title="硕士招生-研究生招生网",
        allow_browser=False,
    )

    leaf = next(candidate for candidate in result.candidates if candidate.role == "leaf")
    assert leaf.family == "admissions"
    assert leaf.audience_scope in {"general", "masters"}


def test_probe_section_page_discovers_iframe_leaf_candidates():
    pages = {
        "https://example.edu.cn/portal/": (
            """
            <html>
              <body>
                <iframe src="/frames/adjustment/list.htm"></iframe>
              </body>
            </html>
            """,
            "研究生院",
        ),
        "https://example.edu.cn/frames/adjustment/list.htm": (
            """
            <html>
              <body>
                <h2>调剂公告</h2>
                <ul class="news-list">
                  <li><a href="/frames/adjustment/2026/1.htm">2026年调剂公告（一）</a></li>
                  <li><a href="/frames/adjustment/2026/2.htm">2026年调剂公告（二）</a></li>
                </ul>
              </body>
            </html>
            """,
            "调剂公告",
        ),
    }

    def _fake_fetch_html(url: str):
        normalized = url.rstrip("/")
        for candidate, payload in pages.items():
            if candidate.rstrip("/") == normalized:
                return payload
        raise AssertionError(f"unexpected url: {url}")

    result = probe_section_page(
        "https://example.edu.cn/portal/",
        raw_html=pages["https://example.edu.cn/portal/"][0],
        page_title=pages["https://example.edu.cn/portal/"][1],
        fetch_html=_fake_fetch_html,
        family_filter={"adjustment"},
        allow_browser=False,
    )

    leaf = next(candidate for candidate in result.candidates if candidate.role == "leaf")
    assert leaf.page_url == "https://example.edu.cn/frames/adjustment/list.htm"
    assert leaf.probe_source == "iframe"
    assert leaf.family == "adjustment"


def test_probe_section_page_skips_browser_probe_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_SITE_SECTION_BROWSER_PROBE", "false")
    get_settings.cache_clear()
    try:
        result = probe_section_page(
            "https://example.edu.cn/csr/",
            raw_html="""
            <html>
              <body>
                <div id="app"></div>
                <script>window.__NEXT_DATA__ = {"props": {}};</script>
              </body>
            </html>
            """,
            page_title="客户端渲染页面",
            allow_browser=True,
        )
    finally:
        get_settings.cache_clear()

    assert result.candidates == []


def test_preview_site_section_selectors_includes_container_candidates(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "调剂公告",
            "section_type": "adjustment",
            "section_url": "https://example.com/adjustment/",
            "school_name": "混合大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.services.crawler._fetch_with_retry",
        lambda *_args, **_kwargs: _DummyResponse(
            """
            <html>
              <body>
                <div class="quick-link">
                  <a href="/adjustment/guide/list.htm">调剂工作</a>
                  <a href="/adjustment/rules/list.htm">调剂说明</a>
                </div>
                <section>
                  <h2>调剂公告</h2>
                  <ul class="news-list">
                    <li><a href="/adjustment/2026/1.htm">2026年调剂公告（一）</a></li>
                    <li><a href="/adjustment/2026/2.htm">2026年调剂公告（二）</a></li>
                  </ul>
                </section>
              </body>
            </html>
            """
        ),
    )

    preview_resp = client.post(
        f"/api/v1/site-sections/{section_id}/preview-selectors",
        json={},
        headers=_admin_headers(),
    )
    assert preview_resp.status_code == 200
    payload = preview_resp.json()
    roles = {item["role"] for item in payload["container_candidates"]}
    assert roles == {"hub", "leaf"}


def test_site_section_discovery_replays_container_links_before_fallback(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "通知公告",
            "section_type": "notice",
            "section_url": "https://example.com/notices/",
            "school_name": "复用大学",
            "list_selector_config": {
                "container_signature": "stale-signature",
                "container_selector": "div.old-list",
                "container_xpath": "/html/body/div[99]",
                "probe_family": "notice",
                "probe_scope": "general",
                "probe_role": "leaf",
                "fallback_to_all_links": False,
                "probe_sample_links": [
                    {"url": "https://example.com/notices/old-1.htm", "text": "旧公告 1", "link_type": "html"},
                    {"url": "https://example.com/notices/old-2.htm", "text": "旧公告 2", "link_type": "html"},
                ],
            },
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200
    section_id = create_resp.json()["id"]

    monkeypatch.setattr(
        "app.services.crawler._fetch_with_retry",
        lambda *_args, **_kwargs: _DummyResponse(
            """
            <html>
              <body>
                <div class="menu">
                  <a href="/notices/list.htm">通知公告</a>
                  <a href="/admissions/list.htm">研究生招生</a>
                </div>
                <section>
                  <h2>通知公告</h2>
                  <ul class="news-list">
                    <li><a href="/notices/2026/1.htm">关于复试安排的通知</a></li>
                    <li><a href="/notices/2026/2.htm">关于调档函领取的通知</a></li>
                  </ul>
                </section>
              </body>
            </html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "复用大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200
    assert _process_announcement_discovery_handoff() == 1

    with SessionLocal() as db:
        links = (
            db.query(SiteSectionLink)
            .filter(SiteSectionLink.site_section_id == section_id)
            .order_by(SiteSectionLink.link_url.asc())
            .all()
        )
        assert [link.link_url for link in links] == [
            "https://example.com/notices/2026/1.htm",
            "https://example.com/notices/2026/2.htm",
        ]


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

    assert _process_announcement_discovery_handoff() == 1

    with SessionLocal() as db:
        section = db.query(SiteSection).filter(SiteSection.id == section_id).one()
        assert section.last_discovery_status == "done"

        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 2
        html_link = next(link for link in links if link.link_type == "html")
        pdf_link = next(link for link in links if link.link_type == "pdf")
        assert html_link.status == "enqueued"
        assert pdf_link.status == "file_recorded"
        assert html_link.crawl_job_id is None
        html_step = db.query(WorkflowStep).filter(WorkflowStep.id == html_link.snapshot_meta["detail_workflow_step_id"]).one()
        html_run = db.query(WorkflowRun).filter(WorkflowRun.id == html_link.snapshot_meta["detail_workflow_run_id"]).one()
        assert html_run.workflow_type == "detail_fetch"
        assert html_step.input_payload["source_url"] == "https://example.com/detail/notice-1.html"
        assert html_step.input_payload["site_section_id"] == section_id
        assert html_step.input_payload["site_section_link_id"] == html_link.id

        file_record = db.query(ContentFile).filter(ContentFile.site_section_link_id == pdf_link.id).one()
        assert file_record.file_url == "https://example.com/college/notices/files/notice-1.pdf"
        assert file_record.file_type == "pdf"
        assert file_record.parse_status == "pending"
        assert pdf_link.crawl_job_id is None
        pdf_step = db.query(WorkflowStep).filter(WorkflowStep.id == pdf_link.snapshot_meta["parse_workflow_step_id"]).one()
        pdf_run = db.query(WorkflowRun).filter(WorkflowRun.id == pdf_link.snapshot_meta["parse_workflow_run_id"]).one()
        assert pdf_run.workflow_type == "file_parse"
        assert pdf_step.input_payload["content_file_id"] == file_record.id

        parent_job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert parent_job.status == "done"
        assert parent_job.query["result_state"] == "workflow_handoff"

    links_resp = client.get(f"/api/v1/site-sections/{section_id}/links", headers=_admin_headers())
    assert links_resp.status_code == 200
    assert links_resp.json()["total"] == 2


def test_site_section_discovery_accepts_shnu_legacy_detail_urls_outside_list_prefix(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "上海师范大学教育学院通知",
            "section_type": "notice",
            "section_url": "http://web.shnu.edu.cn/yjspyzx/19513/list.htm",
            "school_name": "上海师范大学",
            "department_name": "教育学院",
            "list_selector_config": {
                "allowed_path_prefixes": ["/yjspyzx/19513/"],
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
            <html>
              <body>
                <a href="/yjspyzx/19512/list.htm">更多>></a>
                <table class="ArticleList">
                  <tr><td><a href="/yjspyzx/ec/d6/c19513a847062/page.htm">教育学院2026年学术型博士研究生招生进入综合考核考生名单（增补）</a></td></tr>
                  <tr><td><a href="/yjspyzx/dd/20/c19513a843040/page.htm">上海师范大学教育学院2026年博士研究生招生办法</a></td></tr>
                </table>
                <ul class="wp_paging">
                  <li><a class="next" href="/yjspyzx/19513/list2.htm"><span>下一页>></span></a></li>
                  <li><a class="last" href="/yjspyzx/19513/list11.htm"><span>尾页</span></a></li>
                </ul>
              </body>
            </html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "上海师范大学", "department_name": "教育学院"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    assert _process_announcement_discovery_handoff() == 1

    with SessionLocal() as db:
        links = (
            db.query(SiteSectionLink)
            .filter(SiteSectionLink.site_section_id == section_id)
            .order_by(SiteSectionLink.link_url.asc())
            .all()
        )
        assert [link.link_url for link in links] == [
            "http://web.shnu.edu.cn/yjspyzx/dd/20/c19513a843040/page.htm",
            "http://web.shnu.edu.cn/yjspyzx/ec/d6/c19513a847062/page.htm",
        ]
        assert all(link.status == "enqueued" for link in links)
        child_steps = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.id.in_([link.snapshot_meta["detail_workflow_step_id"] for link in links]))
            .all()
        )
        assert len(child_steps) == 2
        assert all(step.step_type == "detail_fetch" for step in child_steps)


def test_site_section_discovery_accepts_shnu_subdomain_detail_urls_outside_list_prefix(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "上海师范大学博士招生信息",
            "section_type": "admissions",
            "section_url": "https://yjsc.shnu.edu.cn/17205/list.htm",
            "school_name": "上海师范大学",
            "department_name": "研究生院",
            "department_type": "graduate_school",
            "list_selector_config": {
                "allowed_path_prefixes": ["/17205/"],
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
            <html>
              <body class="main">
                <nav>
                  <a href="/17192/list.htm">招生工作</a>
                  <a href="/17206/list.htm">硕士研究生招生信息</a>
                </nav>
                <table class="ArticleList">
                  <tr><td><a href="/eb/aa/c17205a846762/page.htm">【博士招生】上海师范大学2026年博士研究生招生综合考核考生须知</a></td></tr>
                  <tr><td><a href="/ea/79/c17205a846457/page.htm">【博士招生】上海师范大学2026年博士研究生招生报考资格审核结果查询</a></td></tr>
                </table>
                <a class="next" href="/17205/list2.htm">下一页>></a>
              </body>
            </html>
            """
        ),
    )

    discover_resp = client.post(
        "/api/v1/site-sections/discover",
        json={"school_name": "上海师范大学", "department_name": "研究生院"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200

    assert _process_announcement_discovery_handoff() == 1

    with SessionLocal() as db:
        links = (
            db.query(SiteSectionLink)
            .filter(SiteSectionLink.site_section_id == section_id)
            .order_by(SiteSectionLink.link_url.asc())
            .all()
        )
        assert [link.link_url for link in links] == [
            "https://yjsc.shnu.edu.cn/ea/79/c17205a846457/page.htm",
            "https://yjsc.shnu.edu.cn/eb/aa/c17205a846762/page.htm",
        ]
        assert all(link.status == "enqueued" for link in links)


def test_site_section_link_retry_queues_html_jobs_and_reuses_existing_jobs(client):
    with SessionLocal() as db:
        school = School(name="上海师范大学", aliases=[])
        db.add(school)
        db.flush()
        section = SiteSection(
            school_id=school.id,
            name="教育学院通知",
            section_type="notice",
            section_url="http://web.shnu.edu.cn/yjspyzx/19513/list.htm",
            discovery_category="announcement",
            list_selector_config={},
            detail_selector_config={},
        )
        db.add(section)
        db.flush()
        existing_link = SiteSectionLink(
            site_section_id=section.id,
            link_url="http://web.shnu.edu.cn/yjspyzx/a8/42/c19513a829506/page.htm",
            link_url_hash="existing-html-link",
            title="教育学院2025年专业型博士研究生招生进入综合考核考生名单",
            link_type="html",
            status="discovered",
        )
        fresh_link = SiteSectionLink(
            site_section_id=section.id,
            link_url="http://web.shnu.edu.cn/yjspyzx/a8/c8/c19513a829640/page.htm",
            link_url_hash="fresh-html-link",
            title="教育学院2025年专业型博士研究生招生进入综合考核考生名单（补充公示）",
            link_type="html",
            status="discovered",
            published_at=datetime(2025, 5, 21, tzinfo=timezone.utc),
        )
        db.add_all([existing_link, fresh_link])
        db.flush()
        existing_job = CrawlJob(
            category="announcement",
            status="pending",
            message="existing detail fetch",
            query={
                "job_kind": "detail_fetch",
                "site_section_id": section.id,
                "site_section_link_id": existing_link.id,
                "source_url": existing_link.link_url,
            },
        )
        db.add(existing_job)
        db.commit()
        db.refresh(existing_link)
        db.refresh(fresh_link)
        db.refresh(existing_job)
        existing_link_id = existing_link.id
        fresh_link_id = fresh_link.id
        existing_job_id = existing_job.id

    resp = client.post(
        "/api/v1/site-sections/links/retry",
        json={"link_ids": [existing_link_id, fresh_link_id]},
        headers=_admin_headers(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total_links"] == 2
    assert payload["queued"] == 1
    assert payload["existing"] == 1
    assert payload["failed"] == 0

    items = {item["link_id"]: item for item in payload["items"]}
    assert items[existing_link_id]["status"] == "existing"
    assert items[existing_link_id]["job_id"] == existing_job_id
    assert items[fresh_link_id]["status"] == "queued"
    assert items[fresh_link_id]["job_id"] is None
    assert items[fresh_link_id]["workflow_run_id"] is not None
    assert items[fresh_link_id]["step_id"] is not None

    with SessionLocal() as db:
        fresh_link = db.query(SiteSectionLink).filter(SiteSectionLink.id == fresh_link_id).one()
        assert fresh_link.status == "enqueued"
        assert fresh_link.crawl_job_id is None
        queued_step = db.query(WorkflowStep).filter(WorkflowStep.id == items[fresh_link_id]["step_id"]).one()
        queued_run = db.query(WorkflowRun).filter(WorkflowRun.id == items[fresh_link_id]["workflow_run_id"]).one()
        assert queued_run.workflow_type == "detail_fetch"
        assert queued_step.input_payload["site_section_link_id"] == fresh_link_id
        assert queued_step.input_payload["site_section_id"] == fresh_link.site_section_id
        assert queued_step.input_payload["published_at"].startswith("2025-05-21")


def test_site_section_link_retry_queues_pdf_jobs_and_creates_missing_content_file(client):
    with SessionLocal() as db:
        school = School(name="电子科技大学", aliases=[])
        db.add(school)
        db.flush()
        section = SiteSection(
            school_id=school.id,
            name="学院附件通知",
            section_type="notice",
            section_url="https://example.com/college/notices/",
            discovery_category="announcement",
            list_selector_config={},
            detail_selector_config={},
        )
        db.add(section)
        db.flush()
        existing_file_link = SiteSectionLink(
            site_section_id=section.id,
            link_url="https://example.com/college/notices/files/notice-1.pdf",
            link_url_hash="existing-pdf-link",
            title="复试细则 PDF",
            link_type="pdf",
            status="discovered",
        )
        missing_file_link = SiteSectionLink(
            site_section_id=section.id,
            link_url="https://example.com/college/notices/files/notice-2.pdf",
            link_url_hash="missing-pdf-link",
            title="复试补充说明 PDF",
            link_type="pdf",
            status="discovered",
        )
        db.add_all([existing_file_link, missing_file_link])
        db.flush()
        file_record = ContentFile(
            site_section_link_id=existing_file_link.id,
            file_url=existing_file_link.link_url,
            file_url_hash="existing-pdf-file",
            file_type="pdf",
            mime_type="application/pdf",
            parse_status="done",
            ocr_status="done",
            file_meta={},
        )
        db.add(file_record)
        db.commit()
        db.refresh(existing_file_link)
        db.refresh(missing_file_link)
        db.refresh(file_record)
        existing_file_link_id = existing_file_link.id
        missing_file_link_id = missing_file_link.id
        existing_file_id = file_record.id

    resp = client.post(
        "/api/v1/site-sections/links/retry",
        json={"link_ids": [existing_file_link_id, missing_file_link_id]},
        headers=_admin_headers(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["queued"] == 2
    assert payload["existing"] == 0
    assert payload["failed"] == 0

    with SessionLocal() as db:
        existing_file = db.query(ContentFile).filter(ContentFile.id == existing_file_id).one()
        assert existing_file.parse_status == "pending"
        queued_existing_step = db.query(WorkflowStep).filter(WorkflowStep.id == existing_file.file_meta["parse_workflow_step_id"]).one()
        queued_existing_run = db.query(WorkflowRun).filter(WorkflowRun.id == existing_file.file_meta["parse_workflow_run_id"]).one()
        assert queued_existing_run.workflow_type == "file_parse"
        assert queued_existing_step.input_payload["content_file_id"] == existing_file.id

        missing_link = db.query(SiteSectionLink).filter(SiteSectionLink.id == missing_file_link_id).one()
        created_file = db.query(ContentFile).filter(ContentFile.site_section_link_id == missing_file_link_id).one()
        assert created_file.file_url == missing_link.link_url
        assert created_file.file_type == "pdf"
        queued_missing_step = db.query(WorkflowStep).filter(WorkflowStep.id == created_file.file_meta["parse_workflow_step_id"]).one()
        queued_missing_run = db.query(WorkflowRun).filter(WorkflowRun.id == created_file.file_meta["parse_workflow_run_id"]).one()
        assert queued_missing_run.workflow_type == "file_parse"
        assert queued_missing_step.input_payload["content_file_id"] == created_file.id


def test_site_section_link_retry_reingests_existing_content_and_cleans_summary(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.crawler._fetch_with_retry",
        lambda _url: _DummyResponse(
            """
            <html>
              <head><title>教育学院2025年专业型博士研究生招生进入综合考核考生名单（补充公示）</title></head>
              <body>
                <div class="Article">
                  <table>
                    <tr>
                      <td>
                        <span>发布日期:</span>
                        <span>2025/05/21</span>
                      </td>
                    </tr>
                  </table>
                  <div class="wp_articlecontent">
                    <p>补充公示如下，请相关考生按时参加综合考核，并按通知要求准备材料。</p>
                    <p><style><!-- BODY,DIV,TABLE,THEAD,TBODY,TFOOT,TR,TH,TD,P { font-family:"Arimo"; font-size:x-small } --></style></p>
                    <table>
                      <tr><td>学科：教育领导与管理</td></tr>
                      <tr><td>250956</td><td>韩杰</td></tr>
                      <tr><td>251108</td><td>宋丹</td></tr>
                      <tr><td>250326</td><td>王孝凡</td></tr>
                    </table>
                  </div>
                </div>
              </body>
            </html>
            """
        ),
    )

    source_url = "http://web.shnu.edu.cn/yjspyzx/a8/c8/c19513a829640/page.htm"

    with SessionLocal() as db:
        school = School(name="上海师范大学", aliases=[])
        db.add(school)
        db.flush()
        section = SiteSection(
            school_id=school.id,
            name="教育学院通知",
            section_type="notice",
            section_url="http://web.shnu.edu.cn/yjspyzx/19513/list.htm",
            discovery_category="announcement",
            list_selector_config={},
            detail_selector_config={},
        )
        db.add(section)
        db.flush()
        link = SiteSectionLink(
            site_section_id=section.id,
            link_url=source_url,
            link_url_hash="shnu-existing-link",
            title="教育学院2025年专业型博士研究生招生进入综合考核考生名单（补充公示）",
            link_type="html",
            status="discovered",
        )
        db.add(link)
        db.flush()
        existing_content = Content(
            school_id=school.id,
            category="announcement",
            title="教育学院2025年专业型博士研究生招生进入综合考核考生名单（补充公示）",
            body="旧正文",
            summary='<!-- BODY,DIV,TABLE,THEAD,TBODY,TFOOT,TR,TH,TD,P { font-family:"Arimo"; font-size:x-small } --> 学科：教育领导与管理',
            source_url=source_url,
            source_type="crawler",
            published_at=None,
            content_fingerprint="legacy-shnu-dirty-content",
            extra={},
        )
        db.add(existing_content)
        db.commit()
        db.refresh(link)
        db.refresh(existing_content)
        link_id = link.id
        content_id = existing_content.id

    retry_resp = client.post(
        "/api/v1/site-sections/links/retry",
        json={"link_ids": [link_id]},
        headers=_admin_headers(),
    )
    assert retry_resp.status_code == 200

    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

    with SessionLocal() as db:
        content = db.query(Content).filter(Content.source_url == source_url).one()
        assert content.id == content_id
        assert "学科：教育领导与管理" in content.body
        assert "<!--" not in content.summary
        assert "Arimo" not in content.summary
        assert content.published_at is not None
        assert content.published_at.isoformat().startswith("2025-05-21")


def test_site_section_link_retry_rejects_more_than_100_links(client):
    resp = client.post(
        "/api/v1/site-sections/links/retry",
        json={"link_ids": [f"link-{index}" for index in range(101)]},
        headers=_admin_headers(),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "link_ids exceeds max length 100"


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

    assert crawl_engine.process_job_batch() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

    with SessionLocal() as db:
        job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one()
        assert job.status == "done"
        assert job.query["result_state"] == "workflow_handoff"

        section = db.query(SiteSection).filter(SiteSection.id == section_id).one()
        assert section.last_discovery_status in {"queued", "failed"}

        errors = db.query(CrawlError).all()
        assert errors == []
        runs = db.query(WorkflowRun).all()
        steps = db.query(WorkflowStep).all()
        assert len(runs) == 1
        assert len(steps) == 1
        assert runs[0].status == "running"
        assert steps[0].status == "pending"
        assert steps[0].attempt_count == 1
        assert "network boom" in (steps[0].error_message or "")


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

    assert _process_announcement_discovery_handoff() == 1

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

    assert _process_announcement_discovery_handoff() == 1

    with SessionLocal() as db:
        links = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == section_id).all()
        assert len(links) == 1
        assert links[0].title == "调剂公告一"


def test_site_section_bootstrap_discovers_sections_and_queues_jobs(client, monkeypatch):
    def _fake_get(url, *args, **kwargs):
        if url == "https://lnnu.edu.cn":
            return _DummyResponse(
                """
                <html><head><title>辽宁师范大学</title></head><body>
                  <a href="/yjs/">研究生院</a>
                  <a href="/news/">新闻网</a>
                </body></html>
                """
            )
        if url == "https://lnnu.edu.cn/":
            return _DummyResponse(
                """
                <html><head><title>辽宁师范大学首页</title></head><body>
                  <a href="/yjs/">研究生院</a>
                  <a href="/info/">通知公告</a>
                </body></html>
                """
            )
        if url == "https://lnnu.edu.cn/yjs/":
            return _DummyResponse(
                """
                <html><head><title>辽宁师范大学研究生院</title></head><body>
                  <a href="/yjs/zs/">研究生招生</a>
                  <a href="/yjs/tzgg/">通知公告</a>
                  <a href="/yjs/tj/">调剂信息</a>
                </body></html>
                """
            )
        if url == "https://lnnu.edu.cn/yjs/zs/":
            return _DummyResponse(
                """
                <html><head><title>研究生招生</title></head><body>
                  <ul class="news-list">
                    <li><a href="/yjs/zs/2026/1.htm">辽宁师范大学2026年硕士研究生招生简章</a></li>
                    <li><a href="/yjs/zs/2026/2.htm">辽宁师范大学2026年复试通知</a></li>
                  </ul>
                </body></html>
                """
            )
        if url == "https://lnnu.edu.cn/yjs/tzgg/":
            return _DummyResponse(
                """
                <html><head><title>通知公告</title></head><body>
                  <ul class="news-list">
                    <li><a href="/yjs/tzgg/2026/1.htm">关于复试资格审查的通知</a></li>
                    <li><a href="/yjs/tzgg/2026/2.htm">关于调档函领取的通知</a></li>
                  </ul>
                </body></html>
                """
            )
        if url == "https://lnnu.edu.cn/yjs/tj/":
            return _DummyResponse(
                """
                <html><head><title>调剂信息</title></head><body>
                  <ul class="news-list">
                    <li><a href="/yjs/tj/2026/1.htm">2026年调剂公告（一）</a></li>
                    <li><a href="/yjs/tj/2026/2.htm">2026年调剂公告（二）</a></li>
                  </ul>
                </body></html>
                """
            )
        if url in {
                "https://lnnu.edu.cn/yjsy/",
                "https://lnnu.edu.cn/yjsc/",
                "https://lnnu.edu.cn/grs/",
                "https://lnnu.edu.cn/graduate/",
                "https://lnnu.edu.cn/yz/",
                "https://lnnu.edu.cn/zs/",
                "https://lnnu.edu.cn/news/",
                "https://lnnu.edu.cn/info/",
            }:
            return _DummyResponse("<html><body>empty</body></html>")
        raise RuntimeError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.crawler.httpx.get", _fake_get)

    resp = client.post(
        "/api/v1/site-sections/bootstrap",
        json={
            "school_name": "辽宁师范大学",
            "homepage_url": "https://lnnu.edu.cn",
            "department_name": "研究生院",
            "queue_discovery": True,
        },
        headers=_admin_headers(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["created_sections"] >= 3
    assert payload["existing_sections"] == 0
    assert len(payload["job_ids"]) == payload["created_sections"]
    names = {item["name"] for item in payload["items"]}
    assert "研究生招生" in names
    assert "通知公告" in names
    assert "调剂信息" in names

    with SessionLocal() as db:
        source = db.query(Source).filter(Source.base_url == "https://lnnu.edu.cn").one()
        assert source.school is not None
        assert source.school.name == "辽宁师范大学"
        sections = db.query(SiteSection).filter(SiteSection.school_id == source.school_id).all()
        assert len(sections) == payload["created_sections"]
        jobs = db.query(CrawlJob).filter(CrawlJob.id.in_(payload["job_ids"])).all()
        assert len(jobs) == payload["created_sections"]
        assert all(job.query["job_kind"] == "site_section_discovery" for job in jobs)


def test_site_section_bootstrap_uses_existing_source_when_homepage_is_missing(client, monkeypatch):
    with SessionLocal() as db:
        school = School(name="陌生大学", aliases=[])
        db.add(school)
        db.flush()
        db.add(
            Source(
                school_id=school.id,
                name="陌生大学官网",
                source_type="official",
                base_url="https://strange.edu.cn",
                config={},
                enabled=1,
            )
        )
        db.commit()

    def _fake_get(url, *args, **kwargs):
        if url in {
            "https://strange.edu.cn",
            "https://strange.edu.cn/",
            "https://strange.edu.cn/yjs/",
            "https://strange.edu.cn/yjsy/",
            "https://strange.edu.cn/yjsc/",
            "https://strange.edu.cn/grs/",
            "https://strange.edu.cn/graduate/",
            "https://strange.edu.cn/yz/",
            "https://strange.edu.cn/zs/",
        }:
            return _DummyResponse(
                """
                <html><head><title>陌生大学研究生院</title></head><body>
                  <a href="/yz/notice/">通知公告</a>
                </body></html>
                """
            )
        if url == "https://strange.edu.cn/yz/notice/":
            return _DummyResponse(
                """
                <html><head><title>通知公告</title></head><body>
                  <ul class="news-list">
                    <li><a href="/yz/notice/2026/1.htm">2026年复试安排通知</a></li>
                    <li><a href="/yz/notice/2026/2.htm">2026年招生咨询安排</a></li>
                  </ul>
                </body></html>
                """
            )
        raise RuntimeError(f"unexpected url: {url}")

    monkeypatch.setattr("app.services.crawler.httpx.get", _fake_get)

    resp = client.post(
        "/api/v1/site-sections/bootstrap",
        json={
            "school_name": "陌生大学",
            "queue_discovery": False,
        },
        headers=_admin_headers(),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["homepage_url"] == "https://strange.edu.cn"
    assert payload["created_sections"] >= 1


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

    assert _process_announcement_discovery_handoff() == 1

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

    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

    with SessionLocal() as db:
        child_step = db.query(WorkflowStep).filter(WorkflowStep.step_type == "detail_fetch").one()
        child_run = db.query(WorkflowRun).filter(WorkflowRun.id == child_step.run_id).one()
        assert child_step.status == "done"
        assert child_run.status == "done"

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

    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

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

    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

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

    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

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
    assert _process_announcement_discovery_handoff() == 1

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
    assert retry_payload["workflow_run_id"] is not None
    assert retry_payload["step_id"] is not None

    with SessionLocal() as db:
        jobs = [job for job in db.query(CrawlJob).all() if (job.query or {}).get("job_kind") == "file_parse"]
        steps = db.query(WorkflowStep).filter(WorkflowStep.step_type == "file_parse").all()
        assert len(jobs) == 0
        assert len(steps) == 1


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
    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

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
    assert retry_payload["workflow_run_id"] is not None
    assert retry_payload["step_id"] is not None

    with SessionLocal() as db:
        file_record = db.query(ContentFile).filter(ContentFile.id == item["id"]).one()
        assert file_record.parse_status == "pending"
        assert file_record.ocr_status == "not_started"
        queued_step = db.query(WorkflowStep).filter(WorkflowStep.id == retry_payload["step_id"]).one()
        queued_run = db.query(WorkflowRun).filter(WorkflowRun.id == retry_payload["workflow_run_id"]).one()
        assert queued_step.status == "pending"
        assert queued_run.workflow_type == "file_parse"


def test_content_file_retry_ocr_queues_workflow_step_after_needs_ocr(client, monkeypatch):
    create_resp = client.post(
        "/api/v1/site-sections",
        json={
            "name": "OCR 工作流栏目",
            "section_type": "notice",
            "section_url": "https://example.com/pdf-ocr/",
            "school_name": "OCR工作流大学",
        },
        headers=_admin_headers(),
    )
    assert create_resp.status_code == 200

    monkeypatch.setattr(
        "app.services.crawler.httpx.get",
        lambda *args, **kwargs: _DummyResponse(
            """
            <html><body>
              <a href="/pdf-ocr/notice-3.pdf">扫描版名单 PDF</a>
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
        json={"school_name": "OCR工作流大学"},
        headers=_admin_headers(),
    )
    assert discover_resp.status_code == 200
    assert _process_announcement_discovery_handoff() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1

    list_resp = client.get(
        "/api/v1/site-sections/content-files",
        headers=_admin_headers(),
        params={"parse_status": "needs_ocr"},
    )
    assert list_resp.status_code == 200
    item = list_resp.json()["items"][0]

    retry_resp = client.post(f"/api/v1/site-sections/content-files/{item['id']}/retry-ocr", headers=_admin_headers())
    assert retry_resp.status_code == 200
    retry_payload = retry_resp.json()
    assert retry_payload["status"] == "queued"

    with SessionLocal() as db:
        file_record = db.query(ContentFile).filter(ContentFile.id == item["id"]).one()
        step = db.query(WorkflowStep).filter(WorkflowStep.id == retry_payload["step_id"]).one()
        run = db.query(WorkflowRun).filter(WorkflowRun.id == retry_payload["workflow_run_id"]).one()
        assert file_record.ocr_status == "queued"
        assert step.step_type == "ocr_enqueue"
        assert run.workflow_type == "ocr_enqueue"

    assert workflow_engine.process_step_batch(batch_size=5, worker_name="test-worker") == 1


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

    assert crawl_engine.process_job_batch() == 1
    assert workflow_engine.process_step_batch(batch_size=10, worker_name="test-worker") == 1
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
    assert payload["suggestions"] == []


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
    assert any("列表规则当前没有命中任何公告链接" in item for item in payload["suggestions"])
