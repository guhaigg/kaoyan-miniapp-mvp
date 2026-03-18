from app.schemas import AnnouncementSearchRequest, SearchItem, SearchResponse
from app.services.search_cache import search_response_cache


def _register_and_login(client, username: str) -> str:
    register = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123"},
    )
    assert register.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_search_announcements_and_adjustments(client):
    first = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "XX大学2026年硕士招生公告",
            "body": "招生安排与时间节点",
            "school_name": "XX大学",
            "source_type": "crawler",
            "source_url": "https://example.com/a1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "XX大学计算机调剂信息",
            "body": "计算机方向可申请调剂",
            "school_name": "XX大学",
            "major": "计算机",
            "region": "北京",
            "source_type": "manual",
            "source_url": "https://example.com/b1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert second.status_code == 200

    res1 = client.post("/api/v1/search/announcements", json={"school_name": "XX大学", "keywords": "招生"})
    assert res1.status_code == 200
    assert res1.json()["total"] == 1
    assert res1.json()["authenticated"] is False
    assert res1.json()["access_limited"] is True

    denied_adjustments = client.post("/api/v1/search/adjustments", json={"major": "计算机", "region": "北京"})
    assert denied_adjustments.status_code == 401


def test_adjustment_search_can_find_content_promoted_by_classifier(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "XX大学电子信息专业2026年硕士研究生调剂公告",
            "body": "现公布调剂缺额信息，请通过全国硕士生招生调剂系统填报。",
            "school_name": "XX大学",
            "major": "电子信息",
            "region": "北京",
            "source_type": "crawler",
            "source_url": "https://example.com/adjustment-promoted-1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    token = _register_and_login(client, "adjustment_search_logged_in")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "北京"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["category"] == "adjustment"


def test_search_announcements_exposes_notice_kind_and_pdf_parse_status(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "XX大学关于查看原文件的通知",
            "body": "该公告为链接型通知，核心内容请查看原链接或原文件。",
            "summary": "系统已识别为链接型公告，请查看原文件。",
            "school_name": "XX大学",
            "source_type": "crawler",
            "source_url": "https://example.com/link-notice-1",
            "extra": {
                "tags": ["复试线", "招生简章"],
                "notice_kind": "link_notice",
                "pdf_parse_status": "needs_ocr",
            },
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    search = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "XX大学", "keywords": "原文件"},
    )
    assert search.status_code == 200

    payload = search.json()
    assert payload["total"] == 1
    assert payload["preview_limit"] == 2
    assert payload["items"][0]["notice_kind"] == "link_notice"
    assert payload["items"][0]["pdf_parse_status"] == "needs_ocr"
    assert payload["items"][0]["tags"] == ["复试线", "招生简章"]


def test_content_upsert_dedupes_by_fingerprint_when_source_url_changes(client):
    first = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "XX大学 2026 年复试通知",
            "body": "请按时参加复试资格审查。",
            "summary": "复试安排已发布",
            "school_name": "XX大学",
            "published_at": "2026-03-18T09:00:00Z",
            "source_type": "crawler",
            "source_url": "https://example.com/source-a",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "created"

    second = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": " XX大学   2026 年复试通知 ",
            "body": "请按时参加复试资格审查。",
            "summary": "复试安排已发布",
            "school_name": "XX大学",
            "published_at": "2026-03-18T09:00:00Z",
            "source_type": "crawler",
            "source_url": "https://mirror.example.com/source-b",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "updated"
    assert second.json()["id"] == first.json()["id"]

    search = client.post("/api/v1/search/announcements", json={"school_name": "XX大学"})
    assert search.status_code == 200
    assert search.json()["total"] == 1


