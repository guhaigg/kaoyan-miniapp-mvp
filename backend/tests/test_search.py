from app.schemas import AnnouncementSearchRequest, SearchItem, SearchResponse
from app.db import SessionLocal
from app.models import AdjustmentOpportunity, HistoricalAdjustmentProfile, HistoricalReleaseTimingProfile, MentorEvaluation, RawDatasetArchive
from app.services.search_cache import search_response_cache
from app.services.historical_intelligence import build_adjustment_opportunities_from_archives


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
    assert payload["items"][0]["adjustment_major_codes"] == []
    assert payload["items"][0]["adjustment_has_vacancy"] is True


def test_adjustment_search_exposes_structured_adjustment_meta(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "XX大学085400电子信息非全日制调剂通知",
            "body": "现有调剂缺额，欢迎考生填报调剂系统。",
            "school_name": "XX大学",
            "major": "电子信息",
            "region": "上海",
            "source_type": "crawler",
            "source_url": "https://example.com/adjustment-meta-1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    token = _register_and_login(client, "adjustment_search_meta_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    item = search.json()["items"][0]
    assert item["adjustment_major_codes"] == ["085400"]
    assert item["adjustment_study_modes"] == ["parttime"]
    assert item["adjustment_has_vacancy"] is True


def test_adjustment_search_keyword_matches_major_field_fuzzily(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "湖北大学外国语学院调剂通知",
            "body": "现有缺额，欢迎调剂。",
            "school_name": "湖北大学",
            "major": "学科教学（英语）",
            "region": "湖北",
            "source_type": "crawler",
            "source_url": "https://example.com/hubu-english-adjustment",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    token = _register_and_login(client, "adjustment_search_english_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "英语"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["school_name"] == "湖北大学"


def test_adjustment_search_school_filter_supports_shorter_school_root(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "湖北大学电子信息调剂公告",
            "body": "电子信息方向有调剂缺额。",
            "school_name": "湖北大学",
            "major": "电子信息",
            "region": "湖北",
            "source_type": "crawler",
            "source_url": "https://example.com/hubu-adjustment",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    token = _register_and_login(client, "adjustment_search_hubei_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] >= 1
    assert payload["items"][0]["school_name"] == "湖北大学"


def test_adjustment_search_falls_back_to_structured_opportunities(client):
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="opp-1",
                source_dataset_key="adjustment_snapshot_2025_0409_raw",
                source_type="snapshot",
                year=2025,
                school_name="山东大学",
                school_name_normalized="山东大学",
                school_code="10422",
                region_name="山东",
                school_tier="985",
                department_name="外国语学院",
                department_name_normalized="外国语学院",
                major_code="055101",
                major_name="英语笔译",
                major_name_normalized="英语笔译",
                study_mode="fulltime",
                vacancy_count=4,
                min_score=360,
                avg_score=374.5,
                max_score=389,
                verification_status="官网",
                title="山东大学 英语笔译 调剂信息",
                summary="2025 年调剂快照 · 官网 · 计划 4",
                source_url="https://example.com/sdu-adjustment",
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_structured_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "山东"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["school_name"] == "山东大学"
    assert payload["items"][0]["notice_kind"] == "historical_opportunity"
    assert payload["items"][0]["source_url"] == "https://example.com/sdu-adjustment"


def test_adjustment_search_merges_same_school_year_major_and_vacancy_rows(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-1",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier=None,
                    department_name="计算机与信息工程学院",
                    department_name_normalized="计算机与信息工程学院",
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    vacancy_count=4,
                    min_score=312,
                    avg_score=328,
                    max_score=340,
                    verification_status="官网",
                    title="湖北大学电子信息调剂快照",
                    summary="快照来源",
                    source_url="https://example.com/hubu-merge-1",
                    meta_json={"reference_urls": ["https://example.com/hubu-ref-1"]},
                ),
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-2",
                    source_dataset_key="adjustment_announcement_2025_raw",
                    source_type="adjustment_notice",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier=None,
                    department_name="人工智能学院",
                    department_name_normalized="人工智能学院",
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    vacancy_count=4,
                    min_score=315,
                    avg_score=331,
                    max_score=345,
                    verification_status="已核验",
                    title="湖北大学电子信息调剂公告",
                    summary="公告来源",
                    source_url="https://example.com/hubu-merge-2",
                    meta_json={"reference_urls": ["https://example.com/hubu-ref-2"]},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_merge_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "湖北大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["item_kind"] == "opportunity"
    assert item["school_name"] == "湖北大学"
    assert item["major"] == "电子信息"
    assert item["merged_count"] == 2
    assert "计算机与信息工程学院" in item["department_name"]
    assert "人工智能学院" in item["department_name"]

    detail = client.get(
        f"/api/v1/search/adjustments/items/{item['id']}?item_kind={item['item_kind']}",
        headers={"X-User-Token": token},
    )
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert "计算机与信息工程学院" in (detail_payload["department_name"] or "")
    assert "人工智能学院" in (detail_payload["department_name"] or "")
    urls = [entry["url"] for entry in detail_payload["links"]]
    assert "https://example.com/hubu-merge-1" in urls
    assert "https://example.com/hubu-merge-2" in urls


def test_adjustment_search_infers_department_from_title_when_missing(client):
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="merge-opp-infer-1",
                source_dataset_key="adjustment_announcement_2025_raw",
                source_type="adjustment_notice",
                year=2025,
                school_name="福州大学",
                school_name_normalized="福州大学",
                school_code="10386",
                region_name="福建",
                school_tier=None,
                department_name=None,
                department_name_normalized=None,
                major_code="045101",
                major_name="教育管理",
                major_name_normalized="教育管理",
                study_mode="fulltime",
                vacancy_count=3,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status="官网",
                title="福州大学经济与管理学院教育管理调剂公告",
                summary="历史表格导入",
                source_url="https://example.com/fzu-edu-mgmt",
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_department_infer_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "福州大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["items"][0]["department_name"] == "经济与管理学院"


def test_adjustment_search_keyword_matches_region_in_structured_opportunities(client):
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="opp-2",
                source_dataset_key="adjustment_snapshot_2025_0409_raw",
                source_type="snapshot",
                year=2025,
                school_name="青岛大学",
                school_name_normalized="青岛大学",
                school_code="11065",
                region_name="山东",
                school_tier=None,
                department_name=None,
                department_name_normalized=None,
                major_code="085400",
                major_name="电子信息",
                major_name_normalized="电子信息",
                study_mode="parttime",
                vacancy_count=2,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status="官网",
                title="青岛大学电子信息调剂信息",
                summary="2025 年调剂快照 · 官网 · 计划 2",
                source_url="https://example.com/qdu-adjustment",
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_region_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "山东"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["region"] == "山东"


def test_adjustment_search_exact_school_filter_does_not_expand_to_school_prefixes(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="opp-hubu",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="025200",
                    major_name="应用统计",
                    major_name_normalized="应用统计",
                    study_mode="fulltime",
                    vacancy_count=2,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    verification_status="官网",
                    title="湖北大学应用统计调剂信息",
                    summary="湖北大学调剂信息",
                    source_url="https://example.com/hubu-adjustment",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="opp-hbzyy",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="湖北中医药大学",
                    school_name_normalized="湖北中医药大学",
                    school_code="10507",
                    region_name="湖北",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="055101",
                    major_name="英语笔译",
                    major_name_normalized="英语笔译",
                    study_mode="fulltime",
                    vacancy_count=2,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    verification_status="官网",
                    title="湖北中医药大学英语笔译调剂信息",
                    summary="湖北中医药大学调剂信息",
                    source_url="https://example.com/hbzyy-adjustment",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_exact_school_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    schools = {item["school_name"] for item in payload["items"]}
    assert "湖北大学" in schools
    assert "湖北中医药大学" not in schools


def test_adjustment_search_uses_adjustment_notice_label_for_table_results(client):
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="opp-3",
                source_dataset_key="adjustment_announcement_2025_raw",
                source_type="adjustment_notice",
                year=2025,
                school_name="山东科技大学",
                school_name_normalized="山东科技大学",
                school_code="10424",
                region_name="山东",
                school_tier=None,
                department_name="计算机学院",
                department_name_normalized="计算机学院",
                major_code="085400",
                major_name="电子信息",
                major_name_normalized="电子信息",
                study_mode="fulltime",
                vacancy_count=3,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status="官网",
                title="山东科技大学电子信息调剂公告",
                summary="表格调剂公告 · 官网 · 计划 3",
                source_url="https://example.com/sdust-adjustment",
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_notice_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "山东科技大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["school_name"] == "山东科技大学"
    assert item["source_type"] == "historical_adjustment_notice"
    assert "表格调剂公告" in item["summary"]


def test_adjustment_search_supports_year_filter(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="year-filter-2025",
                    source_dataset_key="adjustment_announcement_2025_raw",
                    source_type="adjustment_notice",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="030100",
                    major_name="法学",
                    major_name_normalized="法学",
                    study_mode="fulltime",
                    vacancy_count=3,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    verification_status="官网",
                    title="湖北大学法学2025调剂公告",
                    summary="2025 调剂",
                    source_url="https://example.com/hubu-law-2025",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="year-filter-2026",
                    source_dataset_key="admission_program_catalog_2026_raw",
                    source_type="future_program",
                    year=2026,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="030100",
                    major_name="法学",
                    major_name_normalized="法学",
                    study_mode="fulltime",
                    vacancy_count=2,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    verification_status="2026招生专业",
                    title="湖北大学法学2026招生信息",
                    summary="2026 招生专业信息",
                    source_url="https://example.com/hubu-law-2026",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_year_filter_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "湖北大学", "year": 2026},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["source_type"] == "historical_future_program"
    assert "2026" in payload["items"][0]["summary"]


def test_adjustment_search_supports_city_filter(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="city-filter-wh",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北省",
                    city_name="武汉",
                    school_tier="双一流",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    vacancy_count=3,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    title="湖北大学电子信息调剂快照",
                    summary="武汉校区",
                    source_url="https://example.com/hubu-wh",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="city-filter-cs",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="湖南大学",
                    school_name_normalized="湖南大学",
                    school_code="10532",
                    region_name="湖南省",
                    city_name="长沙",
                    school_tier="985",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    vacancy_count=2,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    title="湖南大学电子信息调剂快照",
                    summary="长沙校区",
                    source_url="https://example.com/hnu-cs",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_city_filter_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "city": "武汉"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["city"] == "武汉"


def test_build_adjustment_opportunities_from_archives_includes_2026_program_rows():
    with SessionLocal() as db:
        archive = RawDatasetArchive(
            dataset_key="admission_program_catalog_2026_raw",
            title="2026 招生专业信息表",
            dataset_type="excel",
            source_filename="2026.xlsx",
            source_path="/tmp/2026.xlsx",
            workbook_format="xlsx",
            file_sha256="x" * 64,
            file_size_bytes=1,
            storage_encoding="gzip_base64",
            raw_file_payload="H4sIAAAAAAAAA/NIzcnJVwjPL8pJAQCF/oQNCwAAAA==",
            sheet_names=["Sheet1"],
            primary_sheet_name="Sheet1",
            total_rows=1,
            total_columns=10,
            header_row=["专业代码", "专业名称", "院校名称", "省份", "名额", "发布时间", "年份", "链接"],
            preview_rows=[],
            summary_json={},
            notes=None,
        )
        db.add(archive)
        db.commit()

        from app.services import historical_intelligence as svc

        original_loader = svc.load_archive_dataframe
        svc.load_archive_dataframe = lambda *_args, **_kwargs: __import__("pandas").DataFrame(
            [
                {
                    "专业代码": "095100",
                    "专业名称": "农业",
                    "院校名称": "湖北大学",
                    "省份": "湖北",
                    "名额": 2,
                    "发布时间": "2026-03-15 10:00:00",
                    "年份": 2026,
                    "链接": "https://example.com/hubu-2026-agri",
                }
            ]
        )
        try:
            rows = build_adjustment_opportunities_from_archives(db)
        finally:
            svc.load_archive_dataframe = original_loader

    match = next(row for row in rows if row["school_name"] == "湖北大学")
    assert match["source_type"] == "future_program"
    assert match["year"] == 2026
    assert match["major_name"] == "农业"


def test_adjustment_search_exposes_historical_adjustment_insight(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "XX大学085400电子信息非全日制调剂通知",
            "body": "现有调剂缺额，欢迎考生填报调剂系统。",
            "school_name": "XX大学",
            "major": "电子信息",
            "region": "上海",
            "source_type": "crawler",
            "source_url": "https://example.com/adjustment-history-1",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        db.add_all(
            [
                HistoricalAdjustmentProfile(
                    profile_key="profile-1",
                    year=2024,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2024_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="parttime",
                    sample_count=6,
                    vacancy_count=None,
                    min_score=315,
                    avg_score=328.0,
                    max_score=341,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="profile-2",
                    year=2025,
                    source_type="adjustment_stats",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="parttime",
                    sample_count=4,
                    vacancy_count=4,
                    min_score=320,
                    avg_score=333.0,
                    max_score=320,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="profile-3",
                    year=2026,
                    source_type="future_program",
                    source_dataset_key="admission_program_catalog_2026_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode=None,
                    sample_count=3,
                    vacancy_count=3,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={"source_url": "https://example.com/xx-2026-program"},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="profile-4",
                    year=2025,
                    source_type="notice_reference",
                    source_dataset_key="adjustment_announcement_2025_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    school_code=None,
                    region_name="上海",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code=None,
                    major_name=None,
                    major_name_normalized=None,
                    study_mode=None,
                    sample_count=2,
                    vacancy_count=None,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={"reference_urls": ["https://example.com/xx-history-1", "https://example.com/xx-history-2"]},
                ),
            ]
        )
        db.add_all(
            [
                MentorEvaluation(
                    review_key="review-1",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    department_name=None,
                    department_name_normalized=None,
                    mentor_name="张老师",
                    mentor_name_normalized="张老师",
                    review_text="不推荐，存在压榨和延毕风险。",
                    review_tags=["不推荐", "压榨", "延毕"],
                    risk_level="warning",
                    meta_json={},
                ),
                MentorEvaluation(
                    review_key="review-2",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    department_name=None,
                    department_name_normalized=None,
                    mentor_name="李老师",
                    mentor_name_normalized="李老师",
                    review_text="经费充足，相处融洽。",
                    review_tags=["经费充足", "相处融洽"],
                    risk_level="positive",
                    meta_json={},
                ),
                HistoricalReleaseTimingProfile(
                    profile_key="timing-1",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    sample_count=3,
                    peak_hour=20,
                    peak_hour_bucket="晚间",
                    window_start_md="04-09",
                    window_end_md="04-12",
                    consistency_ratio=0.6667,
                    meta_json={"sample_years": [2024, 2025]},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_search_history_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海", "candidate_score": 340},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    item = search.json()["items"][0]
    assert item["historical_adjustment"]["sample_years"] == [2024, 2025]
    assert item["historical_adjustment"]["sample_count"] == 10
    assert item["historical_adjustment"]["initial_score_min"] == 315
    assert item["historical_adjustment"]["initial_score_max"] == 341
    assert item["historical_adjustment"]["min_score"] == 306
    assert item["historical_adjustment"]["avg_score"] == 326.2
    assert item["historical_adjustment"]["max_score"] == 332
    assert item["historical_adjustment"]["outlook"] == "high"
    assert item["historical_adjustment"]["future_program_count"] == 3
    assert item["historical_adjustment"]["national_line_year"] == 2026
    assert item["historical_adjustment"]["national_line_major_category"] == "工学"
    assert item["historical_adjustment"]["national_line_zone_a"] == 264
    assert item["historical_adjustment"]["national_line_zone_b"] == 254
    assert item["mentor_radar"]["review_count"] == 2
    assert item["mentor_radar"]["warning_count"] == 1
    assert item["mentor_radar"]["risk_label"] == "有导师预警"
    assert item["release_timing"]["peak_hour"] == 20
    assert item["release_timing"]["peak_hour_bucket"] == "晚间"
    assert item["release_timing"]["signal_label"] == "晚间高发"
    assert item["school_intelligence"]["confidence_label"] == "连续活跃"
    assert item["school_intelligence"]["future_program_count"] == 3
    assert item["school_intelligence"]["reference_urls"] == [
        "https://example.com/xx-history-1",
        "https://example.com/xx-history-2",
        "https://example.com/xx-2026-program",
    ]


def test_adjustment_search_sorts_by_intelligence_signal_before_recency(client):
    older = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "甲大学电子信息调剂缺额公告",
            "body": "电子信息方向可申请调剂，存在缺额。",
            "school_name": "甲大学",
            "major": "电子信息",
            "region": "上海",
            "source_type": "crawler",
            "source_url": "https://example.com/a-adjustment",
            "published_at": "2026-03-01T08:00:00Z",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert older.status_code == 200
    newer = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "乙大学电子信息调剂通知",
            "body": "电子信息方向调剂信息。",
            "school_name": "乙大学",
            "major": "电子信息",
            "region": "上海",
            "source_type": "crawler",
            "source_url": "https://example.com/b-adjustment",
            "published_at": "2026-03-10T08:00:00Z",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert newer.status_code == 200

    with SessionLocal() as db:
        db.add_all(
            [
                HistoricalAdjustmentProfile(
                    profile_key="rank-profile-1",
                    year=2024,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2024_raw",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode=None,
                    sample_count=12,
                    vacancy_count=None,
                    min_score=315,
                    avg_score=330.0,
                    max_score=345,
                    meta_json={"reference_urls": ["https://example.com/a-history"]},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="rank-profile-2",
                    year=2025,
                    source_type="future_program",
                    source_dataset_key="admission_program_catalog_2026_raw",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier=None,
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode=None,
                    sample_count=4,
                    vacancy_count=4,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={},
                ),
                HistoricalReleaseTimingProfile(
                    profile_key="rank-timing-1",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    sample_count=4,
                    peak_hour=20,
                    peak_hour_bucket="晚间",
                    window_start_md="04-09",
                    window_end_md="04-12",
                    consistency_ratio=0.75,
                    meta_json={"sample_years": [2024, 2025]},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_search_rank_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海", "candidate_score": 340},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["items"][0]["school_name"] == "甲大学"
    assert payload["items"][1]["school_name"] == "乙大学"


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


def test_adjustment_detail_returns_structured_opportunity_payload(client):
    with SessionLocal() as db:
        db.add(
            MentorEvaluation(
                review_key="mentor-detail-1",
                source_dataset_key="mentor_reviews_raw",
                school_name="山东大学",
                school_name_normalized="山东大学",
                department_name="外国语学院",
                department_name_normalized="外国语学院",
                mentor_name="李老师",
                mentor_name_normalized="李老师",
                review_text="公开评价显示该导师存在强制加班<br><br>和延毕风险，请谨慎选择。",
                review_tags=["延毕风险", "强制加班"],
                risk_level="warning",
                meta_json={},
            )
        )
        db.add(
            AdjustmentOpportunity(
                opportunity_key="opp-detail-1",
                source_dataset_key="adjustment_snapshot_2025_0409_raw",
                source_type="snapshot",
                year=2025,
                school_name="山东大学",
                school_name_normalized="山东大学",
                school_code="10422",
                region_name="山东",
                school_tier="985",
                department_name="外国语学院",
                department_name_normalized="外国语学院",
                major_code="055101",
                major_name="英语笔译",
                major_name_normalized="英语笔译",
                study_mode="fulltime",
                vacancy_count=4,
                min_score=360,
                avg_score=374.5,
                max_score=389,
                verification_status="官网",
                title="山东大学 英语笔译 调剂信息",
                summary="2025 年调剂快照 · 官网 · 计划 4",
                source_url="https://example.com/sdu-adjustment",
                meta_json={"reference_urls": ["https://example.com/sdu-reference"]},
            )
        )
        db.commit()
        opportunity_id = (
            db.query(AdjustmentOpportunity.id)
            .filter(AdjustmentOpportunity.opportunity_key == "opp-detail-1")
            .scalar()
        )

    token = _register_and_login(client, "adjustment_detail_opportunity_user")
    response = client.get(
        f"/api/v1/search/adjustments/items/{opportunity_id}?item_kind=opportunity",
        headers={"X-User-Token": token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["item_kind"] == "opportunity"
    assert payload["school_name"] == "山东大学"
    assert payload["links"][0]["url"] == "https://example.com/sdu-adjustment"
    assert payload["mentor_reviews"][0]["mentor_name"] == "李老师"
    assert "延毕风险" in payload["mentor_reviews"][0]["review_text"]
    assert "<br>" not in payload["mentor_reviews"][0]["review_text"]


def test_adjustment_detail_returns_content_body(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "湖北大学应用统计调剂通知",
            "body": "这是站内保留的完整调剂正文。",
            "school_name": "湖北大学",
            "major": "应用统计",
            "region": "湖北",
            "source_type": "crawler",
            "source_url": "https://example.com/hubu-adjustment-detail",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200
    content_id = response.json()["id"]

    token = _register_and_login(client, "adjustment_detail_content_user")
    detail = client.get(
        f"/api/v1/search/adjustments/items/{content_id}?item_kind=content",
        headers={"X-User-Token": token},
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["item_kind"] == "content"
    assert payload["body"] == "这是站内保留的完整调剂正文。"
    assert payload["source_url"] == "https://example.com/hubu-adjustment-detail"
