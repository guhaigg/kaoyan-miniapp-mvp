from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timezone, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, Field

from ..db import SessionLocal
from ..models import (
    Content,
    ContentFile,
    Department,
    GovernanceAction,
    ParseArtifact,
    PortalEdge,
    PortalHostDecision,
    PortalNode,
    PortalUser,
    RawArtifact,
    School,
    SiteSection,
    WorkflowRun,
    WorkflowStep,
    sha256_hex,
    utcnow,
)
from .classification import sync_content_classification
from .site_section_bootstrap import bootstrap_site_sections

WORKFLOW_TYPE_SCHOOL_BOOTSTRAP = "school_portal_discovery"
WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP = "department_portal_discovery"
WORKFLOW_TYPE_SCHOOL_SECTION_DISCOVERY = "school_section_discovery"
WORKFLOW_TYPE_DEPARTMENT_SECTION_DISCOVERY = "department_section_discovery"
WORKFLOW_TYPE_DETAIL_FETCH = "detail_fetch"
WORKFLOW_TYPE_FILE_FETCH = "file_fetch"
WORKFLOW_TYPE_FILE_PARSE = "file_parse"
WORKFLOW_TYPE_SCOPE_REBUILD = "scope_rebuild"
WORKFLOW_TYPE_POLLUTION_CLEANUP = "pollution_cleanup"
WORKFLOW_TYPE_ANNOUNCEMENT_CATALOG_REFRESH = "announcement_catalog_refresh"
STEP_TYPE_OCR_ENQUEUE = "ocr_enqueue"
STEP_TYPE_CONTENT_RECLASSIFY = "content_reclassify"
STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG = "fetch_chsi_school_catalog"
STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG = "fetch_chsi_major_catalog"
STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS = "fetch_official_seed_rosters"
STEP_TYPE_FETCH_SCHOOL_HOMEPAGES = "fetch_school_homepages"
STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES = "build_department_candidates"
STEP_TYPE_MERGE_ANNOUNCEMENT_SEED_REGISTRY = "merge_announcement_seed_registry"
STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH = "enqueue_chsi_school_enrich"
STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT = "enrich_chsi_school_snapshot"
STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH = "await_chsi_school_enrich"
PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE = "chsi_school_catalog_base"
PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH = "chsi_school_enrich"
RULE_VERSION = "crawler_v2_explicit_seed_v2"
DEFAULT_BOOTSTRAP_FAMILIES = frozenset({"admissions", "notice"})
SUPPORTED_BOOTSTRAP_FAMILIES = frozenset({"admissions", "notice", "adjustment"})
STEP_LEASE_TIMEOUT = timedelta(minutes=10)
ASSET_WORKFLOW_TYPES = frozenset(
    {
        WORKFLOW_TYPE_SCOPE_REBUILD,
        WORKFLOW_TYPE_SCHOOL_BOOTSTRAP,
        WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP,
    }
)


class WorkflowPayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class SchoolBootstrapPayload(WorkflowPayloadModel):
    school_name: str
    homepage_url: str
    seed_urls: list[str] = Field(default_factory=list)
    max_sections: int = 12
    families: list[str] = Field(default_factory=list)
    seed_source: str | None = None


class DepartmentBootstrapPayload(SchoolBootstrapPayload):
    department_name: str
    department_type: str = "college"


class ScopeRebuildPayload(WorkflowPayloadModel):
    scope_type: str
    school_name: str
    department_name: str | None = None
    department_type: str = "college"
    homepage_url: str | None = None
    seed_urls: list[str] = Field(default_factory=list)
    max_sections: int = 12
    families: list[str] = Field(default_factory=list)
    seed_source: str | None = None


class SectionDiscoveryPayload(WorkflowPayloadModel):
    site_section_id: str
    source_url: str
    school_name: str | None = None
    department_name: str | None = None
    section_type: str | None = None
    discovery_category: str = "announcement"
    source_crawl_job_id: str | None = None


class DetailFetchPayload(WorkflowPayloadModel):
    site_section_id: str | None = None
    site_section_link_id: str
    source_url: str
    title: str | None = None
    school_name: str | None = None
    department_name: str | None = None
    section_type: str | None = None
    published_at: str | None = None
    seed_source: str | None = None


class FileParsePayload(WorkflowPayloadModel):
    content_file_id: str
    file_url: str | None = None
    site_section_link_id: str | None = None
    site_section_id: str | None = None
    title: str | None = None
    school_name: str | None = None
    department_name: str | None = None
    section_type: str | None = None
    published_at: str | None = None
    seed_source: str | None = None


class OcrEnqueuePayload(WorkflowPayloadModel):
    content_file_id: str
    file_url: str | None = None
    school_name: str | None = None
    department_name: str | None = None


class ContentReclassifyPayload(WorkflowPayloadModel):
    content_id: str
    school_name: str | None = None
    department_name: str | None = None


class PollutionCleanupPayload(WorkflowPayloadModel):
    scope_type: str
    scope_key: str


class AnnouncementCatalogRefreshPayload(WorkflowPayloadModel):
    school_names: list[str] = Field(default_factory=list)
    dry_run: bool = False
    sources: list[str] = Field(default_factory=list)


class ChsiSchoolEnrichPayload(WorkflowPayloadModel):
    school_code: str
    school_name: str
    chsi_school_url: str


class DeferredStep(RuntimeError):
    def __init__(self, *, result_payload: dict[str, Any], delay_seconds: int = 15):
        super().__init__("workflow step deferred")
        self.result_payload = result_payload
        self.delay_seconds = delay_seconds


class TerminalStepFailure(RuntimeError):
    def __init__(self, *, message: str, result_payload: dict[str, Any]):
        super().__init__(message)
        self.result_payload = result_payload


@dataclass(frozen=True)
class StepPolicy:
    step_type: str
    timeout_seconds: int
    max_attempts: int
    retry_backoff_seconds: int
    host_limit: int = 2


