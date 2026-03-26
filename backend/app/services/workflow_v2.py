from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

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
    utcnow,
)
from .classification import sync_content_classification
from .site_section_bootstrap import bootstrap_site_sections

WORKFLOW_TYPE_SCHOOL_BOOTSTRAP = "school_portal_discovery"
WORKFLOW_TYPE_DEPARTMENT_BOOTSTRAP = "department_portal_discovery"
WORKFLOW_TYPE_SCOPE_REBUILD = "scope_rebuild"
STEP_TYPE_OCR_ENQUEUE = "ocr_enqueue"
STEP_TYPE_CONTENT_RECLASSIFY = "content_reclassify"
RULE_VERSION = "crawler_v2_explicit_seed_v1"
DEFAULT_BOOTSTRAP_FAMILIES = frozenset({"admissions", "notice"})
SUPPORTED_BOOTSTRAP_FAMILIES = frozenset({"admissions", "notice", "adjustment"})


def _compact(value: str | None) -> str:
    return "".join(str(value or "").strip().split())


def _host_from_url(url: str | None) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    return urlparse(text).hostname or None


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
            PortalNode.url == url,
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
) -> tuple[WorkflowRun, WorkflowStep]:
    actor_account_id = _resolve_actor_account_id(db, actor_username)
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
        available_at=utcnow(),
        input_payload=input_payload,
        result_payload={},
        idempotency_key=f"{step_type}:{scope_key}:{host_key or 'none'}",
    )
    db.add(step)
    db.flush()
    return run, step


def create_school_bootstrap_run(
    db: Session,
    *,
    school_name: str,
    homepage_url: str,
    seed_urls: list[str],
    actor_username: str | None,
    max_sections: int = 12,
    families: list[str] | set[str] | tuple[str, ...] | None = None,
) -> tuple[WorkflowRun, WorkflowStep]:
    school = db.query(School).filter(School.name == school_name.strip()).one_or_none()
    if school is None:
        school = School(name=school_name.strip(), aliases=[], enabled=1)
        db.add(school)
        db.flush()
    normalized_families = sorted(_normalize_bootstrap_families(families))
    payload = {
        "school_name": school.name,
        "homepage_url": homepage_url.strip(),
        "seed_urls": [str(url).strip() for url in seed_urls if str(url).strip()],
        "max_sections": max_sections,
        "families": normalized_families,
    }
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
    payload = {
        "school_name": school.name,
        "department_name": department.name,
        "department_type": department.department_type,
        "homepage_url": homepage_url.strip(),
        "seed_urls": [str(url).strip() for url in seed_urls if str(url).strip()],
        "max_sections": max_sections,
        "families": normalized_families,
    }
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
) -> tuple[WorkflowRun, WorkflowStep]:
    normalized_families = sorted(_normalize_bootstrap_families(families))
    payload = {
        "scope_type": scope_type,
        "school_name": school_name.strip(),
        "department_name": str(department_name or "").strip() or None,
        "homepage_url": str(homepage_url or "").strip() or None,
        "seed_urls": [str(url).strip() for url in (seed_urls or []) if str(url).strip()],
        "max_sections": max_sections,
        "families": normalized_families,
    }
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
    )


def queue_ocr_retry(db: Session, *, file_record: ContentFile, actor_username: str | None) -> tuple[WorkflowRun, WorkflowStep]:
    link = file_record.site_section_link
    section = link.site_section if link else None
    school_name = section.school.name if section and section.school else ""
    department_name = section.department.name if section and section.department else None
    scope_type = "department" if department_name else "school"
    payload = {
        "content_file_id": file_record.id,
        "file_url": file_record.file_url,
        "school_name": school_name,
        "department_name": department_name,
    }
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
    )
    file_record.ocr_status = "queued"
    db.flush()
    return run, step


def queue_content_reclassify(db: Session, *, content: Content, actor_username: str | None) -> tuple[WorkflowRun, WorkflowStep]:
    extra = dict(content.extra or {})
    school_name = str(getattr(getattr(content, "school", None), "name", None) or extra.get("school_name") or "").strip()
    department_name = str(extra.get("department_name") or "").strip() or None
    scope_type = "department" if department_name else "school"
    payload = {
        "content_id": content.id,
        "school_name": school_name,
        "department_name": department_name,
    }
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
    )


