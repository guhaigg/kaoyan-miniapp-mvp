from datetime import datetime

from app.schemas import AnnouncementSearchRequest, SearchItem, SearchResponse
from app.db import SessionLocal
from app.models import AdjustmentOpportunity, Content, ContentSnapshot, HistoricalAdjustmentProfile, HistoricalReleaseTimingProfile, MentorEvaluation, RawDatasetArchive, School
from app.services.search_cache import search_response_cache
from app.services.historical_intelligence import build_adjustment_opportunities_from_archives
from app.routers.search import _build_adjustment_detail_from_opportunity
from scripts.repair_stale_announcement_content import _repair_row_by_snapshot


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


def test_adjustment_search_keeps_same_school_major_rows_separate_when_departments_differ(client):
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
    assert payload["total"] == 2
    items_by_department = {
        item["department_name"]: item
        for item in payload["items"]
    }
    assert items_by_department["计算机与信息工程学院"]["merged_count"] == 1
    assert items_by_department["人工智能学院"]["merged_count"] == 1

    detail = client.get(
        f"/api/v1/search/adjustments/items/{items_by_department['人工智能学院']['id']}?item_kind=opportunity",
        headers={"X-User-Token": token},
    )
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["department_name"] == "人工智能学院"
    urls = [entry["url"] for entry in detail_payload["links"]]
    assert "https://example.com/hubu-merge-2" in urls
    assert "https://example.com/hubu-merge-1" not in urls


def test_adjustment_search_merges_missing_department_into_unique_department_group(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-unique-1",
                    source_dataset_key="adjustment_snapshot_2025_0409_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="福州大学",
                    school_name_normalized="福州大学",
                    school_code="10386",
                    region_name="福建",
                    school_tier=None,
                    department_name="经济与管理学院",
                    department_name_normalized="经济与管理学院",
                    major_code="045101",
                    major_name="教育管理",
                    major_name_normalized="教育管理",
                    study_mode="fulltime",
                    vacancy_count=3,
                    min_score=351,
                    avg_score=360,
                    max_score=368,
                    verification_status="官网",
                    title="福州大学教育管理调剂快照",
                    summary="快照来源",
                    source_url="https://example.com/fzu-merge-1",
                    meta_json={"reference_urls": ["https://example.com/fzu-ref-1"]},
                ),
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-unique-2",
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
                    min_score=352,
                    avg_score=361,
                    max_score=369,
                    verification_status="已核验",
                    title="福州大学教育管理调剂公告",
                    summary="公告来源",
                    source_url="https://example.com/fzu-merge-2",
                    meta_json={"reference_urls": ["https://example.com/fzu-ref-2"]},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_merge_unique_department_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"keywords": "福州大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["department_name"] == "经济与管理学院"
    assert item["merged_count"] == 2

    detail = client.get(
        f"/api/v1/search/adjustments/items/{item['id']}?item_kind=opportunity",
        headers={"X-User-Token": token},
    )
    assert detail.status_code == 200
    detail_payload = detail.json()
    urls = [entry["url"] for entry in detail_payload["links"]]
    assert detail_payload["department_name"] == "经济与管理学院"
    assert "https://example.com/fzu-merge-1" in urls
    assert "https://example.com/fzu-merge-2" in urls


