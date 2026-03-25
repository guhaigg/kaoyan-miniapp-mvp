from __future__ import annotations

from app.db import SessionLocal
from app.models import Content, School, SiteSection, SiteSectionLink, Source
from app.services.announcement_portal import announcement_extra_is_visible
from app.services.announcement_portal_backfill import backfill_announcement_portal_metadata


def test_backfill_announcement_portal_metadata_fills_portal_fields_from_section():
    with SessionLocal() as db:
        school = School(name="回填门户大学", aliases=[])
        db.add(school)
        db.flush()
        source = Source(
            school_id=school.id,
            name="回填门户大学研究生院",
            source_type="official",
            base_url="https://portal-backfill.example.edu.cn",
            config={},
            enabled=1,
        )
        db.add(source)
        db.flush()

        section = SiteSection(
            school_id=school.id,
            source_id=source.id,
            name="硕士招生",
            section_type="admissions",
            section_url="https://portal-backfill.example.edu.cn/sszs.htm",
            discovery_category="announcement",
            list_selector_config={
                "portal_scope": "graduate_admissions",
                "portal_entry_url": "https://portal-backfill.example.edu.cn/",
                "channel_label": "硕士招生",
                "channel_tier": "core",
                "channel_keywords": ["硕士招生", "sszs"],
                "portal_path_evidence": {"section_url": "https://portal-backfill.example.edu.cn/sszs.htm"},
            },
            detail_selector_config={},
            enabled=1,
        )
        db.add(section)
        db.flush()

        link = SiteSectionLink(
            site_section_id=section.id,
            link_url="https://portal-backfill.example.edu.cn/info/1001/2001.htm",
            link_url_hash="portal-backfill-link-hash",
            title="回填门户大学2026年硕士研究生招生简章",
            link_type="html",
            status="discovered",
        )
        db.add(link)
        db.flush()

        row = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="回填门户大学2026年硕士研究生招生简章",
            body="这里是硕士研究生招生简章与报考说明。",
            summary="招生简章旧数据",
            source_type="crawler",
            source_url=link.link_url,
            extra={
                "school_name": "回填门户大学",
                "site_section_link_id": link.id,
                "tags": ["报考说明"],
            },
        )
        db.add(row)
        db.commit()
        row_id = row.id
        section_id = section.id

        stats = backfill_announcement_portal_metadata(db)

        assert stats["scanned"] == 1
        assert stats["matched"] == 1
        assert stats["updated"] == 1

    with SessionLocal() as db:
        row = db.query(Content).filter(Content.id == row_id).one()
        extra = dict(row.extra or {})
        assert extra["site_section_id"] == section_id
        assert extra["site_section_name"] == "硕士招生"
        assert extra["portal_scope"] == "graduate_admissions"
        assert extra["portal_entry_url"] == "https://portal-backfill.example.edu.cn/"
        assert extra["channel_label"] == "硕士招生"
        assert extra["channel_tier"] == "core"
        assert extra["channel_keywords"] == ["硕士招生", "sszs", "硕士研究生"]
        assert extra["system_tags"] == ["硕士招生", "招生简章"]
        assert extra["tags"] == ["硕士招生", "报考说明", "招生简章"]


def test_backfill_announcement_portal_metadata_dry_run_does_not_commit_changes():
    with SessionLocal() as db:
        school = School(name="回填演练大学", aliases=[])
        db.add(school)
        db.flush()
        source = Source(
            school_id=school.id,
            name="回填演练大学研究生院",
            source_type="official",
            base_url="https://dry-run.example.edu.cn",
            config={},
            enabled=1,
        )
        db.add(source)
        db.flush()

        section = SiteSection(
            school_id=school.id,
            source_id=source.id,
            name="通知公告",
            section_type="notice",
            section_url="https://dry-run.example.edu.cn/tzgg.htm",
            discovery_category="announcement",
            list_selector_config={
                "portal_scope": "graduate_admissions",
                "channel_label": "通知公告",
                "channel_tier": "core",
            },
            detail_selector_config={},
            enabled=1,
        )
        db.add(section)
        db.flush()

        row = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="回填演练大学复试通知",
            body="请查看复试安排。",
            summary="复试通知",
            source_type="crawler",
            source_url="https://dry-run.example.edu.cn/info/1001/2001.htm",
            extra={
                "school_name": "回填演练大学",
                "site_section_id": section.id,
            },
        )
        db.add(row)
        db.commit()
        row_id = row.id

        stats = backfill_announcement_portal_metadata(db, dry_run=True)

        assert stats["updated"] == 1

    with SessionLocal() as db:
        row = db.query(Content).filter(Content.id == row_id).one()
        extra = dict(row.extra or {})
        assert "portal_scope" not in extra
        assert "system_tags" not in extra