def latest_scope_run(
    db: Session,
    *,
    scope_type: str,
    school_name: str,
    department_name: str | None = None,
) -> WorkflowRun | None:
    return (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.scope_type == scope_type,
            WorkflowRun.scope_key == _scope_key(school_name, department_name),
        )
        .order_by(WorkflowRun.created_at.desc())
        .first()
    )


def _lock_pending_steps(db: Session, batch_size: int, worker_name: str) -> list[str]:
    stale_cutoff = utcnow() - timedelta(minutes=10)
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
        .order_by(WorkflowStep.created_at.asc())
        .limit(batch_size)
    )
    dialect_name = (db.bind.dialect.name if db.bind else "").lower()
    if dialect_name != "sqlite":
        query = query.with_for_update(skip_locked=True)
    rows = query.all()
    if not rows:
        return []
    now = utcnow()
    for row in rows:
        row.status = "running"
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.lease_owner = worker_name
        row.leased_at = now
        row.started_at = row.started_at or now
    db.commit()
    return [row.id for row in rows]


def _mark_step_done(db: Session, step: WorkflowStep, result_payload: dict[str, Any]) -> None:
    step.status = "done"
    step.result_payload = result_payload
    step.finished_at = utcnow()
    step.error_type = None
    step.error_message = None
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    run.status = "done"
    run.result_payload = result_payload
    run.finished_at = utcnow()
    db.commit()


def _mark_step_failed(db: Session, step: WorkflowStep, exc: Exception) -> None:
    step.error_type = type(exc).__name__
    step.error_message = str(exc)
    retryable = not isinstance(exc, ValueError)
    if retryable and step.attempt_count < max(1, int(step.max_attempts or 1)):
        step.status = "pending"
        step.available_at = utcnow() + timedelta(seconds=10)
    else:
        step.status = "failed"
        step.finished_at = utcnow()
    run = db.query(WorkflowRun).filter(WorkflowRun.id == step.run_id).one()
    run.status = "failed" if step.status == "failed" else "pending"
    run.error_message = str(exc)
    db.commit()


def _process_bootstrap_step(db: Session, step: WorkflowStep, *, department_mode: bool) -> dict[str, Any]:
    payload = dict(step.input_payload or {})
    school_name = str(payload.get("school_name") or "").strip()
    department_name = str(payload.get("department_name") or "").strip() or None
    homepage_url = str(payload.get("homepage_url") or "").strip()
    if not school_name or not homepage_url:
        raise ValueError("school_name and homepage_url are required")

    seed_urls = [str(url).strip() for url in (payload.get("seed_urls") or []) if str(url).strip()]
    max_sections = max(1, int(payload.get("max_sections") or 12))
    families = _normalize_bootstrap_families(payload.get("families"))
    family_key = "adjustment" if families == {"adjustment"} else "announcement"
    portal_scope = "graduate_admissions" if families == set(DEFAULT_BOOTSTRAP_FAMILIES) else None
    result = bootstrap_site_sections(
        db,
        school_name=school_name,
        homepage_url=homepage_url,
        department_name=department_name if department_mode else None,
        department_type=str(payload.get("department_type") or "college"),
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
    }


def _process_ocr_enqueue_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = dict(step.input_payload or {})
    content_file_id = str(payload.get("content_file_id") or "").strip()
    file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
    if file_record is None:
        raise ValueError("content file not found")
    file_record.ocr_status = "queued"
    db.flush()
    return {"content_file_id": file_record.id, "ocr_status": file_record.ocr_status}


def _process_reclassify_step(db: Session, step: WorkflowStep) -> dict[str, Any]:
    payload = dict(step.input_payload or {})
    content_id = str(payload.get("content_id") or "").strip()
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
                    elif step.step_type == WORKFLOW_TYPE_SCOPE_REBUILD:
                        result = _process_bootstrap_step(
                            db,
                            step,
                            department_mode=str(step.input_payload.get("scope_type") or "") == "department",
                        )
                    elif step.step_type == STEP_TYPE_OCR_ENQUEUE:
                        result = _process_ocr_enqueue_step(db, step)
                    elif step.step_type == STEP_TYPE_CONTENT_RECLASSIFY:
                        result = _process_reclassify_step(db, step)
                    else:
                        result = {"message": f"noop step_type={step.step_type}"}
                    _mark_step_done(db, step, result)
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
