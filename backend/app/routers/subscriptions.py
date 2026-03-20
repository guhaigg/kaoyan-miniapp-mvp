from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_portal_user_optional, has_premium_monitoring_access
from ..models import PortalUserSubscription
from ..schemas import SubscriptionCreateRequest, SubscriptionItem, SubscriptionListResponse
from ..services.historical_intelligence import (
    normalize_department_name,
    normalize_major_code,
    normalize_major_name,
    normalize_school_name,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _require_portal_user(request: Request, db: Session):
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return user


def _build_radar_snapshot(payload: SubscriptionCreateRequest) -> dict[str, str | None]:
    school_name = str(payload.target_university or "").strip()
    major_code = normalize_major_code(payload.target_major_code)
    major_name = normalize_major_name(payload.target_major_name)
    department_name = str(payload.target_department_name or "").strip() or None
    department_name_normalized = normalize_department_name(department_name)

    if not school_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_university is required for radar subscription")
    if not major_code and not major_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_major_code or target_major_name is required for radar subscription",
        )

    school_name_normalized = normalize_school_name(school_name)
    value = f"radar::{school_name_normalized}::{major_code or major_name}"
    label_parts = [school_name]
    if department_name:
        label_parts.append(department_name)
    if payload.target_major_name:
        label_parts.append(str(payload.target_major_name).strip())
    if major_code:
        label_parts.append(major_code)
    display_label = " · ".join(part for part in label_parts if part)

    return {
        "value": value,
        "display_label": display_label,
        "source_record_id": str(payload.source_record_id or "").strip() or None,
        "source_item_kind": payload.source_item_kind,
        "source_title": str(payload.source_title or "").strip() or None,
        "source_url": str(payload.source_url or "").strip() or None,
        "target_school_name": school_name,
        "target_school_name_normalized": school_name_normalized,
        "target_department_name": department_name,
        "target_department_name_normalized": department_name_normalized,
        "target_major_code": major_code,
        "target_major_name": str(payload.target_major_name or "").strip() or None,
        "target_major_name_normalized": major_name,
    }


@router.post("", response_model=SubscriptionItem)
def create_subscription(payload: SubscriptionCreateRequest, request: Request, db: Session = Depends(get_db)) -> SubscriptionItem:
    user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"subscription_create:{user.id}")
    if payload.subscription_type == "school" and not has_premium_monitoring_access(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="school subscription requires premium or admin role",
        )

    snapshot: dict[str, str | None] = {}
    if payload.subscription_type == "radar":
        snapshot = _build_radar_snapshot(payload)
        value = str(snapshot["value"] or "").strip()
        snapshot.pop("value", None)
    else:
        value = str(payload.value or "").strip()
        if not value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value cannot be empty")

    existing = (
        db.query(PortalUserSubscription)
        .filter(
            PortalUserSubscription.user_id == user.id,
            PortalUserSubscription.subscription_type == payload.subscription_type,
            PortalUserSubscription.value == value,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.status != "active":
            existing.status = "active"
        existing.category = payload.category
        for field, field_value in snapshot.items():
            setattr(existing, field, field_value)
        db.commit()
        db.refresh(existing)
        return _to_subscription_item(existing)

    item = PortalUserSubscription(
        user_id=user.id,
        subscription_type=payload.subscription_type,
        value=value,
        category=payload.category,
        status="active",
        **snapshot,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    audit_event(
        db,
        request,
        "subscription.create",
        None,
        {
            "subscription_id": item.id,
            "type": item.subscription_type,
            "value": item.value,
            "display_label": item.display_label,
            "portal_user_id": user.id,
        },
    )
    return _to_subscription_item(item)


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(request: Request, db: Session = Depends(get_db)) -> SubscriptionListResponse:
    user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"subscription_list:{user.id}")
    rows = (
        db.query(PortalUserSubscription)
        .filter(PortalUserSubscription.user_id == user.id, PortalUserSubscription.status == "active")
        .order_by(PortalUserSubscription.created_at.desc())
        .all()
    )
    return SubscriptionListResponse(total=len(rows), items=[_to_subscription_item(x) for x in rows])


@router.delete("/{subscription_id}")
def delete_subscription(subscription_id: str, request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"subscription_delete:{user.id}")

    item = (
        db.query(PortalUserSubscription)
        .filter(
            PortalUserSubscription.id == subscription_id,
            PortalUserSubscription.user_id == user.id,
        )
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subscription not found")

    item.status = "deleted"
    db.commit()
    audit_event(
        db,
        request,
        "subscription.delete",
        None,
        {"subscription_id": subscription_id, "portal_user_id": user.id},
    )
    return {"status": "ok"}


def _to_subscription_item(item: PortalUserSubscription) -> SubscriptionItem:
    return SubscriptionItem(
        id=item.id,
        subscription_type=item.subscription_type,
        value=item.value,
        display_label=item.display_label,
        category=item.category,
        status=item.status,
        source_record_id=item.source_record_id,
        source_item_kind=item.source_item_kind,
        source_title=item.source_title,
        source_url=item.source_url,
        target_university=item.target_school_name,
        target_department_name=item.target_department_name,
        target_major_code=item.target_major_code,
        target_major_name=item.target_major_name,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
