from pathlib import Path

from openpyxl import Workbook

from app.db import SessionLocal
from app.services.raw_dataset_archive import archive_dataset_file


def _portal_login(client, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap_admin_headers(client, username: str = "portal_admin", password: str = "StrongPass123") -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "nickname": f"{username}-nick"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(
        f"/api/v1/admin/users/{user_id}/promote",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert promote_response.status_code == 200

    access_token = _portal_login(client, username, password)
    return {"X-User-Token": access_token}


def test_archive_dataset_file_persists_workbook_metadata(tmp_path: Path):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["学校", "专业", "人数"])
    worksheet.append(["测试大学", "电子信息", 12])
    worksheet.append(["测试大学", "材料与化工", 8])
    file_path = tmp_path / "sample.xlsx"
    workbook.save(file_path)

    with SessionLocal() as db:
        row = archive_dataset_file(
            db,
            dataset_key="test_adjustment_sheet",
            title="测试调剂表",
            dataset_type="adjustment_snapshot",
            input_path=file_path,
            summary_json={"total_rows": 2},
            notes="unit test",
        )
        db.commit()
        assert row.dataset_key == "test_adjustment_sheet"
        assert row.source_filename == "sample.xlsx"
        assert row.workbook_format == "xlsx"
        assert row.total_rows == 3
        assert row.total_columns == 3
        assert row.header_row == ["学校", "专业", "人数"]
        assert row.preview_rows[0][0] == "测试大学"
        assert row.file_size_bytes > 0
        assert row.raw_file_payload


def test_admin_can_list_raw_datasets(client, tmp_path: Path):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["学校", "学院"])
    worksheet.append(["样例大学", "计算机学院"])
    file_path = tmp_path / "admin-sample.xlsx"
    workbook.save(file_path)

    with SessionLocal() as db:
        archive_dataset_file(
            db,
            dataset_key="admin_test_dataset",
            title="管理员查看测试数据",
            dataset_type="raw_excel",
            input_path=file_path,
            summary_json={"source": "test"},
        )
        db.commit()

    admin_headers = _bootstrap_admin_headers(client, "portal_admin_datasets")
    response = client.get("/api/v1/admin/raw-datasets", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    matched = next(item for item in payload["items"] if item["dataset_key"] == "admin_test_dataset")
    assert matched["title"] == "管理员查看测试数据"
    assert matched["workbook_format"] == "xlsx"
    assert matched["header_row"] == ["学校", "学院"]