STEP_POLICIES: dict[str, StepPolicy] = {
    WORKFLOW_TYPE_SCHOOL_BOOTSTRAP: StepPolicy(
        step_type=WORKFLOW_TYPE_SCHOOL_BOOTSTRAP,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP: StepPolicy(
        step_type=WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    WORKFLOW_TYPE_SCHOOL_SECTION_DISCOVERY: StepPolicy(
        step_type=WORKFLOW_TYPE_SCHOOL_SECTION_DISCOVERY,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=20,
        host_limit=1,
    ),
    WORKFLOW_TYPE_DEPARTMENT_SECTION_DISCOVERY: StepPolicy(
        step_type=WORKFLOW_TYPE_DEPARTMENT_SECTION_DISCOVERY,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=20,
        host_limit=1,
    ),
    WORKFLOW_TYPE_DETAIL_FETCH: StepPolicy(
        step_type=WORKFLOW_TYPE_DETAIL_FETCH,
        timeout_seconds=180,
        max_attempts=3,
        retry_backoff_seconds=20,
        host_limit=2,
    ),
    WORKFLOW_TYPE_FILE_FETCH: StepPolicy(
        step_type=WORKFLOW_TYPE_FILE_FETCH,
        timeout_seconds=180,
        max_attempts=3,
        retry_backoff_seconds=20,
        host_limit=2,
    ),
    WORKFLOW_TYPE_FILE_PARSE: StepPolicy(
        step_type=WORKFLOW_TYPE_FILE_PARSE,
        timeout_seconds=240,
        max_attempts=3,
        retry_backoff_seconds=20,
        host_limit=2,
    ),
    WORKFLOW_TYPE_SCOPE_REBUILD: StepPolicy(
        step_type=WORKFLOW_TYPE_SCOPE_REBUILD,
        timeout_seconds=60,
        max_attempts=2,
        retry_backoff_seconds=10,
        host_limit=1,
    ),
    WORKFLOW_TYPE_POLLUTION_CLEANUP: StepPolicy(
        step_type=WORKFLOW_TYPE_POLLUTION_CLEANUP,
        timeout_seconds=120,
        max_attempts=1,
        retry_backoff_seconds=0,
        host_limit=1,
    ),
    STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG: StepPolicy(
        step_type=STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG,
        timeout_seconds=300,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG: StepPolicy(
        step_type=STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG,
        timeout_seconds=300,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS: StepPolicy(
        step_type=STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_FETCH_SCHOOL_HOMEPAGES: StepPolicy(
        step_type=STEP_TYPE_FETCH_SCHOOL_HOMEPAGES,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES: StepPolicy(
        step_type=STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES,
        timeout_seconds=300,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_MERGE_ANNOUNCEMENT_SEED_REGISTRY: StepPolicy(
        step_type=STEP_TYPE_MERGE_ANNOUNCEMENT_SEED_REGISTRY,
        timeout_seconds=180,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=1,
    ),
    STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH: StepPolicy(
        step_type=STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH,
        timeout_seconds=120,
        max_attempts=2,
        retry_backoff_seconds=10,
        host_limit=1,
    ),
    STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT: StepPolicy(
        step_type=STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
        timeout_seconds=300,
        max_attempts=2,
        retry_backoff_seconds=15,
        host_limit=2,
    ),
    STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH: StepPolicy(
        step_type=STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
        timeout_seconds=120,
        max_attempts=2,
        retry_backoff_seconds=10,
        host_limit=1,
    ),
    STEP_TYPE_OCR_ENQUEUE: StepPolicy(
        step_type=STEP_TYPE_OCR_ENQUEUE,
        timeout_seconds=60,
        max_attempts=2,
        retry_backoff_seconds=10,
        host_limit=1,
    ),
    STEP_TYPE_CONTENT_RECLASSIFY: StepPolicy(
        step_type=STEP_TYPE_CONTENT_RECLASSIFY,
        timeout_seconds=60,
        max_attempts=2,
        retry_backoff_seconds=10,
        host_limit=2,
    ),
}


def _compact(value: str | None) -> str:
    return "".join(str(value or "").strip().split())


def _host_from_url(url: str | None) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    return urlparse(text).hostname or None


def _as_utc(value):
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scope_key(*parts: str | None) -> str:
    values = [_compact(part) for part in parts if _compact(part)]
    return "::".join(values)


def _normalize_bootstrap_families(families: list[str] | set[str] | tuple[str, ...] | None) -> set[str]:
    normalized = {
        str(item or "").strip()
        for item in (families or [])
        if str(item or "").strip() in SUPPORTED_BOOTSTRAP_FAMILIES
    }
    return normalized or set(DEFAULT_BOOTSTRAP_FAMILIES)


def _resolve_actor_account_id(db: Session, actor_username: str | None) -> str | None:
    username = str(actor_username or "").strip()
    if not username:
        return None
    row = db.query(PortalUser.id).filter(PortalUser.username == username).limit(1).scalar()
    return str(row) if row else None


def _step_policy(step_type: str) -> StepPolicy:
    policy = STEP_POLICIES.get(step_type)
    if policy is None:
        return StepPolicy(step_type=step_type, timeout_seconds=300, max_attempts=2, retry_backoff_seconds=10)
    return policy


def _step_idempotency_key(
    *,
    step_type: str,
    scope_key: str,
    host_key: str | None,
    input_payload: dict[str, Any],
) -> str:
    for field in ("content_id", "content_file_id", "site_section_link_id", "site_section_id", "homepage_url"):
        value = str(input_payload.get(field) or "").strip()
        if value:
            return f"{step_type}:{scope_key}:{field}:{value}"
    families = ",".join(
        sorted(str(item or "").strip() for item in (input_payload.get("families") or []) if str(item or "").strip())
    )
    return f"{step_type}:{scope_key}:{families or host_key or 'none'}"


def _ensure_portal_node(
    db: Session,
    *,
    school_id: str | None,
    department_id: str | None,
    scope_type: str,
    scope_key: str,
    node_type: str,
    url: str,
    title: str | None,
    status: str,
    evidence: dict[str, Any],
) -> PortalNode:
    row = (
        db.query(PortalNode)
        .filter(
            PortalNode.scope_type == scope_type,
            PortalNode.scope_key == scope_key,
            PortalNode.node_type == node_type,
            PortalNode.url_hash == sha256_hex(url),
        )
        .one_or_none()
    )
    if row is None:
        row = PortalNode(
            school_id=school_id,
            department_id=department_id,
            scope_type=scope_type,
            scope_key=scope_key,
            node_type=node_type,
            url=url,
        )
        db.add(row)
    row.host = _host_from_url(url)
    row.url_hash = sha256_hex(url)
    row.title = title
    row.status = status
    row.evidence = evidence
    db.flush()
    return row


def _upsert_host_decision(
    db: Session,
    *,
    school_id: str | None,
    department_id: str | None,
    scope_type: str,
    scope_key: str,
    family: str,
    selected_host: str | None,
    candidate_hosts: list[str],
    evidence: dict[str, Any],
) -> PortalHostDecision:
    row = (
        db.query(PortalHostDecision)
        .filter(
            PortalHostDecision.scope_type == scope_type,
            PortalHostDecision.scope_key == scope_key,
            PortalHostDecision.family == family,
        )
        .one_or_none()
    )
    if row is None:
        row = PortalHostDecision(
            school_id=school_id,
            department_id=department_id,
            scope_type=scope_type,
            scope_key=scope_key,
            family=family,
        )
        db.add(row)
    row.selected_host = selected_host
    row.candidate_hosts = candidate_hosts
    row.confidence = 1.0 if selected_host else 0.0
    row.rule_version = RULE_VERSION
    row.decision_source = "workflow"
    row.status = "active"
    row.evidence = evidence
    db.flush()
    return row


def _ensure_portal_edge(
    db: Session,
    *,
    from_node_id: str,
    to_node_id: str,
    relation_type: str,
    evidence: dict[str, Any],
) -> PortalEdge:
    row = (
        db.query(PortalEdge)
        .filter(
            PortalEdge.from_node_id == from_node_id,
            PortalEdge.to_node_id == to_node_id,
            PortalEdge.relation_type == relation_type,
        )
        .one_or_none()
    )
    if row is None:
        row = PortalEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation_type=relation_type,
            evidence=evidence,
        )
        db.add(row)
    else:
        row.evidence = evidence
    db.flush()
    return row


def _record_raw_artifact(
    db: Session,
    *,
    workflow_step_id: str,
    artifact_type: str,
    source_url: str | None,
    payload: dict[str, Any],
    headers: dict[str, Any] | None = None,
) -> RawArtifact:
    row = RawArtifact(
        workflow_step_id=workflow_step_id,
        artifact_type=artifact_type,
        source_url=source_url,
        payload=payload,
        headers=headers or {},
    )
    db.add(row)
    db.flush()
    return row


def _record_parse_artifact(
    db: Session,
    *,
    workflow_step_id: str,
    artifact_type: str,
    source_url: str | None,
    payload: dict[str, Any],
) -> ParseArtifact:
    row = ParseArtifact(
        workflow_step_id=workflow_step_id,
        artifact_type=artifact_type,
        source_url=source_url,
        payload=payload,
    )
    db.add(row)
    db.flush()
    return row


def _record_governance_action(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    scope_type: str,
    scope_key: str,
    action_type: str,
    actor_account_id: str | None,
    payload: dict[str, Any],
) -> GovernanceAction:
    row = GovernanceAction(
        entity_type=entity_type,
        entity_id=entity_id,
        scope_type=scope_type,
        scope_key=scope_key,
        action_type=action_type,
        actor_account_id=actor_account_id,
        payload=payload,
    )
    db.add(row)
    db.flush()
    return row


def _validate_bootstrap_sections(
    *,
    sections: list[SiteSection],
    school: School,
    department: Department | None,
    department_mode: bool,
) -> None:
    for section in sections:
        if section.school_id != school.id:
            raise ValueError("bootstrap returned cross-school section")
        if department_mode:
            if department is None or section.department_id != department.id:
                raise ValueError("department bootstrap returned out-of-scope section")
        elif section.department_id is not None:
            raise ValueError("school bootstrap returned department-scoped section")


def _existing_active_run(
    db: Session,
    *,
    workflow_type: str,
    scope_type: str,
    scope_key: str,
) -> tuple[WorkflowRun, WorkflowStep] | None:
    run = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.workflow_type == workflow_type,
            WorkflowRun.scope_type == scope_type,
            WorkflowRun.scope_key == scope_key,
            WorkflowRun.status.in_(["pending", "running"]),
        )
        .order_by(WorkflowRun.created_at.desc())
        .first()
    )
    if run is None:
        return None
    step = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.run_id == run.id, WorkflowStep.status.in_(["pending", "running"]))
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .first()
    )
    if step is None:
        step = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.run_id == run.id)
            .order_by(WorkflowStep.created_at.desc(), WorkflowStep.id.desc())
            .first()
        )
    if step is None:
        return None
    return run, step


