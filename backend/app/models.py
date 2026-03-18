import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class School(Base):
    __tablename__ = "schools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    sources: Mapped[list["Source"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    departments: Mapped[list["Department"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    site_sections: Mapped[list["SiteSection"]] = relationship(back_populates="school", cascade="all, delete-orphan")
    contents: Mapped[list["Content"]] = relationship(back_populates="school")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="official", nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship(back_populates="sources")
    contents: Mapped[list["Content"]] = relationship(back_populates="source")
    site_sections: Mapped[list["SiteSection"]] = relationship(back_populates="source")


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_departments_school_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    department_type: Mapped[str] = mapped_column(String(64), default="college", nullable=False, index=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship(back_populates="departments")
    site_sections: Mapped[list["SiteSection"]] = relationship(back_populates="department", cascade="all, delete-orphan")


class SiteSection(Base):
    __tablename__ = "site_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section_type: Mapped[str] = mapped_column(String(64), default="notice", nullable=False, index=True)
    section_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    discovery_category: Mapped[str] = mapped_column(String(32), default="announcement", nullable=False, index=True)
    list_selector_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_discovery_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship(back_populates="site_sections")
    department: Mapped["Department | None"] = relationship(back_populates="site_sections")
    source: Mapped["Source | None"] = relationship(back_populates="site_sections")
    links: Mapped[list["SiteSectionLink"]] = relationship(back_populates="site_section", cascade="all, delete-orphan")


class SiteSectionLink(Base):
    __tablename__ = "site_section_links"
    __table_args__ = (UniqueConstraint("site_section_id", "link_url_hash", name="uq_site_section_links_section_url_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_section_id: Mapped[str] = mapped_column(ForeignKey("site_sections.id"), nullable=False, index=True)
    crawl_job_id: Mapped[str | None] = mapped_column(ForeignKey("crawl_jobs.id"), nullable=True, index=True)
    link_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    link_url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_type: Mapped[str] = mapped_column(String(32), default="html", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    site_section: Mapped["SiteSection"] = relationship(back_populates="links")
    files: Mapped[list["ContentFile"]] = relationship(back_populates="site_section_link", cascade="all, delete-orphan")


class ContentFile(Base):
    __tablename__ = "content_files"
    __table_args__ = (UniqueConstraint("site_section_link_id", "file_url_hash", name="uq_content_files_link_file_url_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_id: Mapped[str | None] = mapped_column(ForeignKey("contents.id"), nullable=True, index=True)
    site_section_link_id: Mapped[str | None] = mapped_column(ForeignKey("site_section_links.id"), nullable=True, index=True)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(32), default="pdf", nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text_extracted: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    ocr_status: Mapped[str] = mapped_column(String(32), default="not_started", nullable=False, index=True)
    file_meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    content: Mapped["Content | None"] = relationship()
    site_section_link: Mapped["SiteSectionLink | None"] = relationship(back_populates="files")


class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (UniqueConstraint("source_url", name="uq_contents_source_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # announcement|adjustment
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="crawler", nullable=False, index=True)  # crawler|manual
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    major: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship(back_populates="contents")
    source: Mapped["Source | None"] = relationship(back_populates="contents")
    snapshots: Mapped[list["ContentSnapshot"]] = relationship(back_populates="content", cascade="all, delete-orphan")


class ContentSnapshot(Base):
    __tablename__ = "content_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_id: Mapped[str] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    content: Mapped["Content"] = relationship(back_populates="snapshots")


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    query: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CrawlError(Base):
    __tablename__ = "crawl_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True, index=True)
    content_id: Mapped[str | None] = mapped_column(ForeignKey("contents.id"), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    error_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    openid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="shadow", nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    events: Mapped[list["UserEvent"]] = relationship(back_populates="user")


class PortalUser(Base):
    __tablename__ = "portal_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    notify_bark_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notify_bark_enabled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    premium_monitoring_enabled: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    admin_account: Mapped["AdminAccount | None"] = relationship(back_populates="user", uselist=False)
    sessions: Mapped[list["PortalUserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    subscriptions: Mapped[list["PortalUserSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    monitor_targets: Mapped[list["PortalUserMonitorTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    monitor_keywords: Mapped[list["PortalUserMonitorKeyword"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    monitor_hits: Mapped[list["PortalUserMonitorHit"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AdminAccount(Base):
    __tablename__ = "admin_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user: Mapped["PortalUser"] = relationship(back_populates="admin_account")


class PortalUserSession(Base):
    __tablename__ = "portal_user_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_portal_user_sessions_token_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["PortalUser"] = relationship(back_populates="sessions")


class PortalUserSubscription(Base):
    __tablename__ = "portal_user_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "subscription_type", "value", name="uq_portal_subscriptions_user_type_value"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    subscription_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), default="all", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["PortalUser"] = relationship(back_populates="subscriptions")


class PortalUserMonitorTarget(Base):
    __tablename__ = "portal_user_monitor_targets"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "scope_type",
            "school_id",
            "department_id",
            "site_section_id",
            name="uq_monitor_targets_user_scope_school_department_section",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # school|department|section
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    site_section_id: Mapped[str | None] = mapped_column(ForeignKey("site_sections.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)  # active|paused|deleted
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["PortalUser"] = relationship(back_populates="monitor_targets")
    school: Mapped["School | None"] = relationship()
    department: Mapped["Department | None"] = relationship()
    site_section: Mapped["SiteSection | None"] = relationship()
    keywords: Mapped[list["PortalUserMonitorKeyword"]] = relationship(
        back_populates="monitor_target", cascade="all, delete-orphan"
    )
    hits: Mapped[list["PortalUserMonitorHit"]] = relationship(
        back_populates="monitor_target", cascade="all, delete-orphan"
    )


class PortalUserMonitorKeyword(Base):
    __tablename__ = "portal_user_monitor_keywords"
    __table_args__ = (
        UniqueConstraint(
            "monitor_target_id",
            "keyword",
            "match_mode",
            name="uq_monitor_keywords_target_keyword_mode",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    monitor_target_id: Mapped[str] = mapped_column(ForeignKey("portal_user_monitor_targets.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    match_mode: Mapped[str] = mapped_column(String(32), default="contains", nullable=False, index=True)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["PortalUser"] = relationship(back_populates="monitor_keywords")
    monitor_target: Mapped["PortalUserMonitorTarget"] = relationship(back_populates="keywords")


class PortalUserMonitorHit(Base):
    __tablename__ = "portal_user_monitor_hits"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "monitor_target_id",
            "content_id",
            name="uq_monitor_hits_user_target_content",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    monitor_target_id: Mapped[str] = mapped_column(ForeignKey("portal_user_monitor_targets.id"), nullable=False, index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    site_section_id: Mapped[str | None] = mapped_column(ForeignKey("site_sections.id"), nullable=True, index=True)
    matched_keywords: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    match_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    hit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pushed_inapp: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    pushed_bark: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    user: Mapped["PortalUser"] = relationship(back_populates="monitor_hits")
    monitor_target: Mapped["PortalUserMonitorTarget"] = relationship(back_populates="hits")
    content: Mapped["Content"] = relationship()
    site_section: Mapped["SiteSection | None"] = relationship()


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (Index("ix_outbox_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_id: Mapped[str] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="content.upsert", nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("outbox_id", "user_id", "channel", name="uq_notification_deliveries_outbox_user_channel"),
        Index("ix_delivery_user_status_channel", "user_id", "status", "channel"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    outbox_id: Mapped[str] = mapped_column(ForeignKey("notification_outbox.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), default="inapp", nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    deliver_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["PortalUser"] = relationship()


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="events")
