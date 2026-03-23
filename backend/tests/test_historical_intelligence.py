from pathlib import Path

from openpyxl import Workbook

import scripts.backfill_adjustment_search_facets as backfill_adjustment_search_facets
from app.db import SessionLocal
from app.services.historical_intelligence import (
    _annotate_adjustment_search_facets,
    build_adjustment_opportunities_from_archives,
    build_historical_profiles_from_archives,
    build_release_timing_profiles_from_archives,
    build_mentor_evaluations_from_archives,
)
from app.services.raw_dataset_archive import archive_dataset_file


def _write_xlsx(path: Path, sheet_name: str, header: list[str], rows: list[list[object]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet.append(header)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def test_annotate_adjustment_search_facets_converts_score_floor_to_latest_national_line_year():
    rows = [
        {
            "id": "row-2025-engineering-a",
            "school_name_normalized": "精确大学",
            "source_type": "stats",
            "year": 2025,
            "school_tier": "普本",
            "department_name": None,
            "department_name_normalized": None,
            "major_code": "085400",
            "major_name": "电子信息",
            "major_name_normalized": "电子信息",
            "study_mode": "fulltime",
            "source_url": None,
            "meta_json": {},
            "region_name": "上海",
            "initial_score_min": 260,
            "adjustment_score_min": None,
            "min_score": 260,
        }
    ]

    annotated = _annotate_adjustment_search_facets(rows)

    assert annotated[0]["min_score_required"] == 264
    assert annotated[0]["has_history"] == 1
    assert annotated[0]["is_long_track"] == 0


def test_fast_backfill_strategy_is_exact_alias(monkeypatch):
    called = {"value": False}

    def fake_run_exact_backfill() -> int:
        called["value"] = True
        return 7

    monkeypatch.setattr(backfill_adjustment_search_facets, "_run_exact_backfill", fake_run_exact_backfill)

    assert backfill_adjustment_search_facets._run_fast_backfill() == 7
    assert called["value"] is True


def test_build_historical_profiles_and_mentor_evaluations_from_archives(tmp_path):
    stats_path = tmp_path / "stats25.xlsx"
    stats2325_path = tmp_path / "23-25调剂统计数据.xlsx"
    balance24_path = tmp_path / "24.xlsx"
    landing24_path = tmp_path / "landing24.xlsx"
    landing25_path = tmp_path / "landing25.xlsx"
    program_path = tmp_path / "program2026.xlsx"
    mentor_path = tmp_path / "mentor.xlsx"
    snapshot25_path = tmp_path / "25年4月9日20时03分07秒调剂信息汇总.xlsx"
    snapshot24_path = tmp_path / "24年4月14日10时55分调剂信息汇总.xlsx"
    announcement25_path = tmp_path / "2025年调剂信息公告.xlsx"

    _write_xlsx(
        stats_path,
        "调剂统计（含平均分）",
        ["专业", "学习形式", "推荐院校", "25调剂人数", "25调剂录取最低分", "25调剂平均分"],
        [["(085400)电子信息", "非全日制", "(10001)XX大学", 3, 318, 326.5]],
    )
    _write_xlsx(
        balance24_path,
        "Sheet1",
        ["采集时间", "招生单位", " 院系所", " 专业", " 学习方式", " 计划余额", " 总分", " 调剂说明"],
        [["2024-04-08 23-14-23", "(10001)XX大学", "(001)信息学院", "(085400)电子信息", "非全日制", 5, "国家线", "补充说明"]],
    )
    _write_xlsx(
        landing24_path,
        "总表",
        ["调剂学校", "地区", "院校类别", "所属学院", "专业代码", "专业名称", "初试总分", "调剂成绩"],
        [["(10001)XX大学", "(31)上海市", "211", "信息学院", 85400, "电子信息", 321, 78]],
    )
    _write_xlsx(
        landing25_path,
        "总表",
        ["学校", "地区", "院校类别", "所属学院", "专业", "学习形式", "初试总分", "调剂成绩"],
        [
            ["(10001)XX大学", "(31)上海市", "211", "信息学院", "(085400)电子信息", "非全日制", 335, 82],
            ["(10001)XX大学", "(31)上海市", "211", None, "(085400)电子信息", "非全日制", 338, 81],
            ["(10001)XX大学", "(31)上海市", "211", "人工智能学院", "(085400)电子信息", "全日制", 342, 80],
        ],
    )
    _write_xlsx(
        program_path,
        "Sheet1",
        ["专业代码", "专业名称", "院校名称", "省份", "名额", "发布时间", "链接"],
        [[85601, "材料工程", "XX大学", "上海", 2, "2026-03-13 11:52:00", "https://example.com/program"]],
    )
    _write_xlsx(
        mentor_path,
        "Sheet1",
        ["学校", "学院", "姓名", "评价"],
        [["XX大学", "XX大学信息学院（电子信息）", "张老师", "评价1：好老师；评价2：不强制延毕。"]],
    )
    _write_xlsx(
        snapshot25_path,
        "Sheet1",
        ["专业代码", "专业名称", "学校", "计划人数", "最新时间", "验证状态", "原始网址", "年份"],
        [
            ["085400", "电子信息", "XX大学", "4", "2025/4/9 20:03:00", "官网", "https://example.com/1", 2025],
            ["085400", "电子信息", "XX大学", "2", "2025/4/10 20:08:00", "官网", "https://example.com/2", 2025],
        ],
    )
    _write_xlsx(
        snapshot24_path,
        "Sheet1",
        ["余额", "大学", "学校代码", "学院", "学院代码", "专业", "专业代码", "研究方向", "方向代码", "学习形式", "要求", "距离开网已过时间（分）", "备注"],
        [[1, "XX大学", 10001, "信息学院", 1, "(专业学位)电子信息", "085400", "不区分", "00", 1, "要求", 120, "备注"]],
    )
    _write_xlsx(
        announcement25_path,
        "Sheet1",
        ["学校", "学院", "专业代码", "专业名称", "计划人数", "最新时间", "验证状态", "原始网址", "年份", "标题", "备注"],
        [["XX大学", "信息学院", "085400", "电子信息", 3, "2025/4/9 20:03:00", "官网", "https://example.com/1", 2025, "XX大学电子信息调剂公告", "补充说明"]],
    )
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "23-24-25考研调剂数据-（考研调剂必看）"
    worksheet.append(["本内容是23/24/25年全国院校全专业具体调剂数据", "Unnamed: 1", "Unnamed: 2", "Unnamed: 3", "Unnamed: 4", "Unnamed: 5", "Unnamed: 6", "Unnamed: 7", "Unnamed: 8", "    ", "Unnamed: 10", "Unnamed: 11"])
    worksheet.append(["年份", "学校", "地区", "院校类别", "所属学院", "专业代码", "专业名称", "学习形式", "考生编号", "初试总分", "调剂成绩", "一志愿报考院校", "备注"])
    worksheet.append([2023, "(10001)XX大学", "(31)上海市", "211", "信息学院", "085400", "电子信息", "非全日制", "101", 330, 79, "复旦大学", None])
    workbook.save(stats2325_path)

    with SessionLocal() as db:
        archive_dataset_file(
            db,
            dataset_key="adjustment_stats_2025_full_raw",
            title="stats",
            dataset_type="adjustment_stats",
            input_path=stats_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_stats_2023_2025_raw",
            title="stats2325",
            dataset_type="adjustment_stats",
            input_path=stats2325_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_opportunity_2024_raw",
            title="balance24",
            dataset_type="adjustment_balance",
            input_path=balance24_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_landing_2024_raw",
            title="landing24",
            dataset_type="adjustment_landing",
            input_path=landing24_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_landing_2025_raw",
            title="landing25",
            dataset_type="adjustment_landing",
            input_path=landing25_path,
        )
        archive_dataset_file(
            db,
            dataset_key="admission_program_catalog_2026_raw",
            title="program2026",
            dataset_type="program_catalog",
            input_path=program_path,
        )
        archive_dataset_file(
            db,
            dataset_key="mentor_reviews_raw",
            title="mentor",
            dataset_type="mentor_reviews",
            input_path=mentor_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_snapshot_2025_0409_raw",
            title="snapshot25",
            dataset_type="adjustment_snapshot",
            input_path=snapshot25_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_snapshot_2024_0414_raw",
            title="snapshot24",
            dataset_type="adjustment_snapshot",
            input_path=snapshot24_path,
        )
        archive_dataset_file(
            db,
            dataset_key="adjustment_announcement_2025_raw",
            title="announcement25",
            dataset_type="adjustment_notice",
            input_path=announcement25_path,
        )
        db.commit()

        opportunities = build_adjustment_opportunities_from_archives(db)
        profiles = build_historical_profiles_from_archives(db)
        mentors = build_mentor_evaluations_from_archives(db)
        timings = build_release_timing_profiles_from_archives(db)

    assert len(opportunities) == 12
    snapshot_row = next(row for row in opportunities if row["source_type"] == "snapshot" and row["year"] == 2025)
    assert snapshot_row["source_url"] == "https://example.com/1"
    assert snapshot_row["vacancy_count"] == 4
    adjustment_notice_row = next(row for row in opportunities if row["source_type"] == "adjustment_notice")
    assert adjustment_notice_row["source_url"] == "https://example.com/1"
    stats_opportunity = next(
        row for row in opportunities if row["source_type"] == "stats" and row["source_dataset_key"] == "adjustment_stats_2025_full_raw"
    )
    assert stats_opportunity["min_score"] == 318
    assert stats_opportunity["min_score_required"] == 321
    balance_opportunity = next(row for row in opportunities if row["source_type"] == "balance")
    assert balance_opportunity["vacancy_count"] == 5
    landing_opportunities = [row for row in opportunities if row["source_type"] == "landing"]
    assert {row["year"] for row in landing_opportunities} == {2024, 2025}
    stats2325_opportunity = next(row for row in opportunities if row["source_dataset_key"] == "adjustment_stats_2023_2025_raw")
    assert stats2325_opportunity["year"] == 2023
    assert stats2325_opportunity["avg_score"] == 330
    assert len(profiles) == 7
    stats_row = next(row for row in profiles if row["source_type"] == "adjustment_stats")
    assert stats_row["major_code"] == "085400"
    assert stats_row["avg_score"] == 326.5
    assert stats_row["adjustment_score_min"] == 318

    landing_rows = [row for row in profiles if row["source_type"] == "landing"]
    assert {row["year"] for row in landing_rows} == {2024, 2025}
    assert all(row["city_name"] == "上海" for row in landing_rows)
    assert all(row["initial_score_min"] is not None for row in landing_rows)
    assert all(row["adjustment_score_min"] is not None for row in landing_rows)
    landing_2025_info = next(
        row
        for row in landing_rows
        if row["year"] == 2025 and row["department_name_normalized"] == "信息学院"
    )
    assert landing_2025_info["sample_count"] == 2
    assert landing_2025_info["initial_score_min"] == 335
    assert landing_2025_info["initial_score_max"] == 338
    landing_2025_ai = next(
        row
        for row in landing_rows
        if row["year"] == 2025 and row["department_name_normalized"] == "人工智能学院"
    )
    assert landing_2025_ai["sample_count"] == 1
    assert landing_2025_ai["initial_score_min"] == 342
    legacy_stats_row = next(row for row in profiles if row["source_dataset_key"] == "adjustment_stats_2023_2025_raw")
    assert legacy_stats_row["year"] == 2023
    assert legacy_stats_row["initial_score_min"] == 330
    assert legacy_stats_row["adjustment_score_min"] == 79
    notice_reference = next(row for row in profiles if row["source_type"] == "notice_reference")
    assert notice_reference["meta_json"]["top_source_url"] == "https://example.com/1"
    assert "https://example.com/1" in notice_reference["meta_json"]["reference_urls"]
    assert len(mentors) == 1
    assert mentors[0]["department_name_normalized"] == "信息学院"
    assert mentors[0]["risk_level"] == "warning"
    assert "好老师" in mentors[0]["review_tags"]
    assert len(timings) == 1
    assert timings[0]["school_name_normalized"] == "XX大学"
    assert timings[0]["peak_hour"] == 20
    assert timings[0]["window_start_md"] == "04-09"
    assert timings[0]["window_end_md"] == "04-14"
