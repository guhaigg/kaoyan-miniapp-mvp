from app.db import SessionLocal
from app.models import HistoricalAdjustmentProfile
from app.services.historical_intelligence import normalize_major_name, normalize_school_name


def _insert_profile(
    *,
    year: int,
    major_code: str,
    school_name: str,
    sample_count: int,
    initial_min: int,
    initial_max: int,
    region_name: str = "湖北省",
) -> None:
    with SessionLocal() as db:
        db.add(
            HistoricalAdjustmentProfile(
                profile_key=f"profile:{year}:{school_name}:{major_code}:{sample_count}:{initial_min}:{initial_max}",
                year=year,
                source_type="adjustment_stats",
                source_dataset_key=f"dataset:{year}",
                school_name=school_name,
                school_name_normalized=normalize_school_name(school_name),
                region_name=region_name,
                major_code=major_code,
                major_name="材料与化工" if major_code.startswith("08") else "公共管理",
                major_name_normalized=normalize_major_name("材料与化工" if major_code.startswith("08") else "公共管理"),
                sample_count=sample_count,
                initial_score_min=initial_min,
                initial_score_max=initial_max,
            )
        )
        db.commit()


def test_radar_predict_blends_national_lines_and_historical_profiles(client):
    _insert_profile(year=2024, major_code="085600", school_name="湖北大学", sample_count=16, initial_min=296, initial_max=306)
    _insert_profile(year=2025, major_code="085600", school_name="湘潭大学", sample_count=12, initial_min=282, initial_max=288)

    response = client.post(
        "/api/v1/radar/predict",
        json={"score": 315, "category": "工学(不含照顾专业)", "area": "A"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category_key"] == "08"
    assert payload["category_label"] == "工学"
    assert payload["national_line_year"] == 2026
    assert payload["national_line_a"] == 264
    assert payload["comparison_line"] == 264
    assert payload["historical_sample_count"] == 28
    assert payload["historical_group_count"] == 2
    assert payload["historical_benchmark_score"] is not None
    assert payload["win_rate"] >= 70
    assert "同门类历史样本" in payload["advice"]


def test_radar_predict_supports_major_category_code_and_b_area(client):
    response = client.post(
        "/api/v1/radar/predict",
        json={"score": 250, "category": "08", "area": "B"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["category_key"] == "08"
    assert payload["area"] == "B"
    assert payload["comparison_line"] == 254
    assert payload["delta_to_comparison_line"] == -4
    assert payload["level"] in {"danger", "warning"}


def test_radar_predict_rejects_unknown_category(client):
    response = client.post(
        "/api/v1/radar/predict",
        json={"score": 315, "category": "星际航行学"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported category"