def _existing_active_step(
    db: Session,
    *,
    step_type: str,
    idempotency_key: str,
) -> tuple[WorkflowRun, WorkflowStep] | None:
    step = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.step_type == step_type,
            WorkflowStep.idempotency_key == idempotency_key,
            WorkflowStep.status.in_(["pending", "running"]),
        )
        .order_by(WorkflowStep.created_at.desc(), WorkflowStep.id.desc())
        .first()
    )
    if step is None:
        return None
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one_or_none()
    if run is None:
        return None
    return run, step


def _create_run_with_step(
    db: Session,
    *,
    workflow_type: str,
    step_type: str,
    scope_type: str,
    scope_key: str,
    scope_label: str,
    actor_username: str | None,
    input_payload: dict[str, Any],
    host_key: str | None = None,
    dedupe_mode: str = "none",
) -> tuple[WorkflowRun, WorkflowStep]:
    idempotency_key = _step_idempotency_key(
        step_type=step_type,
        scope_key=scope_key,
        host_key=host_key,
        input_payload=input_payload,
    )
    if dedupe_mode == "run_scope":
        active = _existing_active_run(
            db,
            workflow_type=workflow_type,
            scope_type=scope_type,
            scope_key=scope_key,
        )
        if active is not None:
            return active
    elif dedupe_mode == "step_idempotency":
        active = _existing_active_step(
            db,
            step_type=step_type,
            idempotency_key=idempotency_key,
        )
        if active is not None:
            return active

    actor_account_id = _resolve_actor_account_id(db, actor_username)
    policy = _step_policy(step_type)
    run = WorkflowRun(
        workflow_type=workflow_type,
        scope_type=scope_type,
        scope_key=scope_key,
        scope_label=scope_label,
        requested_by_account_id=actor_account_id,
        status="pending",
        request_payload=input_payload,
        result_payload={},
    )
    db.add(run)
    db.flush()
    step = WorkflowStep(
        run_id=run.id,
        step_type=step_type,
        scope_type=scope_type,
        scope_key=scope_key,
        host_key=host_key,
        status="pending",
        max_attempts=policy.max_attempts,
        timeout_seconds=policy.timeout_seconds,
        available_at=utcnow(),
        input_payload=input_payload,
        result_payload={},
        idempotency_key=idempotency_key,
    )
    db.add(step)
    db.flush()
    return run, step


def _create_child_step(
    db: Session,
    *,
    run: WorkflowRun,
    parent_step: WorkflowStep,
    step_type: str,
    host_key: str | None,
    input_payload: dict[str, Any],
) -> WorkflowStep:
    existing = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.run_id == run.id,
            WorkflowStep.parent_step_id == parent_step.id,
            WorkflowStep.step_type == step_type,
            WorkflowStep.status.in_(["pending", "running"]),
        )
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .first()
    )
    if existing is not None:
        return existing

    policy = _step_policy(step_type)
    child = WorkflowStep(
        run_id=run.id,
        parent_step_id=parent_step.id,
        step_type=step_type,
        scope_type=parent_step.scope_type,
        scope_key=parent_step.scope_key,
        host_key=host_key,
        status="pending",
        max_attempts=policy.max_attempts,
        timeout_seconds=policy.timeout_seconds,
        available_at=utcnow(),
        input_payload=input_payload,
        result_payload={},
        idempotency_key=_step_idempotency_key(
            step_type=step_type,
            scope_key=parent_step.scope_key,
            host_key=host_key,
            input_payload=input_payload,
        ),
    )
    db.add(child)
    db.flush()
    return child


def _create_idempotent_child_step(
    db: Session,
    *,
    run: WorkflowRun,
    parent_step: WorkflowStep,
    step_type: str,
    host_key: str | None,
    input_payload: dict[str, Any],
) -> WorkflowStep:
    school_code = str(input_payload.get("school_code") or "").strip()
    idempotency_key = (
        f"{step_type}:{parent_step.scope_key}:school_code:{school_code}"
        if school_code
        else _step_idempotency_key(
            step_type=step_type,
            scope_key=parent_step.scope_key,
            host_key=host_key,
            input_payload=input_payload,
        )
    )
    existing = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.run_id == run.id,
            WorkflowStep.parent_step_id == parent_step.id,
            WorkflowStep.step_type == step_type,
            WorkflowStep.idempotency_key == idempotency_key,
        )
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .first()
    )
    if existing is not None:
        return existing

    policy = _step_policy(step_type)
    child = WorkflowStep(
        run_id=run.id,
        parent_step_id=parent_step.id,
        step_type=step_type,
        scope_type=parent_step.scope_type,
        scope_key=parent_step.scope_key,
        host_key=host_key,
        status="pending",
        max_attempts=policy.max_attempts,
        timeout_seconds=policy.timeout_seconds,
        available_at=utcnow(),
        input_payload=input_payload,
        result_payload={},
        idempotency_key=idempotency_key,
    )
    db.add(child)
    db.flush()
    return child


def create_school_bootstrap_run(
    db: Session,
    *,
    school_name: str,
    homepage_url: str,
    seed_urls: list[str],
    actor_username: str | None,
    max_sections: int = 12,
    families: list[str] | set[str] | tuple[str, ...] | None = None,
    seed_source: str = "payload",
) -> tuple[WorkflowRun, WorkflowStep]:
    school = db.query(School).filter(School.name == school_name.strip()).one_or_none()
    if school is None:
        school = School(name=school_name.strip(), aliases=[], enabled=1)
        db.add(school)
        db.flush()
    normalized_families = sorted(_normalize_bootstrap_families(families))
    payload = SchoolBootstrapPayload(
        school_name=school.name,
        homepage_url=homepage_url.strip(),
        seed_urls=[str(url).strip() for url in seed_urls if str(url).strip()],
        max_sections=max_sections,
        families=normalized_families,
        seed_source=seed_source,
    ).model_dump()
    return _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_SCHOOL_BOOTSTRAP,
        step_type=WORKFLOW_TYPE_SCHOOL_BOOTSTRAP,
        scope_type="school",
        scope_key=_scope_key(school.name) or school.id,
        scope_label=school.name,
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(homepage_url),
        dedupe_mode="run_scope",
    )


def create_department_bootstrap_run(
    db: Session,
    *,
    school_name: str,
    department_name: str,
    homepage_url: str,
    seed_urls: list[str],
    actor_username: str | None,
    department_type: str = "college",
    max_sections: int = 12,
    families: list[str] | set[str] | tuple[str, ...] | None = None,
    seed_source: str = "payload",
) -> tuple[WorkflowRun, WorkflowStep]:
    school = db.query(School).filter(School.name == school_name.strip()).one_or_none()
    if school is None:
        school = School(name=school_name.strip(), aliases=[], enabled=1)
        db.add(school)
        db.flush()
    department = (
        db.query(Department)
        .filter(Department.school_id == school.id, Department.name == department_name.strip())
        .one_or_none()
    )
    if department is None:
        department = Department(
            school_id=school.id,
            name=department_name.strip(),
            aliases=[],
            department_type=department_type,
            enabled=1,
        )
        db.add(department)
        db.flush()
    normalized_families = sorted(_normalize_bootstrap_families(families))
    payload = DepartmentBootstrapPayload(
        school_name=school.name,
        department_name=department.name,
        department_type=department.department_type,
        homepage_url=homepage_url.strip(),
        seed_urls=[str(url).strip() for url in seed_urls if str(url).strip()],
        max_sections=max_sections,
        families=normalized_families,
        seed_source=seed_source,
    ).model_dump()
    return _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP,
        step_type=WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP,
        scope_type="department",
        scope_key=_scope_key(school.name, department.name) or department.id,
        scope_label=f"{school.name}/{department.name}",
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(homepage_url),
        dedupe_mode="run_scope",
    )


