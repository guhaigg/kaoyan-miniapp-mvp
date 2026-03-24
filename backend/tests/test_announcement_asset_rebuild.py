from __future__ import annotations

from app.db import SessionLocal
from app.models import (
    Content,
    ContentFile,
    ContentSnapshot,
    CrawlError,
    CrawlJob,
    HistoricalReleaseTimingProfile,
    NotificationDelivery,
    NotificationOutbox,
    PortalUser,
    PortalUserMonitorHit,
    PortalUserMonitorTarget,
    School,
    SiteSection,
    SiteSectionLink,
    Source,
)
from app.services.announcement_asset_rebuild import rebuild_announcement_assets


def test_rebuild_announcement_assets_clears_crawler_announcement_chain_and_requeues_sections():
    with SessionLocal() as db:
        school = School(name="重建大学", aliases=[])
        db.add(school)
        db.flush()
        source = Source(
            school_id=school.id,
            name="重建大学研究生院",
            source_type="official",
            base_url="https://rebuild.edu.cn",
            config={},
            enabled=1,
        )
        db.add(source)
        db.flush()

        announcement_section = SiteSection(
            school_id=school.id,
            source_id=source.id,
            name="通知公告",
            section_type="notice",
            section_url="https://rebuild.edu.cn/yjs/notices/",
            discovery_category="announcement",
            list_selector_config={"probe_family": "notice", "probe_role": "leaf", "probe_scope": "general"},
            detail_selector_config={},
            enabled=1,
        )
        adjustment_section = SiteSection(
            school_id=school.id,
            source_id=source.id,
            name="调剂公告",
            section_type="adjustment",
            section_url="https://rebuild.edu.cn/yjs/adjustment/",
            discovery_category="adjustment",
            list_selector_config={"probe_family": "adjustment", "probe_role": "leaf", "probe_scope": "general"},
            detail_selector_config={},
            enabled=1,
        )
        db.add_all([announcement_section, adjustment_section])
        db.flush()

        announcement_link = SiteSectionLink(
            site_section_id=announcement_section.id,
            link_url="https://rebuild.edu.cn/yjs/notices/2026-01.html",
            link_url_hash="announcement-link-hash",
            title="重建大学2026年招生公告",
            link_type="html",
            status="discovered",
        )
        adjustment_link = SiteSectionLink(
            site_section_id=adjustment_section.id,
            link_url="https://rebuild.edu.cn/yjs/adjustment/2026-01.html",
            link_url_hash="adjustment-link-hash",
            title="重建大学调剂公告",
            link_type="html",
            status="discovered",
        )
        db.add_all([announcement_link, adjustment_link])
        db.flush()

        crawler_announcement = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="重建大学2026年招生公告",
            body="这是待清理的 crawler 公告正文。",
            summary="待清理",
            source_type="crawler",
            source_url="https://rebuild.edu.cn/yjs/notices/2026-01.html",
            extra={
                "school_name": "重建大学",
                "site_section_id": announcement_section.id,
                "site_section_link_id": announcement_link.id,
                "crawl_mode": "url_fetch",
            },
        )
        manual_announcement = Content(
            school_id=school.id,
            source_id=source.id,
            category="announcement",
            title="重建大学手工公告",
            body="这条手工录入公告应被保留。",
            summary="手工公告",
            source_type="manual",
            source_url="https://manual.example.com/rebuild-1",
            extra={"school_name": "重建大学"},
        )
        adjustment_content = Content(
            school_id=school.id,
            source_id=source.id,
            category="adjustment",
            title="重建大学调剂信息",
            body="调剂链路内容不应受影响。",
            summary="调剂公告",
            source_type="crawler",
            source_url="https://rebuild.edu.cn/yjs/adjustment/2026-01.html",
            extra={"school_name": "重建大学", "site_section_id": adjustment_section.id},
        )
        db.add_all([crawler_announcement, manual_announcement, adjustment_content])
        db.flush()

        db.add(
            ContentSnapshot(
                content_id=crawler_announcement.id,
                raw_html="<html><body>snapshot</body></html>",
                raw_text="snapshot",
                snapshot_meta={},
            )
        )
        db.add_all(
            [
                ContentFile(
                    content_id=crawler_announcement.id,
                    site_section_link_id=announcement_link.id,
                    file_url="https://rebuild.edu.cn/files/announcement.pdf",
                    file_url_hash="announcement-file-hash",
                    file_type="pdf",
                    parse_status="done",
                    file_meta={},
                ),
                ContentFile(
                    content_id=None,
                    site_section_link_id=adjustment_link.id,
                    file_url="https://rebuild.edu.cn/files/adjustment.pdf",
                    file_url_hash="adjustment-file-hash",
                    file_type="pdf",
                    parse_status="done",
                    file_meta={},
                ),
            ]
        )

        user = PortalUser(username="rebuild-monitor-user", password_hash="hash", nickname="rebuild", status="active")
        db.add(user)
        db.flush()
        target = PortalUserMonitorTarget(
            user_id=user.id,
            scope_type="school",
            school_id=school.id,
            department_id=None,
            site_section_id=None,
            status="active",
            check_interval_minutes=60,
        )
        db.add(target)
        db.flush()
        db.add(
            PortalUserMonitorHit(
                user_id=user.id,
                monitor_target_id=target.id,
                content_id=crawler_announcement.id,
                site_section_id=announcement_section.id,
                matched_keywords=[],
                match_score=1,
                hit_reason="scope_match:school",
                pushed_inapp=0,
                pushed_bark=0,
            )
        )

        outbox = NotificationOutbox(
            content_id=crawler_announcement.id,
            event_type="monitor.hit",
            payload={"content_id": crawler_announcement.id, "title": crawler_announcement.title},
            status="pending",
        )
        db.add(outbox)
        db.flush()
        db.add(
            NotificationDelivery(
                outbox_id=outbox.id,
                user_id=user.id,
                channel="inapp",
                payload={"content_id": crawler_announcement.id},
                status="pending",
            )
        )
        db.add(
            CrawlError(
                source_id=source.id,
                content_id=crawler_announcement.id,
                source_url=crawler_announcement.source_url,
                error_type="detail_fetch",
                error_message="temporary failure",
                payload={},
            )
        )
        db.add_all(
            [
                CrawlJob(
                    category="announcement",
                    status="pending",
                    query={"job_kind": "detail_fetch", "content_id": crawler_announcement.id, "school_name": "重建大学"},
                    message="old announcement job",
                ),
                CrawlJob(
                    category="adjustment",
                    status="pending",
                    query={"job_kind": "detail_fetch", "school_name": "重建大学"},
                    message="adjustment job should remain",
                ),
            ]
        )
        db.add(
            HistoricalReleaseTimingProfile(
                profile_key="rebuild-school-profile",
                school_id=school.id,
                school_name="重建大学",
                school_name_normalized="重建大学",
                sample_count=3,
                meta_json={"source": "test"},
            )
        )
        db.commit()
        announcement_section_id = announcement_section.id
        adjustment_section_id = adjustment_section.id
        announcement_link_id = announcement_link.id
        adjustment_link_id = adjustment_link.id
        crawler_announcement_id = crawler_announcement.id
        manual_announcement_id = manual_announcement.id
        adjustment_content_id = adjustment_content.id

        result = rebuild_announcement_assets(db)

        assert result["snapshot"]["section_count"] == 1
        assert result["snapshot"]["link_count"] == 1
        assert result["snapshot"]["announcement_content_count"] == 1
        assert result["deleted_monitor_hits"] == 1
        assert result["deleted_outboxes"] == 1
        assert result["deleted_deliveries"] == 1
        assert result["deleted_crawl_errors"] == 1
        assert result["queued_discovery_jobs"] == 1

    with SessionLocal() as db:
        assert db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == announcement_section_id).count() == 0
        assert db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == adjustment_section_id).count() == 1
        assert db.query(Content).filter(Content.id == crawler_announcement_id).count() == 0
        assert db.query(Content).filter(Content.id == manual_announcement_id).count() == 1
        assert db.query(Content).filter(Content.id == adjustment_content_id).count() == 1
        assert db.query(ContentSnapshot).filter(ContentSnapshot.content_id == crawler_announcement_id).count() == 0
        assert db.query(ContentFile).filter(ContentFile.site_section_link_id == announcement_link_id).count() == 0
        assert db.query(ContentFile).filter(ContentFile.site_section_link_id == adjustment_link_id).count() == 1
        assert db.query(PortalUserMonitorHit).count() == 0
        assert db.query(NotificationOutbox).count() == 0
        assert db.query(NotificationDelivery).count() == 0
        assert db.query(CrawlError).count() == 0
        announcement_jobs = db.query(CrawlJob).filter(CrawlJob.category == "announcement").all()
        adjustment_jobs = db.query(CrawlJob).filter(CrawlJob.category == "adjustment").all()
        assert len(announcement_jobs) == 1
        assert announcement_jobs[0].query["job_kind"] == "site_section_discovery"
        assert announcement_jobs[0].query["site_section_id"] == announcement_section_id
        assert len(adjustment_jobs) == 1
        assert db.query(HistoricalReleaseTimingProfile).count() == 1