def test_adjustment_search_drops_school_level_aggregate_when_multiple_departments_exist(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-ambiguous-1",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北省",
                    school_tier="普本",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    vacancy_count=219,
                    min_score=260,
                    avg_score=288.2,
                    max_score=353,
                    verification_status="历史统计",
                    title="湖北大学 材料与化工 历史统计",
                    summary="学校级汇总行",
                    source_url="https://example.com/hubu-material-aggregate",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-ambiguous-2",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北省",
                    school_tier="普本",
                    department_name="材料科学与工程学院",
                    department_name_normalized="材料科学与工程学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    vacancy_count=107,
                    min_score=260,
                    avg_score=286.0,
                    max_score=338,
                    verification_status="历史统计",
                    title="湖北大学 材料与化工 历史统计",
                    summary="材料科学与工程学院",
                    source_url="https://example.com/hubu-material-science",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="merge-opp-ambiguous-3",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北省",
                    school_tier="普本",
                    department_name="化学化工学院",
                    department_name_normalized="化学化工学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    vacancy_count=41,
                    min_score=261,
                    avg_score=295.4,
                    max_score=353,
                    verification_status="历史统计",
                    title="湖北大学 材料与化工 历史统计",
                    summary="化学化工学院",
                    source_url="https://example.com/hubu-material-chem",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_aggregate_drop_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北大学", "year": 2025, "page_size": 20},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 2
    department_names = {item["department_name"] for item in payload["items"]}
    assert department_names == {"材料科学与工程学院", "化学化工学院"}
    assert all(item["source_url"] != "https://example.com/hubu-material-aggregate" for item in payload["items"])


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


def test_adjustment_search_mentor_matching_does_not_mix_other_departments_when_department_missing(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "XX大学电子信息调剂通知",
            "body": "学校级调剂通知，正文没有学院。",
            "school_name": "XX大学",
            "major": "电子信息",
            "region": "上海",
            "source_type": "crawler",
            "source_url": "https://example.com/xx-adjustment-mentor-scope",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        db.add_all(
            [
                MentorEvaluation(
                    review_key="mentor-scope-school-1",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    department_name=None,
                    department_name_normalized=None,
                    mentor_name="校级老师",
                    mentor_name_normalized="校级老师",
                    review_text="学校层面口碑不错。",
                    review_tags=["口碑尚可"],
                    risk_level="positive",
                    meta_json={},
                ),
                MentorEvaluation(
                    review_key="mentor-scope-dept-1",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="XX大学",
                    school_name_normalized="XX大学",
                    department_name="人工智能学院",
                    department_name_normalized="人工智能学院",
                    mentor_name="学院老师",
                    mentor_name_normalized="学院老师",
                    review_text="人工智能学院存在延毕风险。",
                    review_tags=["延毕风险"],
                    risk_level="warning",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_mentor_scope_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "XX大学"},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    item = search.json()["items"][0]
    assert item["mentor_radar"]["review_count"] == 2
    assert item["mentor_radar"]["warning_count"] == 1
    assert item["mentor_radar"]["positive_count"] == 1
    assert item["mentor_department_radar"] is None
    assert item["mentor_school_radar"]["review_count"] == 2


def test_adjustment_search_intelligence_filters_run_server_side(client):
    for school_name in ("甲大学", "乙大学", "丙大学"):
        response = client.post(
            "/api/v1/content",
            json={
                "category": "adjustment",
                "title": f"{school_name}电子信息调剂公告",
                "body": "电子信息方向可申请调剂。",
                "school_name": school_name,
                "major": "电子信息",
                "region": "上海",
                "source_type": "crawler",
                "source_url": f"https://example.com/{school_name}-adjustment",
            },
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200

    with SessionLocal() as db:
        db.add_all(
            [
                HistoricalAdjustmentProfile(
                    profile_key="intelligence-filter-a-2023",
                    year=2023,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2023_raw",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10011",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=2,
                    vacancy_count=None,
                    min_score=320,
                    avg_score=325.0,
                    max_score=330,
                    meta_json={"reference_urls": ["https://example.com/a-history-2023"]},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="intelligence-filter-a-2024",
                    year=2024,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2024_raw",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10011",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=3,
                    vacancy_count=None,
                    min_score=322,
                    avg_score=327.0,
                    max_score=332,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="intelligence-filter-a-2025",
                    year=2025,
                    source_type="future_program",
                    source_dataset_key="admission_program_catalog_2025_raw",
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10011",
                    region_name="上海",
                    school_tier="211",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode=None,
                    sample_count=1,
                    vacancy_count=1,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={"source_url": "https://example.com/a-program"},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="intelligence-filter-b-2025",
                    year=2025,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2025_raw",
                    school_name="乙大学",
                    school_name_normalized="乙大学",
                    school_code="10012",
                    region_name="上海",
                    school_tier="普本",
                    department_name=None,
                    department_name_normalized=None,
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=4,
                    vacancy_count=None,
                    min_score=305,
                    avg_score=310.0,
                    max_score=315,
                    meta_json={},
                ),
            ]
        )
        db.add(
            MentorEvaluation(
                review_key="intelligence-filter-warning",
                source_dataset_key="mentor_reviews_raw",
                school_name="乙大学",
                school_name_normalized="乙大学",
                department_name=None,
                department_name_normalized=None,
                mentor_name="高风险导师",
                mentor_name_normalized="高风险导师",
                review_text="存在压榨和延毕风险。",
                review_tags=["压榨", "延毕"],
                risk_level="warning",
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_filter_user")

    history_search = client.post(
        "/api/v1/search/adjustments",
        json={
            "major": "电子信息",
            "region": "上海",
            "history_backed_only": True,
            "page_size": 1,
        },
        headers={"X-User-Token": token},
    )
    assert history_search.status_code == 200
    history_payload = history_search.json()
    assert history_payload["total"] == 2
    assert len(history_payload["items"]) == 1

    long_track_search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海", "long_track_only": True},
        headers={"X-User-Token": token},
    )
    assert long_track_search.status_code == 200
    long_track_payload = long_track_search.json()
    assert long_track_payload["total"] == 1
    assert [item["school_name"] for item in long_track_payload["items"]] == ["甲大学"]

    reference_search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海", "reference_links_only": True},
        headers={"X-User-Token": token},
    )
    assert reference_search.status_code == 200
    reference_payload = reference_search.json()
    assert reference_payload["total"] == 1
    assert [item["school_name"] for item in reference_payload["items"]] == ["甲大学"]

    warning_free_search = client.post(
        "/api/v1/search/adjustments",
        json={"major": "电子信息", "region": "上海", "exclude_mentor_warnings": True},
        headers={"X-User-Token": token},
    )
    assert warning_free_search.status_code == 200
    warning_free_payload = warning_free_search.json()
    assert warning_free_payload["total"] == 2
    assert {item["school_name"] for item in warning_free_payload["items"]} == {"甲大学", "丙大学"}


def test_adjustment_search_school_filter_counts_all_matching_rows_not_first_page_window(client):
    with SessionLocal() as db:
        for index in range(25):
            db.add(
                AdjustmentOpportunity(
                    opportunity_key=f"hubei-opportunity-{index}",
                    source_dataset_key="adjustment_landing_2024_raw",
                    source_type="landing",
                    year=2024,
                    school_name="湖北大学",
                    school_name_normalized="湖北大学",
                    school_code="10512",
                    region_name="湖北",
                    school_tier="211",
                    department_name=f"学院{index}",
                    department_name_normalized=f"学院{index}",
                    major_code=f"0854{index:02d}",
                    major_name=f"专业{index}",
                    major_name_normalized=f"专业{index}",
                    study_mode="fulltime",
                    vacancy_count=1,
                    min_score=300 + index,
                    avg_score=305 + index,
                    max_score=310 + index,
                    verification_status="官网",
                    title=f"湖北大学 专业{index} 调剂信息",
                    summary=f"2024 调剂样本 {index}",
                    source_url=f"https://example.com/hubu-opportunity-{index}",
                    meta_json={},
                )
            )
        db.commit()

    token = _register_and_login(client, "adjustment_count_regression_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北大学", "page_size": 12},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 25
    assert len(payload["items"]) == 12


def test_adjustment_search_broad_filters_use_denormalized_scan_fields(client):
    with SessionLocal() as db:
        db.add_all(
            [
                AdjustmentOpportunity(
                    opportunity_key="broad-filter-match",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="甲大学",
                    school_name_normalized="甲大学",
                    school_code="10001",
                    region_name="上海",
                    school_tier="普本",
                    department_name="材料学院",
                    department_name_normalized="材料学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    has_history=1,
                    is_long_track=1,
                    reference_link_count=2,
                    min_score_required=270,
                    vacancy_count=2,
                    min_score=270,
                    avg_score=281.0,
                    max_score=295,
                    verification_status="历史统计",
                    title="甲大学材料与化工历史统计",
                    summary="用于验证 broad query 降维筛选",
                    source_url="https://example.com/broad-filter-match",
                    meta_json={"reference_urls": ["https://example.com/broad-filter-ref"]},
                ),
                AdjustmentOpportunity(
                    opportunity_key="broad-filter-no-history",
                    source_dataset_key="adjustment_snapshot_2025_raw",
                    source_type="snapshot",
                    year=2025,
                    school_name="乙大学",
                    school_name_normalized="乙大学",
                    school_code="10002",
                    region_name="上海",
                    school_tier="普本",
                    department_name="材料学院",
                    department_name_normalized="材料学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    has_history=0,
                    is_long_track=1,
                    reference_link_count=1,
                    min_score_required=268,
                    vacancy_count=3,
                    min_score=268,
                    avg_score=279.0,
                    max_score=290,
                    verification_status="官网",
                    title="乙大学材料与化工调剂信息",
                    summary="无历史样本",
                    source_url="https://example.com/broad-filter-no-history",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="broad-filter-short-track",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="丙大学",
                    school_name_normalized="丙大学",
                    school_code="10003",
                    region_name="上海",
                    school_tier="普本",
                    department_name="材料学院",
                    department_name_normalized="材料学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    has_history=1,
                    is_long_track=0,
                    reference_link_count=2,
                    min_score_required=266,
                    vacancy_count=2,
                    min_score=266,
                    avg_score=276.0,
                    max_score=288,
                    verification_status="历史统计",
                    title="丙大学材料与化工历史统计",
                    summary="非连续活跃",
                    source_url="https://example.com/broad-filter-short-track",
                    meta_json={},
                ),
                AdjustmentOpportunity(
                    opportunity_key="broad-filter-too-high",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    source_type="stats",
                    year=2025,
                    school_name="丁大学",
                    school_name_normalized="丁大学",
                    school_code="10004",
                    region_name="上海",
                    school_tier="普本",
                    department_name="材料学院",
                    department_name_normalized="材料学院",
                    major_code="085600",
                    major_name="材料与化工",
                    major_name_normalized="材料与化工",
                    study_mode="fulltime",
                    has_history=1,
                    is_long_track=1,
                    reference_link_count=2,
                    min_score_required=320,
                    vacancy_count=2,
                    min_score=320,
                    avg_score=330.0,
                    max_score=340,
                    verification_status="历史统计",
                    title="丁大学材料与化工历史统计",
                    summary="分数要求过高",
                    source_url="https://example.com/broad-filter-too-high",
                    meta_json={},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_broad_filter_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={
            "candidate_score": 280,
            "school_tier": "普通本科",
            "history_backed_only": True,
            "long_track_only": True,
            "page_size": 12,
        },
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert [item["school_name"] for item in payload["items"]] == ["甲大学"]


def test_adjustment_search_broad_query_uses_full_historical_intelligence(client):
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="broad-full-intelligence",
                source_dataset_key="adjustment_stats_2025_full_raw",
                source_type="stats",
                year=2025,
                school_name="深度大学",
                school_name_normalized="深度大学",
                school_code="10005",
                region_name="上海",
                school_tier="211",
                department_name="信息学院",
                department_name_normalized="信息学院",
                major_code="085400",
                major_name="电子信息",
                major_name_normalized="电子信息",
                study_mode="fulltime",
                has_history=1,
                is_long_track=0,
                reference_link_count=2,
                min_score_required=316,
                vacancy_count=2,
                min_score=312,
                avg_score=324.0,
                max_score=336,
                verification_status="历史统计",
                title="深度大学电子信息历史统计",
                summary="用于验证 broad query 卡片走完整画像",
                source_url="https://example.com/broad-full-intelligence",
                meta_json={},
            )
        )
        db.add_all(
            [
                HistoricalAdjustmentProfile(
                    profile_key="broad-profile-1",
                    year=2024,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2024_raw",
                    school_name="深度大学",
                    school_name_normalized="深度大学",
                    school_code="10005",
                    region_name="上海",
                    school_tier="211",
                    department_name="信息学院",
                    department_name_normalized="信息学院",
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=5,
                    vacancy_count=None,
                    initial_score_min=315,
                    initial_score_max=341,
                    min_score=315,
                    avg_score=328.0,
                    max_score=341,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="broad-profile-2",
                    year=2025,
                    source_type="adjustment_stats",
                    source_dataset_key="adjustment_stats_2025_full_raw",
                    school_name="深度大学",
                    school_name_normalized="深度大学",
                    school_code="10005",
                    region_name="上海",
                    school_tier="211",
                    department_name="信息学院",
                    department_name_normalized="信息学院",
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=5,
                    vacancy_count=None,
                    initial_score_min=312,
                    initial_score_max=336,
                    min_score=312,
                    avg_score=324.0,
                    max_score=336,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="broad-profile-3",
                    year=2025,
                    source_type="future_program",
                    source_dataset_key="admission_program_catalog_2026_raw",
                    school_name="深度大学",
                    school_name_normalized="深度大学",
                    school_code="10005",
                    region_name="上海",
                    school_tier="211",
                    department_name="信息学院",
                    department_name_normalized="信息学院",
                    major_code="085400",
                    major_name="电子信息",
                    major_name_normalized="电子信息",
                    study_mode="fulltime",
                    sample_count=3,
                    vacancy_count=3,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={"source_url": "https://example.com/broad-program"},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="broad-profile-4",
                    year=2025,
                    source_type="notice_reference",
                    source_dataset_key="adjustment_announcement_2025_raw",
                    school_name="深度大学",
                    school_name_normalized="深度大学",
                    school_code="10005",
                    region_name="上海",
                    school_tier="211",
                    department_name="信息学院",
                    department_name_normalized="信息学院",
                    major_code=None,
                    major_name=None,
                    major_name_normalized=None,
                    study_mode=None,
                    sample_count=2,
                    vacancy_count=None,
                    min_score=None,
                    avg_score=None,
                    max_score=None,
                    meta_json={"reference_urls": ["https://example.com/broad-history-1", "https://example.com/broad-history-2"]},
                ),
            ]
        )
        db.commit()

    token = _register_and_login(client, "adjustment_broad_full_intelligence_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"candidate_score": 340, "page_size": 10},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["school_name"] == "深度大学"
    assert item["historical_adjustment"]["sample_years"] == [2025]
    assert item["historical_adjustment"]["sample_count"] == 5
    assert item["historical_adjustment"]["min_score"] == 316
    assert item["historical_adjustment"]["future_program_count"] == 3
    assert item["historical_adjustment"]["national_line_year"] == 2026
    assert item["historical_adjustment"]["national_line_major_category"] == "工学"
    assert item["school_intelligence"]["profile_count"] == 4
    assert item["school_intelligence"]["active_years"] == [2024, 2025]
    assert item["school_intelligence"]["future_program_count"] == 3
    assert item["school_intelligence"]["confidence_label"] == "持续关注"
    assert set(item["school_intelligence"]["reference_urls"]) == {
        "https://example.com/broad-history-1",
        "https://example.com/broad-history-2",
        "https://example.com/broad-program",
    }


def test_adjustment_search_year_filter_applies_to_adjustment_content(client):
    for year in (2024, 2025):
        response = client.post(
            "/api/v1/content",
            json={
                "category": "adjustment",
                "title": f"湖北大学 {year} 年调剂公告",
                "body": "用于验证年份筛选只返回对应年份内容。",
                "school_name": "湖北大学",
                "major": "电子信息",
                "region": "湖北",
                "source_type": "crawler",
                "source_url": f"https://example.com/hubu-adjustment-{year}",
                "published_at": f"{year}-04-07T09:34:00Z",
            },
            headers={"X-Admin-Token": "test-admin-token"},
        )
        assert response.status_code == 200

    token = _register_and_login(client, "adjustment_year_content_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北大学", "year": 2024, "page_size": 20},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert payload["items"][0]["adjustment_year"] == 2024
    assert payload["items"][0]["school_name"] == "湖北大学"


def test_adjustment_search_merges_cross_source_records_into_single_entity(client):
    content_response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "湖北大学 材料与化工 公告",
            "body": "同一学校、同一专业、同一年公告来源。",
            "school_name": "湖北大学",
            "major": "材料与化工",
            "region": "湖北",
            "source_type": "crawler",
            "source_url": "https://example.com/hubu-material-notice",
            "published_at": "2025-04-07T09:34:00Z",
            "extra": {
                "adjustment_meta": {
                    "major_codes": ["085600"],
                    "study_modes": ["fulltime"],
                    "vacancy_count": 1,
                }
            },
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert content_response.status_code == 200

    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="hubu-material-stats",
                source_dataset_key="adjustment_stats_2025_full_raw",
                source_type="stats",
                year=2025,
                school_name="湖北大学",
                school_name_normalized="湖北大学",
                school_code="10512",
                region_name="湖北省",
                school_tier="普本",
                department_name=None,
                department_name_normalized=None,
                major_code="085600",
                major_name="材料与化工",
                major_name_normalized="材料与化工",
                study_mode="fulltime",
                vacancy_count=219,
                min_score=260,
                avg_score=288.2,
                max_score=353,
                initial_score_min=260,
                initial_score_max=353,
                adjustment_score_min=260,
                adjustment_score_max=260,
                verification_status="历史统计",
                title="湖北大学 材料与化工 历史统计",
                summary="2025 年历史调剂统计 · 湖北 · 历史统计 · 计划 219 · 调剂 260",
                source_url="https://example.com/hubu-material-stats",
                published_at=datetime.fromisoformat("2025-04-07T09:34:00+00:00"),
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_source_merge_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "湖北大学", "year": 2025, "page_size": 20},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["school_name"] == "湖北大学"
    assert item["major"] == "材料与化工"
    assert item["adjustment_year"] == 2025
    assert item["merged_count"] >= 2
    assert item["title"] == "湖北大学 材料与化工 调剂信息"
    assert item["adjustment_vacancy_count"] is None
    assert "计划 219" not in (item["summary"] or "")


def test_adjustment_search_keeps_missing_department_item_separate_when_vacancy_count_differs(client):
    content_response = client.post(
        "/api/v1/content",
        json={
            "category": "adjustment",
            "title": "福州大学 教育管理 调剂公告",
            "body": "同校同专业但缺少院系，且人数未知。",
            "school_name": "福州大学",
            "major": "教育管理",
            "region": "福建",
            "source_type": "crawler",
            "source_url": "https://example.com/fzu-edu-notice-no-count",
            "published_at": "2025-04-07T09:34:00Z",
            "extra": {
                "adjustment_meta": {
                    "major_codes": ["045101"],
                    "study_modes": ["fulltime"],
                }
            },
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert content_response.status_code == 200

    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="fzu-edu-stats-with-count",
                source_dataset_key="adjustment_stats_2025_full_raw",
                source_type="stats",
                year=2025,
                school_name="福州大学",
                school_name_normalized="福州大学",
                school_code="10386",
                region_name="福建",
                school_tier="211",
                department_name="经济与管理学院",
                department_name_normalized="经济与管理学院",
                major_code="045101",
                major_name="教育管理",
                major_name_normalized="教育管理",
                study_mode="fulltime",
                vacancy_count=3,
                min_score=351,
                avg_score=360,
                max_score=368,
                verification_status="历史统计",
                title="福州大学 教育管理 历史统计",
                summary="2025 年历史调剂统计 · 样本 3",
                source_url="https://example.com/fzu-edu-stats-with-count",
                published_at=datetime.fromisoformat("2025-04-07T09:34:00+00:00"),
                meta_json={},
            )
        )
        db.commit()

    token = _register_and_login(client, "adjustment_source_merge_count_guard_user")
    search = client.post(
        "/api/v1/search/adjustments",
        json={"school_name": "福州大学", "year": 2025, "page_size": 20},
        headers={"X-User-Token": token},
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 2
    department_names = {item["department_name"] for item in payload["items"]}
    assert department_names == {None, "经济与管理学院"}


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


def test_search_announcements_matches_department_name_and_tags_from_extra(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "武汉大学关于复试安排的说明",
            "body": "请考生按要求完成复试准备。",
            "summary": "公告正文未直接写出学院名和标签词。",
            "school_name": "武汉大学",
            "source_type": "crawler",
            "source_url": "https://example.com/whu-announcement-extra-search",
            "extra": {
                "department_name": "数学与统计学院",
                "tags": ["复试线", "报名须知"],
            },
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200

    department_search = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "武汉大学", "keywords": "统计学院"},
    )
    assert department_search.status_code == 200
    department_payload = department_search.json()
    assert department_payload["total"] == 1
    assert department_payload["items"][0]["department_name"] == "数学与统计学院"

    tag_search = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "武汉大学", "keywords": "复试线"},
    )
    assert tag_search.status_code == 200
    tag_payload = tag_search.json()
    assert tag_payload["total"] == 1
    assert tag_payload["items"][0]["tags"] == ["复试线", "报名须知"]


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


def test_content_upsert_generates_summary_from_body_when_missing(client):
    response = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "河海大学计算机学院复试公告",
            "body": "河海大学 计算机与软件学院 发布 2026 年硕士研究生复试安排。\n\n请考生按时完成资格审查，并提前准备面试材料。",
            "school_name": "河海大学",
            "source_type": "manual",
            "source_url": "https://example.com/manual-summary-fallback",
        },
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "created"

    search = client.post("/api/v1/search/announcements", json={"school_name": "河海大学"})
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    assert (
        payload["items"][0]["summary"]
        == "河海大学 计算机与软件学院 发布 2026 年硕士研究生复试安排。 请考生按时完成资格审查，并提前准备面试材料。"
    )


def test_search_announcements_recovers_stale_content_fields_from_body(client):
    with SessionLocal() as db:
        school = School(name="摘要修复大学", aliases=[])
        db.add(school)
        db.flush()
        db.add(
            Content(
                category="announcement",
                title="3019.htm",
                body=(
                    "摘要修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知-摘要修复大学研究生招生信息网 "
                    "摘要修复大学 | 摘要修复大学研究生院 网站首页 发布时间：2024-08-30 "
                    "根据《摘要修复大学同等学力人员申请硕士学位工作实施办法》的相关规定，"
                    "现就2024年同等学力申硕第一批次学员现场确认等事宜通知如下。"
                ),
                summary=None,
                school_id=school.id,
                source_url="https://example.com/stale/3019.htm",
                source_type="crawler",
                published_at=None,
                region=None,
                major=None,
                extra={"tags": ["招生简章", "同等学力"]},
            )
        )
        db.commit()

    response = client.post(
        "/api/v1/search/announcements",
        json={"school_name": "摘要修复大学", "keywords": "现场确认暨开学典礼"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["title"] == "摘要修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知"
    assert item["summary"].startswith("根据《摘要修复大学同等学力人员申请硕士学位工作实施办法》")
    assert item["published_at"].startswith("2024-08-30")


def test_repair_stale_announcement_script_uses_snapshots_before_refetch():
    source_url = "https://example.com/stale/snapshot-3019.htm"
    with SessionLocal() as db:
        school = School(name="快照修复大学", aliases=[])
        db.add(school)
        db.flush()

        content = Content(
            category="announcement",
            title="3019.htm",
            body="详情请查看原文",
            summary=None,
            school_id=school.id,
            source_url=source_url,
            source_type="crawler",
            published_at=None,
            region=None,
            major=None,
            extra={},
        )
        db.add(content)
        db.flush()
        db.add(
            ContentSnapshot(
                content_id=content.id,
                raw_html=(
                    "<html><head><title>快照修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知</title></head>"
                    "<body><article><h1>快照修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知</h1>"
                    "<div>发布时间：2024-08-30</div>"
                    "<p>根据《快照修复大学同等学力人员申请硕士学位工作实施办法》的相关规定，"
                    "现就2024年同等学力申硕第一批次学员现场确认等事宜通知如下。</p>"
                    "</article></body></html>"
                ),
                raw_text=(
                    "快照修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知 "
                    "发布时间：2024-08-30 根据《快照修复大学同等学力人员申请硕士学位工作实施办法》的相关规定，"
                    "现就2024年同等学力申硕第一批次学员现场确认等事宜通知如下。"
                ),
                snapshot_meta={},
            )
        )
        db.commit()
        db.refresh(content)

        changed_fields = _repair_row_by_snapshot(content)
        db.commit()
        repaired = db.query(Content).filter(Content.source_url == source_url).one()

    assert "title" in changed_fields
    assert "summary" in changed_fields
    assert "published_at" in changed_fields
    assert repaired.title == "快照修复大学关于2024年同等学力申硕学员现场确认暨开学典礼的通知"
    assert repaired.summary.startswith("根据《快照修复大学同等学力人员申请硕士学位工作实施办法》")
    assert repaired.published_at.isoformat().startswith("2024-08-30")


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


def test_adjustment_detail_returns_structured_opportunity_payload():
    with SessionLocal() as db:
        db.add_all(
            [
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
                ),
                MentorEvaluation(
                    review_key="mentor-detail-2",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="山东大学",
                    school_name_normalized="山东大学",
                    department_name="文学院",
                    department_name_normalized="文学院",
                    mentor_name="王老师",
                    mentor_name_normalized="王老师",
                    review_text="文学院导师评价。",
                    review_tags=["管理严格"],
                    risk_level="warning",
                    meta_json={},
                ),
                MentorEvaluation(
                    review_key="mentor-detail-3",
                    source_dataset_key="mentor_reviews_raw",
                    school_name="山东大学",
                    school_name_normalized="山东大学",
                    department_name=None,
                    department_name_normalized=None,
                    mentor_name="周老师",
                    mentor_name_normalized="周老师",
                    review_text="校级混合评价，整体口碑尚可。",
                    review_tags=["口碑尚可"],
                    risk_level="positive",
                    meta_json={},
                ),
            ]
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
                meta_json={"reference_urls": ["https://example.com/sdu-reference", "https://example.com/sdu-reference/"]},
            )
        )
        db.add_all(
            [
                HistoricalAdjustmentProfile(
                    profile_key="profile-detail-1",
                    year=2025,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2025_raw",
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
                    sample_count=3,
                    vacancy_count=None,
                    initial_score_min=360,
                    initial_score_max=389,
                    adjustment_score_min=78,
                    adjustment_score_max=85,
                    min_score=360,
                    avg_score=374.5,
                    max_score=389,
                    meta_json={},
                ),
                HistoricalAdjustmentProfile(
                    profile_key="profile-detail-2",
                    year=2025,
                    source_type="landing",
                    source_dataset_key="adjustment_landing_2025_raw",
                    school_name="山东大学",
                    school_name_normalized="山东大学",
                    school_code="10422",
                    region_name="山东",
                    school_tier="985",
                    department_name="文学院",
                    department_name_normalized="文学院",
                    major_code="055101",
                    major_name="英语笔译",
                    major_name_normalized="英语笔译",
                    study_mode="fulltime",
                    sample_count=2,
                    vacancy_count=None,
                    initial_score_min=330,
                    initial_score_max=340,
                    adjustment_score_min=70,
                    adjustment_score_max=74,
                    min_score=330,
                    avg_score=335,
                    max_score=340,
                    meta_json={},
                ),
            ]
        )
        db.commit()
        opportunity = (
            db.query(AdjustmentOpportunity)
            .filter(AdjustmentOpportunity.opportunity_key == "opp-detail-1")
            .one()
        )
        payload = _build_adjustment_detail_from_opportunity(db, opportunity).model_dump()
    assert payload["item_kind"] == "opportunity"
    assert payload["school_name"] == "山东大学"
    assert payload["links"][0]["url"] == "https://example.com/sdu-adjustment"
    assert payload["historical_adjustment"]["initial_score_min"] == 360
    assert payload["historical_adjustment"]["initial_score_max"] == 389
    assert payload["mentor_radar"]["review_count"] == 3
    assert payload["mentor_radar"]["warning_count"] == 2
    assert payload["mentor_department_radar"]["review_count"] == 1
    assert payload["mentor_school_radar"]["review_count"] == 3
    assert {review["mentor_name"] for review in payload["mentor_department_reviews"]} == {"李老师"}
    assert {review["mentor_name"] for review in payload["mentor_school_reviews"]} == {"李老师", "王老师", "周老师"}
    assert payload["mentor_department_reviews"][0]["mentor_name"] == "李老师"
    assert "延毕风险" in payload["mentor_department_reviews"][0]["review_text"]
    assert "<br>" not in payload["mentor_department_reviews"][0]["review_text"]
    urls = [entry["url"] for entry in payload["links"]]
    assert urls.count("https://example.com/sdu-reference") == 1


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


def test_adjustment_detail_hides_historical_sample_count_in_body():
    with SessionLocal() as db:
        db.add(
            AdjustmentOpportunity(
                opportunity_key="opp-detail-historical-body",
                source_dataset_key="adjustment_stats_2023_2025_raw",
                year=2025,
                source_type="stats",
                school_name="湖北大学",
                school_name_normalized="湖北大学",
                department_name="化学化工学院",
                department_name_normalized="化学化工学院",
                major_code="085600",
                major_name="材料与化工",
                major_name_normalized="材料与化工",
                school_tier="普本",
                verification_status="历史统计",
                title="湖北大学 材料与化工 历史统计",
                summary="2025 年历史调剂统计 · 化学化工学院 · 样本 41 · 初试 261-353",
            )
        )
        db.commit()
        opportunity = (
            db.query(AdjustmentOpportunity)
            .filter(AdjustmentOpportunity.opportunity_key == "opp-detail-historical-body")
            .one()
        )
        payload = _build_adjustment_detail_from_opportunity(db, opportunity).model_dump()
    assert payload["vacancy_count"] is None
    assert payload["body"] == "2025 年历史调剂统计 · 化学化工学院 · 初试 261-353"