def create_scope_rebuild_run(
    db: Session,
    *,
    scope_type: str,
    school_name: str,
    actor_username: str | None,
    department_name: str | None = None,
    homepage_url: str | None = None,
    seed_urls: list[str] | None = None,
    max_sections: int = 12,
    families: list[str] | set[str] | tuple[str, ...] | None = None,
    seed_source: str | None = None,
) -> tuple[WorkflowRun, WorkflowStep]:
    normalized_families = sorted(_normalize_bootstrap_families(families))
    payload = ScopeRebuildPayload(
        scope_type=scope_type,
        school_name=school_name.strip(),
        department_name=str(department_name or "").strip() or None,
        homepage_url=str(homepage_url or "").strip() or None,
        seed_urls=[str(url).strip() for url in (seed_urls or []) if str(url).strip()],
        max_sections=max_sections,
        families=normalized_families,
        seed_source=str(seed_source or "").strip() or None,
    ).model_dump()
    return _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_SCOPE_REBUILD,
        step_type=WORKFLOW_TYPE_SCOPE_REBUILD,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or _compact(school_name),
        scope_label="/".join(part for part in [school_name.strip(), str(department_name or "").strip()] if part),
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(homepage_url),
        dedupe_mode="run_scope",
    )


def create_announcement_catalog_refresh_run(
    db: Session,
    *,
    actor_username: str | None,
    school_names: list[str] | None = None,
    dry_run: bool = False,
    sources: list[str] | None = None,
) -> tuple[WorkflowRun, WorkflowStep]:
    from .announcement_foundation import ANNOUNCEMENT_FOUNDATION_SCOPE_KEY

    normalized_school_names = list(
        dict.fromkeys(str(item or "").strip() for item in (school_names or []) if str(item or "").strip())
    )
    normalized_sources = list(dict.fromkeys(str(item or "").strip() for item in (sources or []) if str(item or "").strip()))
    payload = AnnouncementCatalogRefreshPayload(
        school_names=normalized_school_names,
        dry_run=bool(dry_run),
        sources=normalized_sources,
    ).model_dump()
    return _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_ANNOUNCEMENT_CATALOG_REFRESH,
        step_type=STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG,
        scope_type="school",
        scope_key=ANNOUNCEMENT_FOUNDATION_SCOPE_KEY,
        scope_label="announcement foundation",
        actor_username=actor_username,
        input_payload=payload,
        host_key="yz.chsi.com.cn",
        dedupe_mode="run_scope",
    )


def _scope_parts_for_section(section: SiteSection | None) -> tuple[str, str | None, str]:
    school_name = section.school.name if section and section.school else ""
    department_name = section.department.name if section and section.department else None
    scope_type = "department" if department_name else "school"
    return school_name, department_name, scope_type


def _detail_fetch_payload_from_link(link) -> dict[str, Any]:
    section = link.site_section if link else None
    school_name, department_name, _scope_type = _scope_parts_for_section(section)
    return DetailFetchPayload(
        site_section_id=section.id if section else None,
        site_section_link_id=link.id,
        source_url=link.link_url,
        title=link.title,
        school_name=school_name or None,
        department_name=department_name,
        section_type=section.section_type if section else None,
        published_at=link.published_at.isoformat() if link and link.published_at else None,
        seed_source="approved_section_asset",
    ).model_dump()


def _file_parse_payload_from_record(file_record: ContentFile) -> dict[str, Any]:
    link = file_record.site_section_link
    section = link.site_section if link else None
    school_name, department_name, _scope_type = _scope_parts_for_section(section)
    return FileParsePayload(
        content_file_id=file_record.id,
        file_url=file_record.file_url,
        site_section_link_id=link.id if link else None,
        site_section_id=section.id if section else None,
        title=link.title if link else None,
        school_name=school_name or None,
        department_name=department_name,
        section_type=section.section_type if section else None,
        published_at=link.published_at.isoformat() if link and link.published_at else None,
        seed_source="approved_section_asset",
    ).model_dump()


def queue_section_discovery_retry(
    db: Session,
    *,
    section: SiteSection,
    actor_username: str | None,
    source_crawl_job_id: str | None = None,
) -> tuple[WorkflowRun, WorkflowStep]:
    school_name, department_name, scope_type = _scope_parts_for_section(section)
    payload = SectionDiscoveryPayload(
        site_section_id=section.id,
        source_url=section.section_url,
        school_name=school_name or None,
        department_name=department_name,
        section_type=section.section_type,
        discovery_category=section.discovery_category,
        source_crawl_job_id=source_crawl_job_id,
    ).model_dump()
    workflow_type = (
        WORKFLOW_TYPE_DEPARTMENT_SECTION_DISCOVERY
        if scope_type == "department"
        else WORKFLOW_TYPE_SCHOOL_SECTION_DISCOVERY
    )
    run, step = _create_run_with_step(
        db,
        workflow_type=workflow_type,
        step_type=workflow_type,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or section.id,
        scope_label="/".join(part for part in [school_name, department_name or ""] if part) or section.name,
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(section.section_url),
        dedupe_mode="step_idempotency",
    )
    section.last_discovery_status = "queued"
    section.last_error = None
    db.flush()
    return run, step


def queue_detail_fetch_retry(
    db: Session,
    *,
    link,
    actor_username: str | None,
) -> tuple[WorkflowRun, WorkflowStep]:
    section = link.site_section if link else None
    school_name, department_name, scope_type = _scope_parts_for_section(section)
    payload = _detail_fetch_payload_from_link(link)
    run, step = _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_DETAIL_FETCH,
        step_type=WORKFLOW_TYPE_DETAIL_FETCH,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or link.id,
        scope_label="/".join(part for part in [school_name, department_name or ""] if part) or (link.title or link.id),
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(link.link_url),
        dedupe_mode="step_idempotency",
    )
    link.status = "enqueued"
    link.snapshot_meta = {
        **dict(link.snapshot_meta or {}),
        "detail_workflow_run_id": run.id,
        "detail_workflow_step_id": step.id,
    }
    db.flush()
    return run, step


def queue_file_parse_retry(
    db: Session,
    *,
    file_record: ContentFile,
    actor_username: str | None,
) -> tuple[WorkflowRun, WorkflowStep]:
    link = file_record.site_section_link
    section = link.site_section if link else None
    school_name, department_name, scope_type = _scope_parts_for_section(section)
    payload = _file_parse_payload_from_record(file_record)
    run, step = _create_run_with_step(
        db,
        workflow_type=WORKFLOW_TYPE_FILE_PARSE,
        step_type=WORKFLOW_TYPE_FILE_PARSE,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or file_record.id,
        scope_label="/".join(part for part in [school_name, department_name or ""] if part),
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(file_record.file_url),
        dedupe_mode="step_idempotency",
    )
    file_record.parse_status = "pending"
    file_record.ocr_status = "not_started"
    file_record.file_meta = {
        **dict(file_record.file_meta or {}),
        "parse_workflow_run_id": run.id,
        "parse_workflow_step_id": step.id,
        "retry_requested_at": utcnow().isoformat(),
    }
    if link is not None:
        link.status = "file_recorded"
        link.snapshot_meta = {
            **dict(link.snapshot_meta or {}),
            "parse_workflow_run_id": run.id,
            "parse_workflow_step_id": step.id,
        }
    db.flush()
    return run, step


def queue_ocr_retry(db: Session, *, file_record: ContentFile, actor_username: str | None) -> tuple[WorkflowRun, WorkflowStep]:
    link = file_record.site_section_link
    section = link.site_section if link else None
    school_name, department_name, scope_type = _scope_parts_for_section(section)
    payload = OcrEnqueuePayload(
        content_file_id=file_record.id,
        file_url=file_record.file_url,
        school_name=school_name or None,
        department_name=department_name,
    ).model_dump()
    run, step = _create_run_with_step(
        db,
        workflow_type=STEP_TYPE_OCR_ENQUEUE,
        step_type=STEP_TYPE_OCR_ENQUEUE,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or file_record.id,
        scope_label="/".join(part for part in [school_name, department_name or ""] if part),
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(file_record.file_url),
        dedupe_mode="step_idempotency",
    )
    file_record.ocr_status = "queued"
    db.flush()
    return run, step