def test_backfill_announcement_portal_metadata_does_not_promote_non_admissions_detail_pages():
    with SessionLocal() as db:
        school = School(name="严格门户大学", aliases=[])
        db.add(school)
        db.flush()
        source = Source(
            school_id=school.id,
            name="严格门户大学研究生招生网",
            source_type="official",
            base_url="https://yz.strict.example.edu.cn",
            config={},
            enabled=1,
        )
        db.add(source)
        db.flush()

        section = SiteSection(
            school_id=school.id,
            source_id=source.id,
            name="通知公告",
            section_type="notice",
            section_url="https://yz.strict.example.edu.cn/tzgg.htm",
            discovery_category="announcement",
            list_selector_config={
                "portal_scope": "graduate_admissions",
                "portal_entry_url": "https://yz.strict.example.edu.cn/",
                "channel_label": "通知公告",
                "channel_tier": "core",
            },
            detail_selector_config={},
            enabled=1,
        )
        db.add(section)
        db.flush()

        row = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="教职工春游活动通知",
            body="学校工会组织春季踏青活动，请各单位报名参加。",
            summary="工会活动通知",
            source_type="crawler",
            source_url="https://xgh.strict.example.edu.cn/info/1001/2001.htm",
            extra={
                "school_name": "严格门户大学",
                "site_section_id": section.id,
            },
        )
        db.add(row)
        db.commit()
        row_id = row.id

        stats = backfill_announcement_portal_metadata(db, overwrite=True)

        assert stats["matched"] == 1
        assert stats["updated"] == 1

    with SessionLocal() as db:
        row = db.query(Content).filter(Content.id == row_id).one()
        extra = dict(row.extra or {})
        assert "portal_scope" not in extra
        assert "channel_label" not in extra
        assert announcement_extra_is_visible(extra) is False


def test_backfill_announcement_portal_metadata_infers_unlinked_admissions_rows_from_url_and_title():
    with SessionLocal() as db:
        school = School(name="推断门户大学", aliases=[])
        db.add(school)
        db.flush()
        source = Source(
            school_id=school.id,
            name="推断门户大学",
            source_type="official",
            base_url="https://www.infer.example.edu.cn",
            config={},
            enabled=1,
        )
        db.add(source)
        db.flush()

        row = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="推断门户大学2026年硕士研究生招生简章",
            body="现公布2026年硕士研究生招生简章与报考说明。",
            summary="招生简章历史页",
            source_type="crawler",
            source_url="https://yzb.infer.example.edu.cn/2606/list.htm",
            extra={
                "school_name": "推断门户大学",
                "tags": ["报考说明"],
            },
        )
        db.add(row)
        db.commit()
        row_id = row.id

        stats = backfill_announcement_portal_metadata(db, overwrite=True)

        assert stats["matched"] == 0
        assert stats["inferred_without_section"] == 1
        assert stats["updated"] == 1

    with SessionLocal() as db:
        row = db.query(Content).filter(Content.id == row_id).one()
        extra = dict(row.extra or {})
        assert extra["portal_scope"] == "graduate_admissions"
        assert extra["channel_label"] == "硕士招生"
        assert extra["channel_tier"] == "core"
        assert "招生简章" in extra["system_tags"]