def test_search_cache_skips_refresh_and_page_beyond_limit():
    search_response_cache.clear()
    payload = AnnouncementSearchRequest(school_name="XX大学", page=1, page_size=10)
    cached_response = SearchResponse(
        request_id="initial",
        mode="cache",
        authenticated=True,
        access_limited=False,
        preview_limit=None,
        items=[
            SearchItem(
                id="item-1",
                category="announcement",
                school_name="XX大学",
                title="缓存命中样本",
                summary="摘要",
                tags=["调剂"],
                notice_kind=None,
                pdf_parse_status=None,
                source_url="https://example.com/cache",
                source_type="crawler",
                published_at=None,
                region=None,
                major=None,
                updated_at="2026-03-18T09:00:00Z",
            )
        ],
        total=1,
        page=1,
        page_size=10,
        source_breakdown={"crawler": 1},
        last_updated_at="2026-03-18T09:00:00Z",
        refresh_job_id=None,
    )

    search_response_cache.set("announcement", payload, cached_response)

    hit = search_response_cache.get("announcement", payload, request_id="new-request")
    assert hit is not None
    assert hit.request_id == "new-request"
    assert hit.items[0].title == "缓存命中样本"

    refresh_payload = AnnouncementSearchRequest(school_name="XX大学", page=1, page_size=10, refresh=True)
    assert search_response_cache.get("announcement", refresh_payload, request_id="refresh-request") is None

    page_three_payload = AnnouncementSearchRequest(school_name="XX大学", page=3, page_size=10)
    assert search_response_cache.get("announcement", page_three_payload, request_id="page-three") is None


def test_content_upsert_clears_search_cache(client):
    search_response_cache.clear()
    payload = AnnouncementSearchRequest(school_name="缓存大学", page=1, page_size=10)
    cached_response = SearchResponse(
        request_id="cache-before-upsert",
        mode="cache",
        authenticated=True,
        access_limited=False,
        preview_limit=None,
        items=[],
        total=0,
        page=1,
        page_size=10,
        source_breakdown={},
        last_updated_at=None,
        refresh_job_id=None,
    )
    search_response_cache.set("announcement", payload, cached_response)
    assert search_response_cache.get("announcement", payload, request_id="before") is not None

    response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "缓存大学最新通知",
            "body": "缓存应在入库后失效。",
            "school_name": "缓存大学",
            "source_type": "crawler",
            "source_url": "https://example.com/cache-invalidate-1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200
    assert search_response_cache.get("announcement", payload, request_id="after") is None


def test_search_with_invalid_visitor_token_returns_200(client):
    response = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "XX大学"},
        headers={"X-Visitor-Token": "invalid.token"},
    )
    assert response.status_code == 200


def test_anonymous_search_is_limited_to_first_two_records(client):
    for index in range(3):
        response = client.post(
            "/api/v1/content",
            json={
                "category": "announcement",
                "title": f"匿名预览公告 {index}",
                "body": "用于验证匿名搜索只展示前两条。",
                "school_name": "预览大学",
                "source_type": "crawler",
                "source_url": f"https://example.com/public-preview-{index}",
            },
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200

    search = client.post("/api/v1/search/announcements", json={"school_name": "预览大学", "page": 3, "page_size": 20})
    assert search.status_code == 200
    payload = search.json()
    assert payload["authenticated"] is False
    assert payload["access_limited"] is True
    assert payload["preview_limit"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert len(payload["items"]) == 2


def test_portal_logged_in_user_gets_full_announcement_search(client):
    token = _register_and_login(client, "search_logged_in_user")

    for index in range(3):
        response = client.post(
            "/api/v1/content",
            json={
                "category": "announcement",
                "title": f"登录态公告 {index}",
                "body": "用于验证登录态不再走匿名预览。",
                "school_name": "登录大学",
                "source_type": "crawler",
                "source_url": f"https://example.com/auth-preview-{index}",
            },
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200

    search = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "登录大学", "page": 1, "page_size": 20},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["authenticated"] is True
    assert payload["access_limited"] is False
    assert payload["preview_limit"] is None
    assert len(payload["items"]) == 3


def test_content_ingest_requires_admin_token(client):
    payload = {
        "category": "announcement",
        "title": "无权限写入测试",
        "body": "x",
        "source_type": "crawler",
        "source_url": "https://example.com/no-auth",
    }

    denied = client.post("/api/v1/content", json=payload)
    assert denied.status_code == 401

    allowed = client.post("/api/v1/content", json=payload, headers={"X-Admin-Token": "test-admin-token"})
    assert allowed.status_code == 200