def queue_content_reclassify(db: Session, *, content: Content, actor_username: str | None) -> tuple[WorkflowRun, WorkflowStep]:
    extra = dict(content.extra or {})
    school_name = str(getattr(getattr(content, "school", None), "name", None) or extra.get("school_name") or "").strip()
    department_name = str(extra.get("department_name") or "").strip() or None
    scope_type = "department" if department_name else "school"
    payload = ContentReclassifyPayload(
        content_id=content.id,
        school_name=school_name or None,
        department_name=department_name,
    ).model_dump()
    return _create_run_with_step(
        db,
        workflow_type=STEP_TYPE_CONTENT_RECLASSIFY,
        step_type=STEP_TYPE_CONTENT_RECLASSIFY,
        scope_type=scope_type,
        scope_key=_scope_key(school_name, department_name) or content.id,
        scope_label="/".join(part for part in [school_name, department_name or ""] if part),
        actor_username=actor_username,
        input_payload=payload,
        host_key=_host_from_url(content.source_url),
        dedupe_mode="step_idempotency",
    )


def latest_scope_run(
    db: Session,
    *,
    scope_type: str,
    school_name: str,
    department_name: str | None = None,
    workflow_types: set[str] | frozenset[str] | None = None,
) -> WorkflowRun | None:
    query = db.query(WorkflowRun).filter(
        WorkflowRun.scope_type == scope_type,
        WorkflowRun.scope_key == _scope_key(school_name, department_name),
    )
    normalized_workflow_types = {str(item or "").strip() for item in (workflow_types or set()) if str(item or "").strip()}
    if normalized_workflow_types:
        query = query.filter(WorkflowRun.workflow_type.in_(sorted(normalized_workflow_types)))
    return query.order_by(WorkflowRun.created_at.desc()).first()


def _running_host_counts(db: Session) -> dict[str, int]:
    stale_cutoff = utcnow() - STEP_LEASE_TIMEOUT
    rows = (
        db.query(WorkflowStep.host_key)
        .filter(
            WorkflowStep.status == "running",
            WorkflowStep.host_key.is_not(None),
            or_(WorkflowStep.leased_at.is_(None), WorkflowStep.leased_at > stale_cutoff),
        )
        .all()
    )
    counts: dict[str, int] = {}
    for (host_key,) in rows:
        host = str(host_key or "").strip()
        if not host:
            continue
        counts[host] = counts.get(host, 0) + 1
    return counts


def _lock_pending_steps(db: Session, batch_size: int, worker_name: str) -> list[str]:
    stale_cutoff = utcnow() - STEP_LEASE_TIMEOUT
    query = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.available_at <= utcnow(),
            or_(
                WorkflowStep.status == "pending",
                and_(
                    WorkflowStep.status == "running",
                    WorkflowStep.leased_at.is_not(None),
                    WorkflowStep.leased_at <= stale_cutoff,
                ),
            ),
        )
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .limit(max(batch_size * 4, batch_size))
    )
    dialect_name = (db.bind.dialect.name if db.bind else "").lower()
    if dialect_name != "sqlite":
        query = query.with_for_update(skip_locked=True)
    rows = query.all()
    if not rows:
        return []

    host_counts = _running_host_counts(db)
    selected: list[WorkflowStep] = []
    for row in rows:
        policy = _step_policy(row.step_type)
        host_key = str(row.host_key or "").strip() or None
        is_stale_reclaim = row.status == "running"
        if host_key and not is_stale_reclaim and int(host_counts.get(host_key, 0)) >= int(policy.host_limit):
            continue
        selected.append(row)
        if host_key:
            host_counts[host_key] = int(host_counts.get(host_key, 0)) + 1
        if len(selected) >= batch_size:
            break

    if not selected:
        return []

    now = utcnow()
    for row in selected:
        was_stale_running = row.status == "running"
        if was_stale_running:
            result_payload = dict(row.result_payload or {})
            result_payload["lease_reclaimed_at"] = now.isoformat()
            row.result_payload = result_payload
        row.status = "running"
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.lease_owner = worker_name
        row.leased_at = now
        row.started_at = row.started_at or now
        row.finished_at = None
        if row.run is not None:
            row.run.status = "running"
            row.run.started_at = row.run.started_at or now
    db.commit()
    return [row.id for row in selected]


def _refresh_run_status(db: Session, run_id: str) -> None:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).one()
    steps = (
        db.query(WorkflowStep)
        .filter(WorkflowStep.run_id == run_id)
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .all()
    )
    if not steps:
        run.status = "done"
        run.finished_at = utcnow()
        return

    started_values = [_as_utc(step.started_at) for step in steps if step.started_at is not None]
    finished_values = [_as_utc(step.finished_at) for step in steps if step.finished_at is not None]
    latest_result = next((dict(step.result_payload or {}) for step in reversed(steps) if step.result_payload), {})

    run.started_at = min(started_values) if started_values else run.started_at
    run.result_payload = latest_result

    if any(step.status == "failed" for step in steps):
        failed_step = next(step for step in reversed(steps) if step.status == "failed")
        run.status = "failed"
        run.error_message = failed_step.error_message
        run.finished_at = failed_step.finished_at or (max(finished_values) if finished_values else utcnow())
        return

    if any(step.status in {"pending", "running"} for step in steps):
        run.status = "running" if any(step.status == "running" for step in steps) or started_values else "pending"
        run.error_message = None
        run.finished_at = None
        return

    run.status = "done"
    run.error_message = None
    run.finished_at = max(finished_values) if finished_values else utcnow()


def _mark_step_done(db: Session, step: WorkflowStep, result_payload: dict[str, Any]) -> None:
    step.status = "done"
    step.result_payload = result_payload
    step.finished_at = utcnow()
    step.error_type = None
    step.error_message = None
    step.lease_owner = None
    step.leased_at = None
    _refresh_run_status(db, step.run_id)
    db.commit()


def _mark_step_deferred(
    db: Session,
    step: WorkflowStep,
    *,
    result_payload: dict[str, Any],
    delay_seconds: int,
) -> None:
    step.status = "pending"
    step.result_payload = result_payload
    step.available_at = utcnow() + timedelta(seconds=max(1, delay_seconds))
    step.finished_at = None
    step.error_type = None
    step.error_message = None
    step.lease_owner = None
    step.leased_at = None
    _refresh_run_status(db, step.run_id)
    db.commit()


def _mark_step_failed(
    db: Session,
    step: WorkflowStep,
    exc: Exception,
    *,
    result_payload: dict[str, Any] | None = None,
) -> None:
    policy = _step_policy(step.step_type)
    step.error_type = type(exc).__name__
    step.error_message = str(exc)[:2000]
    if result_payload is not None:
        step.result_payload = result_payload
    step.lease_owner = None
    step.leased_at = None
    retryable = not isinstance(exc, (ValueError, TerminalStepFailure))
    if retryable and int(step.attempt_count or 0) < int(max(1, step.max_attempts or policy.max_attempts)):
        step.status = "pending"
        step.available_at = utcnow() + timedelta(seconds=max(1, policy.retry_backoff_seconds * int(step.attempt_count or 1)))
        step.finished_at = None
    else:
        step.status = "failed"
        step.finished_at = utcnow()
    _refresh_run_status(db, step.run_id)
    db.commit()


def _process_scope_rebuild_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = ScopeRebuildPayload.model_validate(step.input_payload or {})
    scope_type = str(payload.scope_type or "").strip()
    school_name = str(payload.school_name or "").strip()
    department_name = str(payload.department_name or "").strip() or None
    homepage_url = str(payload.homepage_url or "").strip()
    if scope_type not in {"school", "department"}:
        raise ValueError("scope_type must be school or department")
    if not school_name or not homepage_url:
        raise ValueError("scope rebuild requires school_name and homepage_url")

    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    child_step_type = WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP if scope_type == "department" else WORKFLOW_TYPE_SCHOOL_BOOTSTRAP
    child_payload = (
        DepartmentBootstrapPayload(
            school_name=school_name,
            department_name=department_name or "",
            department_type=str(payload.department_type or "college"),
            homepage_url=homepage_url,
            seed_urls=[str(url).strip() for url in (payload.seed_urls or []) if str(url).strip()],
            max_sections=max(1, int(payload.max_sections or 12)),
            families=sorted(_normalize_bootstrap_families(payload.families)),
            seed_source=str(payload.seed_source or "").strip() or None,
        ).model_dump()
        if scope_type == "department"
        else SchoolBootstrapPayload(
            school_name=school_name,
            homepage_url=homepage_url,
            seed_urls=[str(url).strip() for url in (payload.seed_urls or []) if str(url).strip()],
            max_sections=max(1, int(payload.max_sections or 12)),
            families=sorted(_normalize_bootstrap_families(payload.families)),
            seed_source=str(payload.seed_source or "").strip() or None,
        ).model_dump()
    )
    child = _create_child_step(
        db,
        run=run,
        parent_step=step,
        step_type=child_step_type,
        host_key=_host_from_url(homepage_url),
        input_payload=child_payload,
    )
    db.flush()
    return {
        "scope_type": scope_type,
        "scope_key": step.scope_key,
        "child_step_id": child.id,
        "child_step_type": child.step_type,
        "seed_source": child_payload.get("seed_source"),
    }


