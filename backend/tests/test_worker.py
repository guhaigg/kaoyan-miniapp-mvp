from app.worker import process_single_pending_job


def test_refresh_job_is_consumed_async(client, monkeypatch):
    source_resp = client.post(
        "/api/v1/admin/sources",
        headers={"X-Admin-Token": "test-admin-token"},
        json={
            "school_name": "XX大学",
            "name": "研究生院公告源",
            "base_url": "https://example.com/graduate",
            "source_type": "official",
            "enabled": True,
            "config": {"categories": ["announcement"]},
        },
    )
    assert source_resp.status_code == 200

    refresh_resp = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "XX大学", "keywords": "公告", "refresh": True},
    )
    assert refresh_resp.status_code == 200
    refresh_job_id = refresh_resp.json()["refresh_job_id"]
    assert refresh_job_id

    def fake_fetch_html(_url: str, timeout_seconds: int = 12):
        return """
        <html><head><title>研究生公告</title></head>
        <body>
          <a href="/notice/1">2026年硕士招生公告</a>
          <a href="/notice/2">普通新闻</a>
        </body></html>
        """

    monkeypatch.setattr("app.services.crawler.fetch_html", fake_fetch_html)
    assert process_single_pending_job() is True

    job_status_resp = client.get(f"/api/v1/jobs/{refresh_job_id}")
    assert job_status_resp.status_code == 200
    assert job_status_resp.json()["status"] == "completed"

    search_resp = client.post("/api/v1/search/announcements", json={"school_name": "XX大学"})
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 1

