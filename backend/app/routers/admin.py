import json
from collections import Counter, defaultdict
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, load_only, selectinload

from ..config import get_settings
from ..db import get_db
from ..dependencies import (
    audit_event,
    get_admin_identity,
    require_admin_request,
)
from ..models import (
    AccountPaymentOrder,
    Content,
    HistoricalReleaseTimingProfile,
    MentorEvaluation,
    PortalUser,
    PortalUserSubscription,
    RawDatasetArchive,
    School,
    UserEvent,
)
from ..schemas import (
    AdminAuditItem,
    AdminAuditListResponse,
    AdminChangePasswordRequest,
    AdminChangePasswordResponse,
    AdminContentFingerprintStatsResponse,
    AdjustmentIntelligenceBreakdownItem,
    AdjustmentMentorRadarSchoolItem,
    AdjustmentIntelligenceResponse,
    AdjustmentIntelligenceSchoolItem,
    AdjustmentIntelligenceSourceItem,
    AdjustmentTimingSchoolItem,
    AdminEntitlementItem,
    AdminIdentityItem,
    AdminMarkPaymentOrderPaidRequest,
    AdminPaymentOrderItem,
    AdminPaymentOrderListResponse,
    AdminUserDemoteRequest,
    AdminMeResponse,
    AdminRegisterRequest,
    AdminRegisterResponse,
    AdminResetUserPasswordRequest,
    AdminResetUserPasswordResponse,
    AdminRoleAssignmentItem,
    AdminUserItem,
    AdminUserListResponse,
    RawDatasetArchiveItem,
    RawDatasetArchiveListResponse,
    AdminUserPromoteRequest,
    AdminUserUpdateRequest,
    ContentIn,
    ContentOut,
    ManualEntryRequest,
)
from ..security import hash_password, verify_password
from ..services.account_access import (
    ENTITLEMENT_PREMIUM_MONITORING,
    ENTITLEMENT_SOURCE_ADMIN_GRANT,
    ROLE_ADMIN,
    create_payment_order,
    ensure_account_role,
    ensure_password_identity,
    entitlement_expiry_from_days,
    find_password_login_account,
    mark_payment_order_paid,
    resolve_portal_access,
    revoke_premium_entitlements,
    set_password_hash,
    upsert_premium_entitlement,
)
from ..services.content import _build_content_fingerprint, upsert_content

