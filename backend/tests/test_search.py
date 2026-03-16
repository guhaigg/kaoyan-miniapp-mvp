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

    res2 = client.post("/api/v1/search/adjustments", json={"major": "计算机", "region": "北京"})
    assert res2.status_code == 200
    assert res2.json()["total"] == 1


def test_search_with_invalid_visitor_token_returns_200(client):
    response = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "XX大学"},
        headers={"X-Visitor-Token": "invalid.token"},
    )
    assert response.status_code == 200


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
