import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def sha256_hex(value: str | None) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


LONGTEXT_TYPE = Text().with_variant(mysql.LONGTEXT(), "mysql")


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
    detail_selector_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
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


class AnnouncementPortalCache(Base):
    __tablename__ = "announcement_portal_caches"
    __table_args__ = (
        UniqueConstraint("school_name", "families_key", name="uq_announcement_portal_caches_school_families"),
        Index("ix_announcement_portal_caches_lookup", "school_name", "families_key", "last_verified_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    families_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    candidate_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferred_hosts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


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
    __table_args__ = (
        UniqueConstraint("source_url", name="uq_contents_source_url"),
        UniqueConstraint("content_fingerprint", name="uq_contents_content_fingerprint"),
    )

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
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
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


class PortalNode(Base):
    __tablename__ = "portal_nodes"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_key", "node_type", "url_hash", name="uq_portal_nodes_scope_type_url_hash"),
        Index("ix_portal_nodes_scope_status", "scope_type", "scope_key", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="candidate", nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship()
    department: Mapped["Department | None"] = relationship()


class PortalEdge(Base):
    __tablename__ = "portal_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", "relation_type", name="uq_portal_edges_from_to_relation"),
        Index("ix_portal_edges_relation", "relation_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_node_id: Mapped[str] = mapped_column(ForeignKey("portal_nodes.id"), nullable=False, index=True)
    to_node_id: Mapped[str] = mapped_column(ForeignKey("portal_nodes.id"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    from_node: Mapped["PortalNode"] = relationship(foreign_keys=[from_node_id])
    to_node: Mapped["PortalNode"] = relationship(foreign_keys=[to_node_id])


class PortalHostDecision(Base):
    __tablename__ = "portal_host_decisions"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_key", "family", name="uq_portal_host_decisions_scope_family"),
        Index("ix_portal_host_decisions_scope_key_status", "scope_type", "scope_key", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    selected_host: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    candidate_hosts: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), default="v2", nullable=False)
    decision_source: Mapped[str] = mapped_column(String(32), default="workflow", nullable=False)
    manual_override: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship()
    department: Mapped["Department | None"] = relationship()


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_scope_status", "scope_type", "scope_key", "status"),
        Index("ix_workflow_runs_type_created", "workflow_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("portal_users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    requested_by_account: Mapped["PortalUser | None"] = relationship(foreign_keys=[requested_by_account_id])


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        Index("ix_workflow_steps_scope_status", "scope_type", "scope_key", "status"),
        Index("ix_workflow_steps_type_available", "step_type", "available_at"),
        Index("ix_workflow_steps_host_status", "host_key", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    parent_step_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_steps.id"), nullable=True, index=True)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    host_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    run: Mapped["WorkflowRun"] = relationship()
    parent_step: Mapped["WorkflowStep | None"] = relationship(remote_side=[id], foreign_keys=[parent_step_id])


class RawArtifact(Base):
    __tablename__ = "raw_artifacts"
    __table_args__ = (
        Index("ix_raw_artifacts_step_type", "workflow_step_id", "artifact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id"), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    headers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    workflow_step: Mapped["WorkflowStep"] = relationship()


class ParseArtifact(Base):
    __tablename__ = "parse_artifacts"
    __table_args__ = (
        Index("ix_parse_artifacts_step_type", "workflow_step_id", "artifact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workflow_step_id: Mapped[str] = mapped_column(ForeignKey("workflow_steps.id"), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    workflow_step: Mapped["WorkflowStep"] = relationship()


class ContentClassification(Base):
    __tablename__ = "content_classifications"
    __table_args__ = (
        UniqueConstraint("content_id", name="uq_content_classifications_content_id"),
        Index("ix_content_classifications_scope_visibility", "scope_type", "scope_key", "is_visible"),
        Index("ix_content_classifications_state", "classification_state", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    content_id: Mapped[str] = mapped_column(ForeignKey("contents.id"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="hidden", nullable=False, index=True)
    classification_state: Mapped[str] = mapped_column(String(64), default="hidden_non_admissions", nullable=False, index=True)
    is_visible: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    rule_version: Mapped[str] = mapped_column(String(64), default="v2", nullable=False)
    explain_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    content: Mapped["Content"] = relationship()


class GovernanceAction(Base):
    __tablename__ = "governance_actions"
    __table_args__ = (
        Index("ix_governance_actions_scope_key_created", "scope_type", "scope_key", "created_at"),
        Index("ix_governance_actions_entity", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_account_id: Mapped[str | None] = mapped_column(ForeignKey("portal_users.id"), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    actor_account: Mapped["PortalUser | None"] = relationship(foreign_keys=[actor_account_id])


class RawDatasetArchive(Base):
    __tablename__ = "raw_dataset_archives"
    __table_args__ = (
        UniqueConstraint("dataset_key", name="uq_raw_dataset_archives_dataset_key"),
        Index("ix_raw_dataset_archives_type_created", "dataset_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    dataset_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    workbook_format: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_encoding: Mapped[str] = mapped_column(String(32), default="gzip_base64", nullable=False)
    raw_file_payload: Mapped[str] = mapped_column(LONGTEXT_TYPE, nullable=False)
    sheet_names: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    primary_sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_columns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    header_row: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preview_rows: Mapped[list[list[str]]] = mapped_column(JSON, default=list, nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AdjustmentOpportunity(Base):
    __tablename__ = "adjustment_opportunities"
    __table_args__ = (
        UniqueConstraint("opportunity_key", name="uq_adjustment_opportunities_opportunity_key"),
        Index(
            "ix_adjustment_opportunities_lookup",
            "school_name_normalized",
            "major_code",
            "major_name_normalized",
            "region_name",
        ),
        Index("ix_adjustment_opportunities_source_year", "source_type", "year"),
        Index("ix_adjustment_opportunities_published", "published_at"),
        Index(
            "ix_adjustment_opportunities_broad_filters",
            "school_tier",
            "has_history",
            "is_long_track",
            "min_score_required",
        ),
        Index(
            "ix_adjustment_opportunities_reference_links",
            "school_tier",
            "reference_link_count",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opportunity_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_dataset_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    school_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    region_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    city_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    school_tier: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    major_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    major_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    major_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    study_mode: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    has_history: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    is_long_track: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    reference_link_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_score_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vacancy_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initial_score_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initial_score_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_score_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_score_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship()


class HistoricalAdjustmentProfile(Base):
    __tablename__ = "historical_adjustment_profiles"
    __table_args__ = (
        UniqueConstraint("profile_key", name="uq_historical_adjustment_profiles_profile_key"),
        Index(
            "ix_historical_adjustment_profiles_lookup",
            "school_name_normalized",
            "major_code",
            "major_name_normalized",
            "study_mode",
        ),
        Index("ix_historical_adjustment_profiles_year_source", "year", "source_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_dataset_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    school_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    region_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    city_name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    school_tier: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    major_code: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    major_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    major_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    study_mode: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vacancy_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initial_score_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initial_score_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_score_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adjustment_score_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship()


class MentorEvaluation(Base):
    __tablename__ = "mentor_evaluations"
    __table_args__ = (
        UniqueConstraint("review_key", name="uq_mentor_evaluations_review_key"),
        Index("ix_mentor_evaluations_school_department", "school_name_normalized", "department_name_normalized"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_dataset_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    mentor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mentor_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    review_text: Mapped[str] = mapped_column(LONGTEXT_TYPE, nullable=False)
    review_tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class HistoricalReleaseTimingProfile(Base):
    __tablename__ = "historical_release_timing_profiles"
    __table_args__ = (
        UniqueConstraint("profile_key", name="uq_historical_release_timing_profiles_profile_key"),
        Index("ix_historical_release_timing_profiles_school", "school_name_normalized"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    profile_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    school_name: Mapped[str] = mapped_column(String(255), nullable=False)
    school_name_normalized: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    peak_hour: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    peak_hour_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    window_start_md: Mapped[str | None] = mapped_column(String(16), nullable=True)
    window_end_md: Mapped[str | None] = mapped_column(String(16), nullable=True)
    consistency_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    school: Mapped["School | None"] = relationship()


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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    identities: Mapped[list["AccountIdentity"]] = relationship(back_populates="account", cascade="all, delete-orphan")
    roles: Mapped[list["AccountRole"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", foreign_keys="AccountRole.account_id"
    )
    entitlements: Mapped[list["AccountEntitlement"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", foreign_keys="AccountEntitlement.account_id"
    )
    payment_orders: Mapped[list["AccountPaymentOrder"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", foreign_keys="AccountPaymentOrder.account_id"
    )
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


class AccountIdentity(Base):
    __tablename__ = "account_identities"
    __table_args__ = (
        UniqueConstraint("identity_type", "login_name", name="uq_account_identities_type_login_name"),
        UniqueConstraint("identity_type", "provider_subject", "provider_app_id", name="uq_account_identities_type_subject_app"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    identity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    login_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_unionid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_app_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["PortalUser"] = relationship(back_populates="identities")


class AccountRole(Base):
    __tablename__ = "account_roles"
    __table_args__ = (UniqueConstraint("account_id", "role_code", name="uq_account_roles_account_role_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    granted_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("portal_users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["PortalUser"] = relationship(back_populates="roles", foreign_keys=[account_id])


class AccountEntitlement(Base):
    __tablename__ = "account_entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    granted_by_account_id: Mapped[str | None] = mapped_column(ForeignKey("portal_users.id"), nullable=True, index=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["PortalUser"] = relationship(back_populates="entitlements", foreign_keys=[account_id])


class AccountPaymentOrder(Base):
    __tablename__ = "account_payment_orders"
    __table_args__ = (
        UniqueConstraint("order_ref", name="uq_account_payment_orders_order_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), default="web_pay", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    duration_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="CNY", nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_order_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    provider_payment_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["PortalUser"] = relationship(back_populates="payment_orders", foreign_keys=[account_id])


class AccountBindCode(Base):
    __tablename__ = "account_bind_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_account_bind_codes_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_id: Mapped[str] = mapped_column(ForeignKey("portal_users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    bind_type: Mapped[str] = mapped_column(String(32), default="wechat_miniapp", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    claimed_by_shadow_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account: Mapped["PortalUser"] = relationship(foreign_keys=[account_id])
    claimed_by_shadow_user: Mapped["User | None"] = relationship(foreign_keys=[claimed_by_shadow_user_id])

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
    display_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_item_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    target_school_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_school_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_department_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_major_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_major_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_major_name_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
