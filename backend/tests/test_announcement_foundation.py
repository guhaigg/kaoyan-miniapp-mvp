from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import httpx

from app.services import announcement_foundation
from app.services.canonical_scope_seeds import (
    _announcement_department_seed_registry,
    _announcement_school_seed_registry,
    get_announcement_department_seed,
    get_announcement_school_seed,
)

def _temp_dir() -> Path:
    root = Path("backend/tests/.tmp")
    root.mkdir(parents=True, exist_ok=True)
    path = root.resolve() / f"announcement-foundation-{uuid.uuid4().hex}"
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_enrich_chsi_school_entry_extracts_seed_and_category_urls(monkeypatch):
    school = {
        "school_code": "1001",
        "school_name": "Example University",
        "chsi_school_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001.dhtml",
        "source_meta": {"source_type": "chsi_school_catalog"},
    }
    detail_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001,categoryId-481347.dhtml">院系设置</a>
      <a href="/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml">专业介绍</a>
      <a href="/sch/viewBulletin--infoId-5001,categoryId-481379,schId-1001,mindex-12.dhtml">Example University研究生招生信息网</a>
    </body></html>
    """
    bulletin_html = '<html><body><a href="https://yz.example.edu.cn/">graduate admissions</a></body></html>'
    monkeypatch.setattr(
        announcement_foundation,
        "_fetch_text",
        lambda url, timeout=20: detail_html if "schoolInfo" in url else bulletin_html,
    )

    enriched = announcement_foundation.enrich_chsi_school_entry(school)

    assert enriched["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
    assert enriched["source_meta"]["department_page_url"].endswith("categoryId-481347.dhtml")
    assert enriched["source_meta"]["major_page_url"].endswith("categoryId-692157514.dhtml")


def test_merge_chsi_school_catalog_writes_final_snapshot(tmp_path):
    paths = announcement_foundation.foundation_paths(tmp_path)
    merged = announcement_foundation.merge_chsi_school_catalog(
        [
            {
                "school_code": "1001",
                "school_name": "Example University",
                "source_meta": {"source_type": "chsi_school_catalog"},
            },
            {
                "school_code": "1002",
                "school_name": "Other University",
                "source_meta": {"source_type": "chsi_school_catalog"},
            },
        ],
        [
            {
                "school_code": "9999",
                "school_name": "Unmatched University",
                "source_meta": {"seed_hint_urls": ["https://unmatched.example.edu.cn/"]},
            },
            {
                "school_code": "1002",
                "school_name": "Other University",
                "source_meta": {
                    "seed_hint_urls": ["https://other.example.edu.cn/"],
                    "major_page_url": "https://yz.chsi.com.cn/sch/listYzZyjs--schId-1002,categoryId-692157514.dhtml",
                },
            },
            {
                "school_code": "1001",
                "school_name": "Example University",
                "source_meta": {
                    "seed_hint_urls": ["https://example.edu.cn/"],
                    "department_page_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001,categoryId-481347.dhtml",
                },
            },
        ],
        paths=paths,
    )

    assert [item["school_code"] for item in merged] == ["1001", "1002"]
    assert merged[0]["source_meta"]["seed_hint_urls"] == ["https://example.edu.cn/"]
    assert merged[0]["source_meta"]["department_page_url"].endswith("categoryId-481347.dhtml")
    assert merged[1]["source_meta"]["seed_hint_urls"] == ["https://other.example.edu.cn/"]
    assert merged[1]["source_meta"]["major_page_url"].endswith("categoryId-692157514.dhtml")
    assert json.loads(paths.school_catalog.read_text(encoding="utf-8"))[0]["school_code"] == "1001"


def test_enrich_school_catalog_snapshot_writes_enriched_snapshot(tmp_path, monkeypatch):
    paths = announcement_foundation.foundation_paths(tmp_path)
    school = {
        "school_code": "1001",
        "school_name": "Example University",
        "chsi_school_url": "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001.dhtml",
        "source_meta": {"source_type": "chsi_school_catalog"},
    }
    detail_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001,categoryId-481347.dhtml">院系设置</a>
      <a href="/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml">专业介绍</a>
      <a href="/sch/viewBulletin--infoId-5001,categoryId-481379,schId-1001,mindex-12.dhtml">Example University研究生招生信息网</a>
    </body></html>
    """
    bulletin_html = '<html><body><a href="https://yz.example.edu.cn/">graduate admissions</a></body></html>'
    monkeypatch.setattr(
        announcement_foundation,
        "_fetch_text",
        lambda url, timeout=20: detail_html if "schoolInfo" in url else bulletin_html,
    )

    enriched = announcement_foundation.enrich_school_catalog_snapshot([school], paths=paths)

    assert enriched[0]["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]
    assert json.loads(paths.school_catalog.read_text(encoding="utf-8"))[0]["school_code"] == "1001"


def test_build_department_candidates_skips_department_page_timeouts(tmp_path, monkeypatch):
    paths = announcement_foundation.foundation_paths(tmp_path)
    schools = [
        {
            "school_code": "1001",
            "school_name": "Healthy University",
            "source_meta": {
                "department_page_url": "https://healthy.example.edu.cn/departments/",
            },
        },
        {
            "school_code": "1002",
            "school_name": "Timeout University",
            "source_meta": {
                "department_page_url": "https://timeout.example.edu.cn/departments/",
            },
        },
    ]
    department_listing_html = """
    <html><body>
      <a href="https://healthy.example.edu.cn/cs/">计算机学院</a>
      <a href="https://healthy.example.edu.cn/math/">数学学院</a>
    </body></html>
    """

    def _fake_fetch_text(url: str, timeout: int = 20) -> str:
        if url == "https://healthy.example.edu.cn/departments/":
            return department_listing_html
        if url == "https://timeout.example.edu.cn/departments/":
            raise httpx.ReadTimeout("The read operation timed out")
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(announcement_foundation, "_fetch_text", _fake_fetch_text)

    departments, candidates, skipped_schools = announcement_foundation.build_department_candidates(schools, paths=paths)

    assert [item["department_name"] for item in departments] == ["计算机学院", "数学学院"]
    assert [item["department_name"] for item in candidates] == ["计算机学院", "数学学院"]
    assert all(item["school_name"] == "Healthy University" for item in departments)
    assert all(item["school_name"] == "Healthy University" for item in candidates)
    assert skipped_schools == [
        {
            "school_code": "1002",
            "school_name": "Timeout University",
            "department_page_url": "https://timeout.example.edu.cn/departments/",
            "error_type": "ReadTimeout",
            "error_message": "The read operation timed out",
        }
    ]
    assert json.loads(paths.department_catalog.read_text(encoding="utf-8"))[0]["school_name"] == "Healthy University"
    assert json.loads(paths.department_candidates.read_text(encoding="utf-8"))[0]["school_name"] == "Healthy University"


def test_refresh_announcement_foundation_builds_snapshots_and_registry(monkeypatch):
    tmp_path = _temp_dir()
    school_catalog_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001.dhtml">示例大学</a>
      <div>北京 主管部门：教育部</div>
      <a href="https://yz.chsi.com.cn/sch/?start=20">2</a>
    </body></html>
    """
    school_detail_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001,categoryId-481347.dhtml">院系设置</a>
      <a href="/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml">专业介绍</a>
      <a href="/sch/viewBulletin--infoId-5001,categoryId-481379,schId-1001,mindex-12.dhtml">示例大学研究生招生信息网</a>
    </body></html>
    """
    school_bulletin_html = """
    <html><body>
      详见 <a href="https://yz.example.edu.cn/">示例大学研究生招生网</a>
    </body></html>
    """
    department_listing_html = """
    <html><body>
      <a href="https://example.edu.cn/cs/">计算机学院</a>
      <a href="https://example.edu.cn/math/">数学学院</a>
      <a href="https://example.edu.cn/news/">新闻网</a>
    </body></html>
    """
    major_listing_html = """
    <html><body>
      <h2>硕士专业</h2>
      工学
      <ul>
        <li>计算机系统结构[081201]</li>
        <li>计算机软件与理论[081202]</li>
      </ul>
      <h2>博士专业</h2>
      工学
      <ul>
        <li>计算机应用技术[081203]</li>
      </ul>
    </body></html>
    """
    roster_html = """
    <html><body>
      <a href="https://yz.example.edu.cn/">示例大学研招信息网址</a>
    </body></html>
    """
    homepage_json = [
        {"school_name": "示例大学", "website": "https://www.example.edu.cn/"},
    ]
    text_map = {
        announcement_foundation.CHSI_SCHOOL_CATALOG_URL: school_catalog_html,
        "https://yz.chsi.com.cn/sch/?start=20": "<html><body></body></html>",
        "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001.dhtml": school_detail_html,
        "https://yz.chsi.com.cn/sch/viewBulletin--infoId-5001,categoryId-481379,schId-1001,mindex-12.dhtml": school_bulletin_html,
        "https://yz.chsi.com.cn/sch/schoolInfo--schId-1001,categoryId-481347.dhtml": department_listing_html,
        "https://yz.chsi.com.cn/sch/listYzZyjs--schId-1001,categoryId-692157514.dhtml": major_listing_html,
        "https://www.example.edu.cn/": "<html><body></body></html>",
        announcement_foundation.OFFICIAL_SEED_ROSTER_SOURCES[0]["source_url"]: roster_html,
    }

    try:
        monkeypatch.setenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", str(tmp_path))
        monkeypatch.setattr(announcement_foundation, "_fetch_text", lambda url, timeout=20: text_map[url])
        monkeypatch.setattr(announcement_foundation, "_fetch_json", lambda url, timeout=20: homepage_json)

        result = announcement_foundation.refresh_announcement_foundation(dry_run=False)

        assert result["school_count"] == 1
        assert result["department_count"] == 2
        assert result["major_count"] == 3
        assert result["official_seed_candidate_count"] == 1
        assert result["skipped_school_count"] == 0

        school_snapshot = json.loads((tmp_path / announcement_foundation.SCHOOL_CATALOG_FILENAME).read_text(encoding="utf-8"))
        assert school_snapshot[0]["school_name"] == "示例大学"
        assert school_snapshot[0]["source_meta"]["seed_hint_urls"] == ["https://yz.example.edu.cn/"]

        department_snapshot = json.loads((tmp_path / announcement_foundation.DEPARTMENT_CATALOG_FILENAME).read_text(encoding="utf-8"))
        assert [item["department_name"] for item in department_snapshot] == ["计算机学院", "数学学院"]

        major_snapshot = json.loads((tmp_path / announcement_foundation.MAJOR_CATALOG_FILENAME).read_text(encoding="utf-8"))
        assert {(item["major_code"], item["degree_type"]) for item in major_snapshot} == {
            ("081201", "master"),
            ("081202", "master"),
            ("081203", "doctor"),
        }

        registry = json.loads((tmp_path / announcement_foundation.ANNOUNCEMENT_SEED_REGISTRY_FILENAME).read_text(encoding="utf-8"))
        assert registry[0]["school_name"] == "示例大学"
        assert registry[0]["homepage_url"] == "https://yz.example.edu.cn/"
        assert registry[0]["source_type"] == "official_roster"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_fetch_chsi_school_catalog_stops_after_requested_school_found_on_first_page(monkeypatch):
    school_catalog_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001.dhtml">Example University</a>
      <div>Beijing 主管部门：教育部</div>
      <a href="https://yz.chsi.com.cn/sch/?start=20">2</a>
      <a href="https://yz.chsi.com.cn/sch/?start=920">47</a>
    </body></html>
    """
    calls: list[str] = []

    def _fake_fetch_text(url: str, timeout: int = 20) -> str:
        calls.append(url)
        if url == announcement_foundation.CHSI_SCHOOL_CATALOG_URL:
            return school_catalog_html
        return "<html><body></body></html>"

    monkeypatch.setattr(announcement_foundation, "_fetch_text", _fake_fetch_text)

    schools = announcement_foundation.fetch_chsi_school_catalog(school_names=["Example University"])

    assert len(schools) == 1
    assert schools[0]["school_name"] == "Example University"
    assert calls == [announcement_foundation.CHSI_SCHOOL_CATALOG_URL]


def test_fetch_chsi_school_catalog_continues_until_requested_school_found(monkeypatch):
    first_page_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-1001.dhtml">First University</a>
      <div>Beijing 主管部门：教育部</div>
      <a href="https://yz.chsi.com.cn/sch/?start=20">2</a>
      <a href="https://yz.chsi.com.cn/sch/?start=920">47</a>
    </body></html>
    """
    second_page_html = """
    <html><body>
      <a href="/sch/schoolInfo--schId-2002.dhtml">Target University</a>
      <div>Shanghai 主管部门：教育部</div>
    </body></html>
    """
    calls: list[str] = []

    def _fake_fetch_text(url: str, timeout: int = 20) -> str:
        calls.append(url)
        if url == announcement_foundation.CHSI_SCHOOL_CATALOG_URL:
            return first_page_html
        if url == "https://yz.chsi.com.cn/sch/?start=20":
            return second_page_html
        return "<html><body></body></html>"

    monkeypatch.setattr(announcement_foundation, "_fetch_text", _fake_fetch_text)

    schools = announcement_foundation.fetch_chsi_school_catalog(school_names=["Target University"])

    assert len(schools) == 1
    assert schools[0]["school_name"] == "Target University"
    assert calls == [
        announcement_foundation.CHSI_SCHOOL_CATALOG_URL,
        "https://yz.chsi.com.cn/sch/?start=20",
    ]


def test_canonical_scope_seeds_reads_json_registry_and_department_override(monkeypatch):
    tmp_path = _temp_dir()
    try:
        monkeypatch.setenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", str(tmp_path))
        (tmp_path / announcement_foundation.ANNOUNCEMENT_SEED_REGISTRY_FILENAME).write_text(
            json.dumps(
                [
                    {
                        "scope_type": "school",
                        "school_name": "离线大学",
                        "department_name": None,
                        "homepage_url": "https://yz.offline.edu.cn/",
                        "seed_urls": ["https://yz.offline.edu.cn/"],
                        "source_type": "official_roster",
                        "confidence": "high",
                        "deny_prefixes": [],
                        "notes": "offline test",
                        "last_verified_at": "2026-03-26T00:00:00+00:00",
                    },
                    {
                        "scope_type": "department",
                        "school_name": "离线大学",
                        "department_name": "计算机学院",
                        "homepage_url": "https://yz.offline.edu.cn/cs/",
                        "seed_urls": ["https://yz.offline.edu.cn/cs/"],
                        "source_type": "manual_override",
                        "confidence": "high",
                        "deny_prefixes": [],
                        "notes": "department review passed",
                        "last_verified_at": "2026-03-26T00:00:00+00:00",
                    },
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _announcement_school_seed_registry.cache_clear()
        _announcement_department_seed_registry.cache_clear()

        school_seed = get_announcement_school_seed("离线大学")
        department_seed = get_announcement_department_seed("离线大学", "计算机学院")

        assert school_seed is not None
        assert school_seed.homepage_url == "https://yz.offline.edu.cn/"
        assert department_seed is not None
        assert department_seed.homepage_url == "https://yz.offline.edu.cn/cs/"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