def _announcement_catalog_refresh_host_key(step_type: str) -> str | None:
    if step_type in {
        STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG,
        STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
        STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG,
    }:
        return "yz.chsi.com.cn"
    if step_type == STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS:
        return "yz.chsi.com.cn"
    if step_type == STEP_TYPE_FETCH_SCHOOL_HOMEPAGES:
        return "raw.githubusercontent.com"
    return None


def _queue_next_announcement_catalog_step(
    db: Session,
    *,
    step: WorkflowStep,
    next_step_type: str | None,
    payload: AnnouncementCatalogRefreshPayload,
) -> WorkflowStep | None:
    if next_step_type is None:
        return None
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    return _create_child_step(
        db,
        run=run,
        parent_step=step,
        step_type=next_step_type,
        host_key=_announcement_catalog_refresh_host_key(next_step_type),
        input_payload=payload.model_dump(),
    )


def _process_fetch_chsi_school_catalog_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import (
        CHSI_SCHOOL_CATALOG_URL,
        foundation_paths,
        fetch_chsi_school_catalog,
    )

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    schools = fetch_chsi_school_catalog(school_names=payload.school_names or None)
    _record_parse_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type=PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE,
        source_url=CHSI_SCHOOL_CATALOG_URL,
        payload={"schools": schools},
    )
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH,
        payload=payload,
    )
    return {
        "school_count": len(schools),
        "base_dir": str(paths.base_dir),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_enqueue_chsi_school_enrich_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import foundation_paths

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    base_artifact = (
        db.query(ParseArtifact)
        .filter(
            ParseArtifact.workflow_step_id == step.parent_step_id,
            ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE,
        )
        .order_by(ParseArtifact.created_at.desc(), ParseArtifact.id.desc())
        .first()
    )
    if base_artifact is None:
        raise ValueError("missing chsi school catalog base artifact")

    base_schools = list((base_artifact.payload or {}).get("schools") or [])
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    child_ids: list[str] = []
    for school in base_schools:
        child = _create_idempotent_child_step(
            db,
            run=run,
            parent_step=step,
            step_type=STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
            host_key="yz.chsi.com.cn",
            input_payload=ChsiSchoolEnrichPayload(
                school_code=str(school.get("school_code") or ""),
                school_name=str(school.get("school_name") or ""),
                chsi_school_url=str(school.get("chsi_school_url") or ""),
            ).model_dump(),
        )
        child_ids.append(child.id)
    barrier = _create_idempotent_child_step(
        db,
        run=run,
        parent_step=step,
        step_type=STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH,
        host_key=None,
        input_payload=payload.model_dump(),
    )
    return {
        "queued_school_count": len(child_ids),
        "child_step_ids": child_ids,
        "barrier_step_id": barrier.id,
        "base_dir": str(paths.base_dir),
    }


def _process_enrich_chsi_school_snapshot_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import enrich_chsi_school_entry

    payload = ChsiSchoolEnrichPayload.model_validate(step.input_payload or {})
    school = enrich_chsi_school_entry(payload.model_dump())
    _record_parse_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type=PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH,
        source_url=payload.chsi_school_url,
        payload=school,
    )
    source_meta = dict(school.get("source_meta") or {})
    return {
        "school_code": payload.school_code,
        "school_name": payload.school_name,
        "seed_hint_count": len(source_meta.get("seed_hint_urls") or []),
        "has_department_page": bool(source_meta.get("department_page_url")),
        "has_major_page": bool(source_meta.get("major_page_url")),
    }


