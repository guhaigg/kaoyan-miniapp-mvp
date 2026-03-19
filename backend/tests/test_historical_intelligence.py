from pathlib import Path

from openpyxl import Workbook

from app.db import SessionLocal
from app.services.historical_intelligence import (
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


def test_build_historical_profiles_and_mentor_evaluations_from_archives(tmp_path):
    stats_path = tmp_path / "stats25.xlsx"
    landing24_path = tmp_path / "landing24.xlsx"
    landing25_path = tmp_path / "landing25.xlsx"
    program_path = tmp_path / "program2026.xlsx"
    mentor_path = tmp_path / "mentor.xlsx"
    snapshot25_path = tmp_path / "25年4月9日20时03分07秒调剂信息汇总.xlsx"
    snapshot24_path = tmp_path / "24年4月14日10时55分调剂信息汇总.xlsx"

    _write_xlsx(
        stats_path,
        "调剂统计（含平均分）",
        ["专业", "学习形式", "推荐院校", "25调剂人数", "25调剂录取最低分", "25调剂平均分"],
        [["(085400)电子信息", "非全日制", "(10001)XX大学", 3, 318, 326.5]],
    )
    _write_xlsx(
        landing24_path,
        "总表",
        ["调剂学校", "地区", "院校类别", "所属学院", "专业代码", "专业名称", "初试总分"],
        [["(10001)XX大学", "(31)上海市", "211", "信息学院", 85400, "电子信息", 321]],
    )
    _write_xlsx(
        landing25_path,
        "总表",
        ["学校", "地区", "院校类别", "所属学院", "专业", "学习形式", "初试总分"],
        [["(10001)XX大学", "(31)上海市", "211", "信息学院", "(085400)电子信息", "非全日制", 335]],
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
        [["XX大学", "信息学院", "张老师", "评价1：好老师；评价2：不强制延毕。"]],
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
        db.commit()

        profiles = build_historical_profiles_from_archives(db)
        mentors = build_mentor_evaluations_from_archives(db)
        timings = build_release_timing_profiles_from_archives(db)

    assert len(profiles) == 5
    stats_row = next(row for row in profiles if row["source_type"] == "adjustment_stats")
    assert stats_row["major_code"] == "085400"
    assert stats_row["avg_score"] == 326.5

    landing_rows = [row for row in profiles if row["source_type"] == "landing"]
    assert {row["year"] for row in landing_rows} == {2024, 2025}
    notice_reference = next(row for row in profiles if row["source_type"] == "notice_reference")
    assert notice_reference["meta_json"]["top_source_url"] == "https://example.com/1"
    assert notice_reference["meta_json"]["reference_urls"] == [
        "https://example.com/1",
        "https://example.com/2",
    ]
    assert len(mentors) == 1
    assert mentors[0]["risk_level"] == "warning"
    assert "好老师" in mentors[0]["review_tags"]
    assert len(timings) == 1
    assert timings[0]["school_name_normalized"] == "XX大学"
    assert timings[0]["peak_hour"] == 20
    assert timings[0]["window_start_md"] == "04-09"
    assert timings[0]["window_end_md"] == "04-14"