router = APIRouter(prefix="/admin", tags=["admin"])


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _to_admin_user_item(user: PortalUser, is_admin: bool, is_premium: bool, premium_expires_at=None) -> AdminUserItem:
    identities = [
        AdminIdentityItem(
            id=identity.id,
            identity_type=identity.identity_type,
            login_name=identity.login_name,
            status=identity.status,
            provider_subject=identity.provider_subject,
            provider_unionid=identity.provider_unionid,
            verified_at=identity.verified_at,
            last_login_at=identity.last_login_at,
        )
        for identity in sorted(user.identities, key=lambda item: (item.identity_type, item.created_at))
    ]
    roles = [
        AdminRoleAssignmentItem(
            role_code=role.role_code,
            status=role.status,
            source=role.source,
            created_at=role.created_at,
        )
        for role in sorted(user.roles, key=lambda item: (item.role_code, item.created_at))
    ]
    entitlements = [
        AdminEntitlementItem(
            entitlement_code=entitlement.entitlement_code,
            status=entitlement.status,
            source=entitlement.source,
            starts_at=entitlement.starts_at,
            expires_at=entitlement.expires_at,
            revoked_at=entitlement.revoked_at,
            order_ref=entitlement.order_ref,
        )
        for entitlement in sorted(
            user.entitlements,
            key=lambda item: (item.entitlement_code, item.created_at),
        )
    ]
    return AdminUserItem(
        id=user.id,
        username=user.username,
        status=user.status,
        is_admin=is_admin,
        is_premium=is_premium,
        premium_expires_at=premium_expires_at,
        nickname=user.nickname,
        identities=identities,
        roles=roles,
        entitlements=entitlements,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _to_admin_payment_order_item(order: AccountPaymentOrder, username: str) -> AdminPaymentOrderItem:
    return AdminPaymentOrderItem(
        id=order.id,
        account_id=order.account_id,
        username=username,
        entitlement_code=order.entitlement_code,
        source=order.source,
        status=order.status,
        duration_days=order.duration_days,
        amount_cents=order.amount_cents,
        currency=order.currency,
        order_ref=order.order_ref,
        provider_name=order.provider_name,
        provider_order_ref=order.provider_order_ref,
        provider_payment_ref=order.provider_payment_ref,
        paid_at=order.paid_at,
        canceled_at=order.canceled_at,
        created_at=order.created_at,
        meta_json=dict(order.meta_json or {}),
    )


def _to_raw_dataset_archive_item(row: RawDatasetArchive) -> RawDatasetArchiveItem:
    return RawDatasetArchiveItem(
        id=row.id,
        dataset_key=row.dataset_key,
        title=row.title,
        dataset_type=row.dataset_type,
        source_filename=row.source_filename,
        source_path=row.source_path,
        workbook_format=row.workbook_format,
        file_sha256=row.file_sha256,
        file_size_bytes=row.file_size_bytes,
        sheet_names=list(row.sheet_names or []),
        primary_sheet_name=row.primary_sheet_name,
        total_rows=row.total_rows,
        total_columns=row.total_columns,
        header_row=list(row.header_row or []),
        preview_rows=list(row.preview_rows or []),
        summary_json=dict(row.summary_json or {}),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _mark_school_subscriptions_deleted(db: Session, user_id: str) -> int:
    rows = (
        db.query(PortalUserSubscription)
        .filter(
            PortalUserSubscription.user_id == user_id,
            PortalUserSubscription.subscription_type == "school",
            PortalUserSubscription.status == "active",
        )
        .all()
    )
    for row in rows:
        row.status = "deleted"
    return len(rows)


def _sync_user_identity_statuses(user: PortalUser) -> None:
    next_status = "active" if user.status == "active" else "inactive"
    for identity in user.identities:
        if identity.identity_type == "password":
            identity.status = next_status


def _apply_role_for_user(
    db: Session,
    *,
    user: PortalUser,
    target_role: str,
    operator: str,
    premium_days: int | None,
) -> dict:
    affected_school_subscriptions = 0
    operator_user = db.query(PortalUser).filter(PortalUser.username == operator).one_or_none()
    operator_account_id = operator_user.id if operator_user is not None else None

    if target_role == "admin":
        revoke_premium_entitlements(db, user_id=user.id)
        ensure_account_role(
            db,
            user_id=user.id,
            role_code=ROLE_ADMIN,
            operator_account_id=operator_account_id,
            source="manual",
            active=True,
        )
    elif target_role == "premium":
        expires_at = entitlement_expiry_from_days(premium_days)
        upsert_premium_entitlement(
            db,
            user_id=user.id,
            operator_account_id=operator_account_id,
            expires_at=expires_at,
            source=ENTITLEMENT_SOURCE_ADMIN_GRANT,
        )
        ensure_account_role(
            db,
            user_id=user.id,
            role_code=ROLE_ADMIN,
            operator_account_id=operator_account_id,
            source="manual",
            active=False,
        )
    else:
        revoke_premium_entitlements(db, user_id=user.id)
        ensure_account_role(
            db,
            user_id=user.id,
            role_code=ROLE_ADMIN,
            operator_account_id=operator_account_id,
            source="manual",
            active=False,
        )
        affected_school_subscriptions = _mark_school_subscriptions_deleted(db, user.id)

    db.flush()
    access_state = resolve_portal_access(db, user)
    return {
        "is_admin": access_state.is_admin,
        "is_premium": access_state.is_premium,
        "premium_expires_at": access_state.premium_expires_at,
        "affected_school_subscriptions": affected_school_subscriptions,
    }


def _get_portal_admin_user(db: Session, username: str) -> PortalUser | None:
    user, _identity = find_password_login_account(db, username)
    if user is None:
        return None
    access_state = resolve_portal_access(db, user)
    if not access_state.is_admin:
        return None
    return user


def _content_fingerprint_stats(db: Session) -> AdminContentFingerprintStatsResponse:
    total_contents = int(db.query(func.count(Content.id)).scalar() or 0)
    fingerprinted_contents = int(
        db.query(func.count(Content.id))
        .filter(Content.content_fingerprint.is_not(None), Content.content_fingerprint != "")
        .scalar()
        or 0
    )

    pending_rows = (
        db.query(
            Content.id,
            Content.category,
            Content.title,
            Content.body,
            Content.summary,
            Content.source_url,
            Content.source_type,
            Content.published_at,
            Content.region,
            Content.major,
            Content.extra,
            School.name.label("school_name"),
        )
        .outerjoin(School, School.id == Content.school_id)
        .filter(or_(Content.content_fingerprint.is_(None), Content.content_fingerprint == ""))
        .all()
    )

    fingerprint_counter: Counter[str] = Counter()
    pending_fingerprints_by_id: dict[str, str] = {}
    existing_fingerprints = {
        row[0]
        for row in db.query(Content.content_fingerprint)
        .filter(Content.content_fingerprint.is_not(None), Content.content_fingerprint != "")
        .all()
        if row[0]
    }

    for row in pending_rows:
        fingerprint = _build_content_fingerprint(
            ContentIn(
                category=row.category,
                title=row.title,
                body=row.body,
                summary=row.summary,
                school_name=row.school_name,
                source_url=row.source_url,
                source_type=row.source_type,
                published_at=row.published_at,
                region=row.region,
                major=row.major,
                extra=dict(row.extra or {}),
                raw_html=None,
            ),
            row.school_name,
        )
        pending_fingerprints_by_id[row.id] = fingerprint
        fingerprint_counter[fingerprint] += 1

    collision_contents = 0
    for row_id, fingerprint in pending_fingerprints_by_id.items():
        if fingerprint in existing_fingerprints or fingerprint_counter[fingerprint] > 1:
            collision_contents += 1

    pending_contents = len(pending_rows)
    coverage_ratio = 0.0 if total_contents == 0 else round(fingerprinted_contents / total_contents, 4)
    return AdminContentFingerprintStatsResponse(
        total_contents=total_contents,
        fingerprinted_contents=fingerprinted_contents,
        pending_contents=pending_contents,
        collision_contents=collision_contents,
        coverage_ratio=coverage_ratio,
    )


def _adjustment_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data"


def _load_adjustment_summary(name: str) -> dict:
    return json.loads((_adjustment_data_dir() / name).read_text(encoding="utf-8"))


def _to_breakdown_items(counter: Counter[str], limit: int = 8) -> list[AdjustmentIntelligenceBreakdownItem]:
    return [AdjustmentIntelligenceBreakdownItem(label=label, count=count) for label, count in counter.most_common(limit)]


def _adjustment_intelligence(db: Session) -> AdjustmentIntelligenceResponse:
    summary_rows = [
        ("adjustment_stats_2023_2025", "23-25 调剂统计", _load_adjustment_summary("adjustment_stats_2023_2025_summary.json"), 208),
        ("adjustment_opportunity_2024", "2024 调剂机会", _load_adjustment_summary("adjustment_opportunity_2024_summary.json"), None),
        ("adjustment_snapshot_2025_0409", "2025 调剂快照", _load_adjustment_summary("adjustment_opportunity_2025_snapshot_summary.json"), None),
        ("adjustment_landing_2025", "2025 调剂上岸画像", _load_adjustment_summary("adjustment_landing_2025_summary.json"), None),
        ("adjustment_snapshot_2024_0414", "2024-04-14 调剂快照", _load_adjustment_summary("adjustment_snapshot_2024_0414_summary.json"), None),
        ("program_catalog_2026", "2026 招生专业目录", _load_adjustment_summary("admission_program_catalog_2026_summary.json"), None),
        ("adjustment_stats_2025_full", "2025 调剂统计完整版", _load_adjustment_summary("adjustment_stats_2025_full_summary.json"), 127),
        ("adjustment_announcement_2025", "2025 调剂公告", _load_adjustment_summary("adjustment_announcement_2025_summary.json"), None),
        ("adjustment_landing_2024", "2024 调剂上岸画像", _load_adjustment_summary("adjustment_landing_2024_summary.json"), None),
    ]

    school_scores: defaultdict[str, dict] = defaultdict(lambda: {"score": 0, "source_hits": 0, "sources": set(), "categories": set()})
    study_mode_counts: Counter[str] = Counter()
    province_counts: Counter[str] = Counter()
    verification_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    score_band_counts: Counter[str] = Counter()
    mentor_risk_counts: Counter[str] = Counter()
    mentor_tag_counts: Counter[str] = Counter()
    timing_hour_counts: Counter[str] = Counter()
    source_cards: list[AdjustmentIntelligenceSourceItem] = []

    for source_key, title, summary, target_rows in summary_rows:
        source_cards.append(
            AdjustmentIntelligenceSourceItem(
                source_key=source_key,
                title=title,
                total_rows=int(summary.get("total_rows") or 0),
                unique_schools=int(summary["unique_schools"]) if summary.get("unique_schools") is not None else None,
                target_rows=target_rows,
            )
        )

        for label, count in (summary.get("study_mode_counts") or {}).items():
            study_mode_counts[str(label)] += int(count)
        for label, count in (summary.get("province_counts") or {}).items():
            province_counts[str(label)] += int(count)
        for label, count in (summary.get("region_counts") or {}).items():
            province_counts[str(label)] += int(count)
        for label, count in (summary.get("validation_state_counts") or {}).items():
            verification_counts[str(label)] += int(count)
        for label, count in (summary.get("verification_counts") or {}).items():
            verification_counts[str(label)] += int(count)
        for label, count in (summary.get("category_counts") or {}).items():
            category_counts[str(label)] += int(count)
        for label, count in (summary.get("score_bucket_counts") or {}).items():
            score_band_counts[str(label)] += int(count)

        for row in summary.get("top_schools") or []:
            school_name = str(row.get("school_name") or "").strip()
            if not school_name:
                continue
            rank = int(row.get("rank") or 26)
            score = max(1, 26 - rank)
            item = school_scores[school_name]
            if source_key not in item["sources"]:
                item["sources"].add(source_key)
                item["source_hits"] += 1
            item["score"] += score
            category = str(row.get("school_category") or "").strip()
            if category:
                item["categories"].add(category)

    school_leaderboard = [
        AdjustmentIntelligenceSchoolItem(
            school_name=school_name,
            source_hits=int(payload["source_hits"]),
            score=int(payload["score"]),
            sources=sorted(payload["sources"]),
            categories=sorted(payload["categories"]),
        )
        for school_name, payload in sorted(
            school_scores.items(),
            key=lambda item: (-int(item[1]["source_hits"]), -int(item[1]["score"]), item[0]),
        )[:12]
    ]

    raw_dataset_total, raw_dataset_total_bytes = (
        db.query(func.count(RawDatasetArchive.id), func.coalesce(func.sum(RawDatasetArchive.file_size_bytes), 0)).one()
    )
    mentor_rows = db.query(MentorEvaluation).all()
    mentor_school_scores: defaultdict[str, dict] = defaultdict(
        lambda: {"review_count": 0, "warning_count": 0, "mentor_names": set(), "tag_counts": Counter()}
    )
    for row in mentor_rows:
        school_name = str(row.school_name or "").strip()
        if not school_name:
            continue
        bucket = mentor_school_scores[school_name]
        bucket["review_count"] += 1
        if row.mentor_name:
            bucket["mentor_names"].add(row.mentor_name_normalized or row.mentor_name)
        level = str(row.risk_level or "neutral").strip() or "neutral"
        mentor_risk_counts[level] += 1
        if level == "warning":
            bucket["warning_count"] += 1
        for tag in row.review_tags or []:
            clean_tag = str(tag or "").strip()
            if clean_tag:
                mentor_tag_counts[clean_tag] += 1
                bucket["tag_counts"][clean_tag] += 1

    mentor_school_leaderboard = [
        AdjustmentMentorRadarSchoolItem(
            school_name=school_name,
            review_count=int(payload["review_count"]),
            warning_count=int(payload["warning_count"]),
            mentor_count=len(payload["mentor_names"]),
            top_tags=[label for label, _count in payload["tag_counts"].most_common(3)],
        )
        for school_name, payload in sorted(
            mentor_school_scores.items(),
            key=lambda item: (-int(item[1]["warning_count"]), -int(item[1]["review_count"]), item[0]),
        )[:10]
    ]

    timing_rows = db.query(HistoricalReleaseTimingProfile).all()
    for row in timing_rows:
        if row.peak_hour_bucket:
            timing_hour_counts[row.peak_hour_bucket] += int(row.sample_count or 0)
    timing_school_leaderboard = [
        AdjustmentTimingSchoolItem(
            school_name=row.school_name,
            sample_count=int(row.sample_count),
            peak_hour=row.peak_hour,
            peak_hour_bucket=row.peak_hour_bucket,
            window_start_md=row.window_start_md,
            window_end_md=row.window_end_md,
        )
        for row in sorted(
            timing_rows,
            key=lambda item: (-int(item.sample_count or 0), item.school_name),
        )[:10]
    ]

    return AdjustmentIntelligenceResponse(
        raw_dataset_total=int(raw_dataset_total or 0),
        raw_dataset_total_bytes=int(raw_dataset_total_bytes or 0),
        source_cards=source_cards,
        school_leaderboard=school_leaderboard,
        mentor_school_leaderboard=mentor_school_leaderboard,
        timing_school_leaderboard=timing_school_leaderboard,
        study_mode_breakdown=_to_breakdown_items(study_mode_counts),
        province_breakdown=_to_breakdown_items(province_counts),
        verification_breakdown=_to_breakdown_items(verification_counts),
        category_breakdown=_to_breakdown_items(category_counts),
        score_band_breakdown=_to_breakdown_items(score_band_counts),
        mentor_risk_breakdown=_to_breakdown_items(mentor_risk_counts),
        mentor_tag_breakdown=_to_breakdown_items(mentor_tag_counts),
        timing_hour_breakdown=_to_breakdown_items(timing_hour_counts),
    )


@router.get("/auth/me", response_model=AdminMeResponse)
def admin_me(request: Request) -> AdminMeResponse:
    require_admin_request(request)
    return AdminMeResponse(username=get_admin_identity(request) or "admin", authenticated=True)


@router.get("/content-fingerprint-stats", response_model=AdminContentFingerprintStatsResponse)
def admin_content_fingerprint_stats(request: Request, db: Session = Depends(get_db)) -> AdminContentFingerprintStatsResponse:
    require_admin_request(request)
    return _content_fingerprint_stats(db)


@router.get("/adjustment-intelligence", response_model=AdjustmentIntelligenceResponse)
def admin_adjustment_intelligence(request: Request, db: Session = Depends(get_db)) -> AdjustmentIntelligenceResponse:
    require_admin_request(request)
    return _adjustment_intelligence(db)


@router.get("/raw-datasets", response_model=RawDatasetArchiveListResponse)
def list_raw_datasets(request: Request, db: Session = Depends(get_db)) -> RawDatasetArchiveListResponse:
    require_admin_request(request)
    rows = (
        db.query(RawDatasetArchive)
        .options(
            load_only(
                RawDatasetArchive.id,
                RawDatasetArchive.dataset_key,
                RawDatasetArchive.title,
                RawDatasetArchive.dataset_type,
                RawDatasetArchive.source_filename,
                RawDatasetArchive.source_path,
                RawDatasetArchive.workbook_format,
                RawDatasetArchive.file_sha256,
                RawDatasetArchive.file_size_bytes,
                RawDatasetArchive.storage_encoding,
                RawDatasetArchive.sheet_names,
                RawDatasetArchive.primary_sheet_name,
                RawDatasetArchive.total_rows,
                RawDatasetArchive.total_columns,
                RawDatasetArchive.header_row,
                RawDatasetArchive.preview_rows,
                RawDatasetArchive.notes,
                RawDatasetArchive.created_at,
                RawDatasetArchive.updated_at,
            )
        )
        .order_by(RawDatasetArchive.created_at.desc())
        .all()
    )
    return RawDatasetArchiveListResponse(total=len(rows), items=[_to_raw_dataset_archive_item(row) for row in rows])


@router.post("/auth/register", response_model=AdminRegisterResponse)
def admin_register(
    payload: AdminRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminRegisterResponse:
    require_admin_request(request)
    username = _normalize_username(payload.username)
    existing = db.query(PortalUser).filter(PortalUser.username == username).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="admin username already exists")

    operator = get_admin_identity(request) or get_settings().admin_username
    user = PortalUser(
        username=username,
        password_hash=hash_password(payload.password),
        status="active",
    )
    db.add(user)
    db.flush()
    ensure_password_identity(db, user)
    ensure_account_role(
        db,
        user_id=user.id,
        role_code=ROLE_ADMIN,
        operator_account_id=None,
        source="bootstrap",
        active=True,
    )
    db.commit()
    db.refresh(user)
    audit_event(db, request, "admin.register", None, {"user_id": user.id, "operator": operator})
    return AdminRegisterResponse(user_id=user.id, username=user.username, promoted=True, bootstrap=False)


@router.post("/auth/change-password", response_model=AdminChangePasswordResponse)
def admin_change_password(
    payload: AdminChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminChangePasswordResponse:
    require_admin_request(request)
    username = get_admin_identity(request) or get_settings().admin_username
    user = _get_portal_admin_user(db, username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current admin account must be a portal admin user")

    ensure_password_identity(db, user)
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="old password incorrect")

    set_password_hash(db, user, hash_password(payload.new_password))
    db.commit()
    audit_event(db, request, "admin.password_change", None, {"operator": username})
    return AdminChangePasswordResponse(status="ok")


@router.post("/users/{user_id}/reset-password", response_model=AdminResetUserPasswordResponse)
def reset_user_password(
    user_id: str,
    payload: AdminResetUserPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminResetUserPasswordResponse:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot reset password for blocked user")

    ensure_password_identity(db, user)
    set_password_hash(db, user, hash_password(payload.new_password))
    _sync_user_identity_statuses(user)
    db.commit()
    audit_event(
        db,
        request,
        "admin.user_password_reset",
        None,
        {"user_id": user.id, "operator": get_admin_identity(request) or get_settings().admin_username},
    )
    return AdminResetUserPasswordResponse(status="ok", user_id=user.id, username=user.username)


@router.get("/payment-orders", response_model=AdminPaymentOrderListResponse)
def list_payment_orders(
    request: Request,
    db: Session = Depends(get_db),
    status_value: str | None = Query(default=None, alias="status"),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminPaymentOrderListResponse:
    require_admin_request(request)
    query = db.query(AccountPaymentOrder, PortalUser.username).join(PortalUser, PortalUser.id == AccountPaymentOrder.account_id)
    if status_value:
        query = query.filter(AccountPaymentOrder.status == status_value.strip())
    if user_id:
        query = query.filter(AccountPaymentOrder.account_id == user_id)
    rows = query.order_by(AccountPaymentOrder.created_at.desc()).limit(limit).all()
    return AdminPaymentOrderListResponse(
        total=len(rows),
        items=[_to_admin_payment_order_item(order, username) for order, username in rows],
    )


@router.post("/payment-orders/{order_id}/mark-paid", response_model=AdminPaymentOrderItem)
def admin_mark_payment_order_paid(
    order_id: str,
    payload: AdminMarkPaymentOrderPaidRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminPaymentOrderItem:
    require_admin_request(request)
    order = db.query(AccountPaymentOrder).filter(AccountPaymentOrder.id == order_id).one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment order not found")
    operator_username = get_admin_identity(request) or get_settings().admin_username
    operator_user = db.query(PortalUser).filter(PortalUser.username == operator_username).one_or_none()
    operator_account_id = operator_user.id if operator_user is not None else None
    try:
        mark_payment_order_paid(
            db,
            order=order,
            operator_account_id=operator_account_id,
            provider_payment_ref=payload.provider_payment_ref,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(order)
    audit_event(
        db,
        request,
        "admin.payment_order_mark_paid",
        None,
        {"order_id": order.id, "account_id": order.account_id, "operator": operator_username},
    )
    username = db.query(PortalUser.username).filter(PortalUser.id == order.account_id).scalar() or "unknown"
    return _to_admin_payment_order_item(order, username)


@router.post("/users/{user_id}/payment-orders", response_model=AdminPaymentOrderItem)
def create_user_payment_order(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    duration_days: int = Query(default=30, ge=1, le=3650),
    amount_cents: int = Query(default=0, ge=0),
) -> AdminPaymentOrderItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    order = create_payment_order(
        db,
        user_id=user.id,
        entitlement_code=ENTITLEMENT_PREMIUM_MONITORING,
        source=ENTITLEMENT_SOURCE_ADMIN_GRANT,
        duration_days=duration_days,
        amount_cents=amount_cents,
        currency="CNY",
        provider_name="manual_admin",
        meta_json={"issued_by_admin": True},
    )
    db.commit()
    audit_event(
        db,
        request,
        "admin.payment_order_create",
        None,
        {"order_id": order.id, "account_id": user.id, "duration_days": duration_days, "amount_cents": amount_cents},
    )
    return _to_admin_payment_order_item(order, user.username)


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    state: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=120),
) -> AdminUserListResponse:
    require_admin_request(request)

    query = db.query(PortalUser).options(
        selectinload(PortalUser.identities),
        selectinload(PortalUser.roles),
        selectinload(PortalUser.entitlements),
    )
    if state:
        query = query.filter(PortalUser.status == state.strip())
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(or_(PortalUser.username.ilike(kw), PortalUser.nickname.ilike(kw)))

    total = query.count()
    rows = query.order_by(PortalUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    changed = False
    for row in rows:
        access_state = resolve_portal_access(db, row)
        if access_state.expired_premium and not access_state.is_admin and not access_state.is_premium:
            _mark_school_subscriptions_deleted(db, row.id)
            changed = True
    if changed:
        db.commit()
    return AdminUserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            _to_admin_user_item(x, state.is_admin, state.is_premium, state.premium_expires_at)
            for x in rows
            for state in [resolve_portal_access(db, x)]
        ],
    )


@router.patch("/users/{user_id}", response_model=AdminUserItem)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminUserItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    if payload.status is not None:
        user.status = payload.status
    if payload.nickname is not None:
        nickname = payload.nickname.strip()
        user.nickname = nickname or None
    ensure_password_identity(db, user)
    _sync_user_identity_statuses(user)

    db.commit()
    db.refresh(user)
    audit_event(db, request, "admin.user_update", None, {"user_id": user.id})
    access_state = resolve_portal_access(db, user)
    return _to_admin_user_item(user, access_state.is_admin, access_state.is_premium, access_state.premium_expires_at)


@router.post("/users/{user_id}/promote", response_model=AdminUserItem)
def promote_user(
    user_id: str,
    request: Request,
    payload: AdminUserPromoteRequest | None = None,
    db: Session = Depends(get_db),
) -> AdminUserItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot promote blocked user")

    target_role = payload.target_role if payload is not None else "admin"
    operator = get_admin_identity(request) or get_settings().admin_username
    role_state = _apply_role_for_user(
        db,
        user=user,
        target_role=target_role,
        operator=operator,
        premium_days=(payload.premium_days if payload is not None else None),
    )

    db.commit()
    db.refresh(user)
    audit_event(
        db,
        request,
        "admin.user_promote",
        None,
        {
            "user_id": user.id,
            "operator": operator,
            "target_role": target_role,
            "is_admin": role_state["is_admin"],
            "is_premium": role_state["is_premium"],
            "premium_expires_at": role_state["premium_expires_at"].isoformat() if role_state["premium_expires_at"] else None,
        },
    )
    return _to_admin_user_item(
        user,
        bool(role_state["is_admin"]),
        bool(role_state["is_premium"]),
        role_state["premium_expires_at"],
    )


@router.post("/users/{user_id}/demote", response_model=AdminUserItem)
def demote_user(
    user_id: str,
    payload: AdminUserDemoteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminUserItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    operator = get_admin_identity(request) or get_settings().admin_username
    role_state = _apply_role_for_user(
        db,
        user=user,
        target_role=payload.target_role,
        operator=operator,
        premium_days=payload.premium_days,
    )
    db.commit()
    db.refresh(user)
    audit_event(
        db,
        request,
        "admin.user_demote",
        None,
        {
            "user_id": user.id,
            "operator": operator,
            "target_role": payload.target_role,
            "is_admin": role_state["is_admin"],
            "is_premium": role_state["is_premium"],
            "premium_expires_at": role_state["premium_expires_at"].isoformat() if role_state["premium_expires_at"] else None,
            "affected_school_subscriptions": role_state["affected_school_subscriptions"],
        },
    )
    return _to_admin_user_item(
        user,
        bool(role_state["is_admin"]),
        bool(role_state["is_premium"]),
        role_state["premium_expires_at"],
    )


@router.get("/audits", response_model=AdminAuditListResponse)
def list_admin_audits(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    prefix: str = Query(default="admin.", max_length=64),
) -> AdminAuditListResponse:
    require_admin_request(request)
    query = db.query(UserEvent).filter(UserEvent.event_type.ilike(f"{prefix}%"))
    total = query.count()
    rows = query.order_by(UserEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AdminAuditListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            AdminAuditItem(
                id=x.id,
                event_type=x.event_type,
                endpoint=x.endpoint,
                event_data=x.event_data,
                ip=x.ip,
                created_at=x.created_at,
            )
            for x in rows
        ],
    )


@router.post("/manual-entry", response_model=ContentOut)
def manual_entry(payload: ManualEntryRequest, request: Request, db: Session = Depends(get_db)) -> ContentOut:
    require_admin_request(request)

    if payload.action == "offline":
        if not payload.content_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_id is required when action=offline")
        content = db.query(Content).filter(Content.id == payload.content_id).one_or_none()
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
        next_extra = dict(content.extra or {})
        next_extra["offline"] = True
        next_extra["offline_reason"] = payload.reason or "manual offline"
        content.extra = next_extra
        db.commit()
        audit_event(db, request, "admin.offline", None, {"content_id": content.id})
        return ContentOut(id=content.id, status="updated")

    if payload.content is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required when action=upsert")
    content_data = payload.content.model_copy(update={"source_type": "manual"})
    content, result = upsert_content(db, content_data)
    audit_event(db, request, "admin.manual_upsert", None, {"content_id": content.id, "status": result})
    return ContentOut(id=content.id, status=result)