def _process_await_chsi_school_enrich_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import foundation_paths, merge_chsi_school_catalog

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    children = (
        db.query(WorkflowStep)
        .filter(
            WorkflowStep.run_id == step.run_id,
            WorkflowStep.parent_step_id == step.parent_step_id,
            WorkflowStep.step_type == STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT,
        )
        .order_by(WorkflowStep.created_at.asc(), WorkflowStep.id.asc())
        .all()
    )
    succeeded = [child for child in children if child.status == "done"]
    failed = [child for child in children if child.status == "failed"]
    pending = [child for child in children if child.status in {"pending", "running"}]
    summary = {
        "total_school_count": len(children),
        "succeeded_school_count": len(succeeded),
        "failed_school_count": len(failed),
        "pending_school_count": len(pending),
        "failed_schools": [
            {
                "school_code": str((child.input_payload or {}).get("school_code") or ""),
                "school_name": str((child.input_payload or {}).get("school_name") or ""),
                "error_type": child.error_type,
                "error_message": child.error_message,
            }
            for child in failed
        ],
        "base_dir": str(paths.base_dir),
    }
    if pending:
        raise DeferredStep(result_payload=summary, delay_seconds=15)
    if failed:
        raise TerminalStepFailure(
            message="chsi school enrich barrier failed",
            result_payload={**summary, "terminal_reason": "chsi_school_enrich_failed"},
        )

    enqueue_step = db.query(WorkflowStep).filter(WorkflowStep.id == step.parent_step_id).one_or_none()
    if enqueue_step is None or not enqueue_step.parent_step_id:
        raise ValueError("missing chsi school enrich parent chain")
    base_artifact = (
        db.query(ParseArtifact)
        .filter(
            ParseArtifact.workflow_step_id == enqueue_step.parent_step_id,
            ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_CATALOG_BASE,
        )
        .order_by(ParseArtifact.created_at.desc(), ParseArtifact.id.desc())
        .first()
    )
    if base_artifact is None:
        raise ValueError("missing chsi school catalog base artifact")

    child_ids = [child.id for child in succeeded]
    enrich_artifacts = (
        db.query(ParseArtifact)
        .filter(
            ParseArtifact.workflow_step_id.in_(child_ids or [""]),
            ParseArtifact.artifact_type == PARSE_ARTIFACT_TYPE_CHSI_SCHOOL_ENRICH,
        )
        .order_by(ParseArtifact.created_at.asc(), ParseArtifact.id.asc())
        .all()
        if child_ids
        else []
    )
    enrich_rows = [artifact.payload for artifact in enrich_artifacts]
    merged = merge_chsi_school_catalog(
        list((base_artifact.payload or {}).get("schools") or []),
        enrich_rows,
        paths=paths,
    )
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG,
        payload=payload,
    )
    return {
        **summary,
        "school_count": len(merged),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_fetch_chsi_major_catalog_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import fetch_chsi_major_catalog, foundation_paths

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    schools = list(json.loads(paths.school_catalog.read_text(encoding="utf-8"))) if paths.school_catalog.exists() else []
    majors = fetch_chsi_major_catalog(schools, paths=paths)
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS,
        payload=payload,
    )
    return {
        "major_count": len(majors),
        "base_dir": str(paths.base_dir),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_fetch_official_seed_rosters_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import fetch_official_seed_rosters, foundation_paths

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    records = fetch_official_seed_rosters(paths=paths)
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_FETCH_SCHOOL_HOMEPAGES,
        payload=payload,
    )
    return {
        "official_seed_candidate_count": len(records),
        "base_dir": str(paths.base_dir),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_fetch_school_homepages_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import fetch_school_homepages, foundation_paths

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    rows = fetch_school_homepages(paths=paths)
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES,
        payload=payload,
    )
    return {
        "homepage_count": len(rows),
        "base_dir": str(paths.base_dir),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_build_department_candidates_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import build_department_candidates, foundation_paths

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    schools = list(json.loads(paths.school_catalog.read_text(encoding="utf-8"))) if paths.school_catalog.exists() else []
    departments, candidates = build_department_candidates(schools, paths=paths)
    next_step = _queue_next_announcement_catalog_step(
        db,
        step=step,
        next_step_type=STEP_TYPE_MERGE_ANNOUNCEMENT_SEED_REGISTRY,
        payload=payload,
    )
    return {
        "department_count": len(departments),
        "department_candidate_count": len(candidates),
        "base_dir": str(paths.base_dir),
        "child_step_id": next_step.id if next_step is not None else None,
    }


def _process_merge_announcement_seed_registry_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    from .announcement_foundation import foundation_paths, merge_announcement_seed_registry

    payload = AnnouncementCatalogRefreshPayload.model_validate(step.input_payload or {})
    paths = foundation_paths()
    diff_payload = merge_announcement_seed_registry(paths=paths, dry_run=payload.dry_run)
    return {
        "base_dir": str(paths.base_dir),
        "dry_run": payload.dry_run,
        "registry_diff": diff_payload,
    }


def _process_bootstrap_step(db: Session, step: WorkflowStep, *, department_mode: bool) -> dict[str, Any]:
    payload = (
        DepartmentBootstrapPayload.model_validate(step.input_payload or {})
        if department_mode
        else SchoolBootstrapPayload.model_validate(step.input_payload or {})
    )
    school_name = str(payload.school_name or "").strip()
    department_name = str(getattr(payload, "department_name", None) or "").strip() or None
    homepage_url = str(payload.homepage_url or "").strip()
    if not school_name or not homepage_url:
        raise ValueError("school_name and homepage_url are required")

    seed_urls = [str(url).strip() for url in (payload.seed_urls or []) if str(url).strip()]
    max_sections = max(1, int(payload.max_sections or 12))
    families = _normalize_bootstrap_families(payload.families)
    family_key = "adjustment" if families == {"adjustment"} else "announcement"
    portal_scope = "graduate_admissions" if families == set(DEFAULT_BOOTSTRAP_FAMILIES) else None
    result = bootstrap_site_sections(
        db,
        school_name=school_name,
        homepage_url=homepage_url,
        department_name=department_name if department_mode else None,
        department_type=str(getattr(payload, "department_type", "college") or "college"),
        seed_urls=seed_urls,
        enabled=False,
        queue_discovery=False,
        max_sections=max_sections,
        families=families,
        portal_scope=portal_scope,
    )
    school = result["school"]
    department = None
    if department_mode and department_name:
        department = (
            db.query(Department)
            .filter(Department.school_id == school.id, Department.name == department_name)
            .one_or_none()
        )
    sections = list(result["items"])
    _validate_bootstrap_sections(
        sections=sections,
        school=school,
        department=department,
        department_mode=department_mode,
    )
    scope_type = "department" if department_mode else "school"
    scope_key = _scope_key(school_name, department_name if department_mode else None) or school.id
    actor_account_id = (
        db.query(WorkflowRun.requested_by_account_id)
        .filter(WorkflowRun.id == step.run_id)
        .limit(1)
        .scalar()
    )
    raw_artifact = _record_raw_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type="bootstrap_input",
        source_url=homepage_url,
        payload={
            "scope_type": scope_type,
            "scope_key": scope_key,
            "school_name": school_name,
            "department_name": department_name,
            "homepage_url": homepage_url,
            "seed_urls": seed_urls,
            "families": sorted(families),
            "seed_source": str(payload.seed_source or "").strip() or None,
        },
    )
    homepage_node = _ensure_portal_node(
        db,
        school_id=school.id,
        department_id=department.id if department else None,
        scope_type=scope_type,
        scope_key=scope_key,
        node_type="homepage",
        url=homepage_url,
        title=school_name if not department_mode else f"{school_name}/{department_name}",
        status="approved",
        evidence={"source": "explicit_homepage", "raw_artifact_id": raw_artifact.id},
    )
    seed_nodes: list[PortalNode] = []
    for seed_url in seed_urls:
        seed_node = _ensure_portal_node(
            db,
            school_id=school.id,
            department_id=department.id if department else None,
            scope_type=scope_type,
            scope_key=scope_key,
            node_type="seed",
            url=seed_url,
            title=f"{scope_key} seed",
            status="approved",
            evidence={"source": "explicit_seed", "raw_artifact_id": raw_artifact.id},
        )
        seed_nodes.append(seed_node)
        if seed_node.id != homepage_node.id:
            _ensure_portal_edge(
                db,
                from_node_id=homepage_node.id,
                to_node_id=seed_node.id,
                relation_type="explicit_seed",
                evidence={"workflow_step_id": step.id},
            )
    parse_artifact = _record_parse_artifact(
        db,
        workflow_step_id=step.id,
        artifact_type="section_candidates",
        source_url=homepage_url,
        payload={
            "scope_type": scope_type,
            "scope_key": scope_key,
            "candidate_count": result["candidate_count"],
            "candidate_urls": list(result.get("candidate_urls") or []),
            "families": sorted(families),
            "sections": [
                {
                    "id": section.id,
                    "name": section.name,
                    "section_type": section.section_type,
                    "section_url": section.section_url,
                    "school_id": section.school_id,
                    "department_id": section.department_id,
                    "enabled": section.enabled,
                }
                for section in sections
            ],
        },
    )
    section_node_ids: list[str] = []
    for section in sections:
        section_node = _ensure_portal_node(
            db,
            school_id=school.id,
            department_id=department.id if department else None,
            scope_type=scope_type,
            scope_key=scope_key,
            node_type="section_candidate",
            url=section.section_url,
            title=section.name,
            status="approved" if int(section.enabled or 0) == 1 else "recommended",
            evidence={
                "site_section_id": section.id,
                "section_type": section.section_type,
                "discovery_category": section.discovery_category,
                "parse_artifact_id": parse_artifact.id,
            },
        )
        section_node_ids.append(section_node.id)
        parent_node = next(
            (
                node
                for node in seed_nodes
                if _host_from_url(node.url) and _host_from_url(node.url) == _host_from_url(section.section_url)
            ),
            homepage_node,
        )
        if parent_node.id != section_node.id:
            _ensure_portal_edge(
                db,
                from_node_id=parent_node.id,
                to_node_id=section_node.id,
                relation_type="section_candidate",
                evidence={"site_section_id": section.id, "workflow_step_id": step.id},
            )
    candidate_hosts = list(
        dict.fromkeys(
            host
            for host in [
                _host_from_url(homepage_url),
                *[_host_from_url(url) for url in seed_urls],
                *[_host_from_url(section.section_url) for section in sections],
            ]
            if host
        )
    )
    host_decision = _upsert_host_decision(
        db,
        school_id=school.id,
        department_id=department.id if department else None,
        scope_type=scope_type,
        scope_key=scope_key,
        family=family_key,
        selected_host=next(
            (host for host in [_host_from_url(section.section_url) for section in sections] if host),
            candidate_hosts[0] if candidate_hosts else None,
        ),
        candidate_hosts=candidate_hosts,
        evidence={
            "homepage_url": homepage_url,
            "seed_urls": seed_urls,
            "recommended_section_ids": [section.id for section in sections],
            "parse_artifact_id": parse_artifact.id,
            "families": sorted(families),
            "seed_source": str(payload.seed_source or "").strip() or None,
        },
    )
    _record_governance_action(
        db,
        entity_type="workflow_run",
        entity_id=step.run_id,
        scope_type=scope_type,
        scope_key=scope_key,
        action_type="bootstrap.completed",
        actor_account_id=actor_account_id,
        payload={
            "recommended_section_ids": [section.id for section in sections],
            "homepage_url": homepage_url,
            "seed_urls": seed_urls,
            "homepage_node_id": homepage_node.id,
            "section_node_ids": section_node_ids,
            "host_decision_id": host_decision.id,
            "raw_artifact_id": raw_artifact.id,
            "parse_artifact_id": parse_artifact.id,
            "families": sorted(families),
            "seed_source": str(payload.seed_source or "").strip() or None,
        },
    )
    return {
        "school_name": school_name,
        "department_name": department_name,
        "recommended_section_ids": [section.id for section in sections],
        "total_candidate_sections": result["candidate_count"],
        "section_node_ids": section_node_ids,
        "host_decision_id": host_decision.id,
        "raw_artifact_id": raw_artifact.id,
        "parse_artifact_id": parse_artifact.id,
        "families": sorted(families),
        "seed_source": str(payload.seed_source or "").strip() or None,
    }


