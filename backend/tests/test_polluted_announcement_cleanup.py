from __future__ import annotations

from app.db import SessionLocal
from app.models import (
    Content,
    ContentSnapshot,
    CrawlJob,
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
from app.services.polluted_announcement_cleanup import cleanup_polluted_announcement_data


def _seed_polluted_school_host_mismatch() -> dict[str, str]:
    with SessionLocal() as db:
        owner_school = School(name="正确来源大学", aliases=[])
        polluted_school = School(name="误绑大学", aliases=[])
        db.add_all([owner_school, polluted_school])
        db.flush()

        owner_source = Source(
            school_id=owner_school.id,
            name="正确来源大学研究生招生网",
            source_type="official",
            base_url="https://yz.owner.edu.cn/",
            config={},
            enabled=1,
        )
        polluted_source = Source(
            school_id=polluted_school.id,
            name="误绑大学研究生院",
            source_type="official",
            base_url="https://yz.polluted.edu.cn/",
            config={},
            enabled=1,
        )
        db.add_all([owner_source, polluted_source])
        db.flush()

        owner_section = SiteSection(
            school_id=owner_school.id,
            source_id=owner_source.id,
            name="正确来源大学研究生招生网",
            section_type="notice",
            section_url="https://yz.owner.edu.cn/",
            discovery_category="announcement",
            list_selector_config={"probe_heading": "正确来源大学研究生招生网"},
            detail_selector_config={},
            enabled=1,
        )
        polluted_section = SiteSection(
            school_id=polluted_school.id,
            source_id=polluted_source.id,
            name="通知公告",
            section_type="notice",
            section_url="https://yz.owner.edu.cn/notice/",
            discovery_category="announcement",
            list_selector_config={"probe_heading": "通知公告"},
            detail_selector_config={},
            enabled=1,
        )
        correct_section = SiteSection(
            school_id=polluted_school.id,
            source_id=polluted_source.id,
            name="误绑大学研究生院通知公告",
            section_type="notice",
            section_url="https://yz.polluted.edu.cn/notice/",
            discovery_category="announcement",
            list_selector_config={"probe_heading": "误绑大学研究生院"},
            detail_selector_config={},
            enabled=1,
        )
        db.add_all([owner_section, polluted_section, correct_section])
        db.flush()

        polluted_link = SiteSectionLink(
            site_section_id=polluted_section.id,
            link_url="https://yz.owner.edu.cn/info/1001/2001.htm",
            link_url_hash="polluted-link",
            title="正确来源大学 2026 招生公告",
            link_type="html",
            status="discovered",
        )
        correct_link = SiteSectionLink(
            site_section_id=correct_section.id,
            link_url="https://yz.polluted.edu.cn/info/1001/2002.htm",
            link_url_hash="correct-link",
            title="误绑大学 2026 招生公告",
            link_type="html",
            status="discovered",
        )
        db.add_all([polluted_link, correct_link])
        db.flush()

        polluted_content = Content(
            school_id=polluted_school.id,
            source_id=polluted_source.id,
            category="announcement",
            title="正确来源大学 2026 招生公告",
            body="来自错误 host 的内容。",
            summary="污染数据",
            source_type="crawler",
            source_url="https://yz.owner.edu.cn/info/1001/2001.htm",
            extra={"site_section_id": polluted_section.id, "school_name": polluted_school.name},
        )
        correct_content = Content(
            school_id=polluted_school.id,
            source_id=polluted_source.id,
            category="announcement",
            title="误绑大学 2026 招生公告",
            body="正确内容。",
            summary="正确数据",
            source_type="crawler",
            source_url="https://yz.polluted.edu.cn/info/1001/2002.htm",
            extra={"site_section_id": correct_section.id, "school_name": polluted_school.name},
        )
        db.add_all([polluted_content, correct_content])
        db.flush()

        db.add(ContentSnapshot(content_id=polluted_content.id, raw_html="<html>polluted</html>", raw_text="polluted", snapshot_meta={}))

        portal_user = PortalUser(username="cleanup-user", password_hash="hash", nickname="cleanup")
        db.add(portal_user)
        db.flush()
        target = PortalUserMonitorTarget(
            user_id=portal_user.id,
            scope_type="school",
            school_id=polluted_school.id,
            status="active",
            check_interval_minutes=60,
        )
        db.add(target)
        db.flush()
        db.add(
            PortalUserMonitorHit(
                user_id=portal_user.id,
                monitor_target_id=target.id,
                content_id=polluted_content.id,
                site_section_id=polluted_section.id,
                matched_keywords=["招生"],
                match_score=10,
            )
        )

        outbox = NotificationOutbox(content_id=polluted_content.id, payload={"school_name": polluted_school.name}, status="pending")
        db.add(outbox)
        db.flush()
        db.add(NotificationDelivery(outbox_id=outbox.id, user_id=portal_user.id, channel="inapp", payload={"school_name": polluted_school.name}))

        db.add(
            CrawlJob(
                category="announcement",
                status="done",
                message="polluted detail fetch",
                query={
                    "job_kind": "detail_fetch",
                    "school_name": polluted_school.name,
                    "source_url": "https://yz.owner.edu.cn/info/1001/2001.htm",
                },
            )
        )
        db.add(
            CrawlJob(
                category="announcement",
                status="done",
                message="correct detail fetch",
                query={
                    "job_kind": "detail_fetch",
                    "school_name": polluted_school.name,
                    "source_url": "https://yz.polluted.edu.cn/info/1001/2002.htm",
                },
            )
        )
        db.commit()
        return {
            "polluted_school_id": polluted_school.id,
            "polluted_section_id": polluted_section.id,
            "polluted_content_id": polluted_content.id,
            "correct_content_id": correct_content.id,
        }


def test_cleanup_polluted_announcement_data_dry_run_keeps_rows():
    ids = _seed_polluted_school_host_mismatch()

    with SessionLocal() as db:
        stats = cleanup_polluted_announcement_data(db, dry_run=True)

    assert stats["identified"]["sections"] == 1
    assert stats["identified"]["contents"] == 1
    assert stats["identified"]["monitor_hits"] == 1
    assert stats["identified"]["notification_outbox"] == 1
    assert stats["identified"]["notification_deliveries"] == 1
    assert stats["identified"]["crawl_jobs"] == 1

    with SessionLocal() as db:
        assert db.query(SiteSection).filter(SiteSection.id == ids["polluted_section_id"]).one_or_none() is not None
        assert db.query(Content).filter(Content.id == ids["polluted_content_id"]).one_or_none() is not None


def test_cleanup_polluted_announcement_data_deletes_only_mismatched_host_rows():
    ids = _seed_polluted_school_host_mismatch()

    with SessionLocal() as db:
        stats = cleanup_polluted_announcement_data(db)

    assert stats["deleted"]["sections"] == 1
    assert stats["deleted"]["contents"] == 1
    assert stats["deleted"]["snapshots"] == 1
    assert stats["deleted"]["monitor_hits"] == 1
    assert stats["deleted"]["notification_outbox"] == 1
    assert stats["deleted"]["notification_deliveries"] == 1
    assert stats["deleted"]["crawl_jobs"] == 1

    with SessionLocal() as db:
        assert db.query(SiteSection).filter(SiteSection.id == ids["polluted_section_id"]).one_or_none() is None
        assert db.query(Content).filter(Content.id == ids["polluted_content_id"]).one_or_none() is None
        assert db.query(Content).filter(Content.id == ids["correct_content_id"]).one_or_none() is not None
