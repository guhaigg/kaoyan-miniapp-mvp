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
    )
    assert second.status_code == 200

    res1 = client.post("/api/v1/search/announcements", json={"school_name": "XX大学", "keywords": "招生"})
    assert res1.status_code == 200
    assert res1.json()["total"] == 1

    res2 = client.post("/api/v1/search/adjustments", json={"major": "计算机", "region": "北京"})
    assert res2.status_code == 200
    assert res2.json()["total"] == 1