def _process_section_discovery_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = SectionDiscoveryPayload.model_validate(step.input_payload or {})
    section = db.query(SiteSection).filter(SiteSection.id == payload.site_section_id).one_or_none()
    if section is None:
        raise ValueError("site section not found")
    if section.discovery_category != "announcement":
        raise ValueError("section discovery workflow only supports announcement sections")

    from .crawler import discover_site_section_work_item

    return discover_site_section_work_item(
        db,
        section=section,
        source_url=payload.source_url,
        work_item_kind="workflow_step",
        work_item_id=step.id,
        run_id=step.run_id,
    )


def _process_detail_fetch_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = DetailFetchPayload.model_validate(step.input_payload or {})
    site_section_link_id = str(payload.site_section_link_id or "").strip()
    if not site_section_link_id:
        raise ValueError("site_section_link_id is required")

    from ..models import SiteSectionLink
    from .crawler import ingest_url_work_item

    link_row = db.query(SiteSectionLink).filter(SiteSectionLink.id == site_section_link_id).one_or_none()
    if link_row is None:
        raise ValueError("site section link not found")
    if not str(payload.source_url or "").strip():
        raise ValueError("source_url is required")

    content_id, result = ingest_url_work_item(
        db,
        category="announcement",
        query=payload.model_dump(),
        source_url=str(payload.source_url or "").strip(),
        work_item_kind="workflow_step",
        work_item_id=step.id,
        run_id=step.run_id,
    )
    classification = None
    if content_id:
        content = db.query(Content).filter(Content.id == content_id).one_or_none()
        if content is not None and content.category == "announcement":
            classification = sync_content_classification(db, content)
    link_row.status = "parsed"
    link_row.snapshot_meta = {
        **dict(link_row.snapshot_meta or {}),
        "detail_workflow_run_id": step.run_id,
        "detail_workflow_step_id": step.id,
        **({"content_id": content_id} if content_id else {}),
    }
    db.flush()
    return {
        "content_id": content_id,
        "site_section_link_id": link_row.id,
        "status": link_row.status,
        "result": result,
        "classification_state": classification.classification_state if classification is not None else None,
    }


def _process_file_parse_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = FileParsePayload.model_validate(step.input_payload or {})
    content_file_id = str(payload.content_file_id or "").strip()
    if not content_file_id:
        raise ValueError("content_file_id is required")
    file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
    if file_record is None:
        raise ValueError("content file not found")

    from .crawler import ingest_file_work_item

    content_id, result = ingest_file_work_item(
        db,
        category="announcement",
        query=payload.model_dump(),
        file_record=file_record,
        work_item_kind="workflow_step",
        work_item_id=step.id,
        run_id=step.run_id,
    )
    classification = None
    if content_id:
        content = db.query(Content).filter(Content.id == content_id).one_or_none()
        if content is not None and content.category == "announcement":
            classification = sync_content_classification(db, content)
    file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one()
    return {
        "content_id": content_id,
        "content_file_id": file_record.id,
        "parse_status": file_record.parse_status,
        "ocr_status": file_record.ocr_status,
        "result": result,
        "classification_state": classification.classification_state if classification is not None else None,
    }


def _process_ocr_enqueue_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = OcrEnqueuePayload.model_validate(step.input_payload or {})
    content_file_id = str(payload.content_file_id or "").strip()
    file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
    if file_record is None:
        raise ValueError("content file not found")
    file_record.ocr_status = "queued"
    db.flush()
    return {"content_file_id": file_record.id, "ocr_status": file_record.ocr_status}


def _process_reclassify_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = ContentReclassifyPayload.model_validate(step.input_payload or {})
    content_id = str(payload.content_id or "").strip()
    content = db.query(Content).filter(Content.id == content_id).one_or_none()
    if content is None:
        raise ValueError("content not found")
    classification = sync_content_classification(db, content)
    return {
        "content_id": content.id,
        "classification_state": classification.classification_state,
        "scope_type": classification.scope_type,
        "scope_key": classification.scope_key,
    }


def _process_pollution_cleanup_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    _payload = PollutionCleanupPayload.model_validate(step.input_payload or {})
    return {
        "scope_type": step.scope_type,
        "scope_key": step.scope_key,
        "message": "pollution cleanup workflow type is reserved for the next phase",
    }


class WorkflowEngine:
    def process_step_batch(self, *, batch_size: int = 10, worker_name: str = "crawler-v2-worker") -> int:
        with SessionLocal() as db:
            locked_ids = _lock_pending_steps(db, batch_size, worker_name)
        if not locked_ids:
            return 0

        processed = 0
        for step_id in locked_ids:
            with SessionLocal() as db:
                step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one_or_none()
                if step is None:
                    continue
                try:
                    if step.step_type == WORKFLOW_TYPE_SCHOOL_BOOTSTRAP:
                        result = _process_bootstrap_step(db, step, department_mode=False)
                    elif step.step_type == WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP:
                        result = _process_bootstrap_step(db, step, department_mode=True)
                    elif step.step_type in {WORKFLOW_TYPE_SCHOOL_SECTION_DISCOVERY, WORKFLOW_TYPE_DEPARTMENT_SECTION_DISCOVERY}:
                        result = _process_section_discovery_step(db, step)
                    elif step.step_type == WORKFLOW_TYPE_DETAIL_FETCH:
                        result = _process_detail_fetch_step(db, step)
                    elif step.step_type == WORKFLOW_TYPE_SCOPE_REBUILD:
                        result = _process_scope_rebuild_step(db, step)
                    elif step.step_type == STEP_TYPE_FETCH_CHSI_SCHOOL_CATALOG:
                        result = _process_fetch_chsi_school_catalog_step(db, step)
                    elif step.step_type == STEP_TYPE_ENQUEUE_CHSI_SCHOOL_ENRICH:
                        result = _process_enqueue_chsi_school_enrich_step(db, step)
                    elif step.step_type == STEP_TYPE_ENRICH_CHSI_SCHOOL_SNAPSHOT:
                        result = _process_enrich_chsi_school_snapshot_step(db, step)
                    elif step.step_type == STEP_TYPE_AWAIT_CHSI_SCHOOL_ENRICH:
                        result = _process_await_chsi_school_enrich_step(db, step)
                    elif step.step_type == STEP_TYPE_FETCH_CHSI_MAJOR_CATALOG:
                        result = _process_fetch_chsi_major_catalog_step(db, step)
                    elif step.step_type == STEP_TYPE_FETCH_OFFICIAL_SEED_ROSTERS:
                        result = _process_fetch_official_seed_rosters_step(db, step)
                    elif step.step_type == STEP_TYPE_FETCH_SCHOOL_HOMEPAGES:
                        result = _process_fetch_school_homepages_step(db, step)
                    elif step.step_type == STEP_TYPE_BUILD_DEPARTMENT_CANDIDATES:
                        result = _process_build_department_candidates_step(db, step)
                    elif step.step_type == STEP_TYPE_MERGE_ANNOUNCEMENT_SEED_REGISTRY:
                        result = _process_merge_announcement_seed_registry_step(db, step)
                    elif step.step_type == WORKFLOW_TYPE_FILE_PARSE:
                        result = _process_file_parse_step(db, step)
                    elif step.step_type == STEP_TYPE_OCR_ENQUEUE:
                        result = _process_ocr_enqueue_step(db, step)
                    elif step.step_type == STEP_TYPE_CONTENT_RECLASSIFY:
                        result = _process_reclassify_step(db, step)
                    elif step.step_type == WORKFLOW_TYPE_POLLUTION_CLEANUP:
                        result = _process_pollution_cleanup_step(db, step)
                    else:
                        raise ValueError(f"unsupported workflow step type: {step.step_type}")
                    _mark_step_done(db, step, result)
                    processed += 1
                except DeferredStep as exc:
                    db.rollback()
                    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one_or_none()
                    if step is None:
                        processed += 1
                        continue
                    _mark_step_deferred(
                        db,
                        step,
                        result_payload=exc.result_payload,
                        delay_seconds=exc.delay_seconds,
                    )
                    processed += 1
                except TerminalStepFailure as exc:
                    db.rollback()
                    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one_or_none()
                    if step is None:
                        processed += 1
                        continue
                    _mark_step_failed(db, step, exc, result_payload=exc.result_payload)
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    step = db.query(WorkflowStep).filter(WorkflowStep.id == step_id).one_or_none()
                    if step is None:
                        processed += 1
                        continue
                    _mark_step_failed(db, step, exc)
                    processed += 1
        return processed


workflow_engine = WorkflowEngine()
