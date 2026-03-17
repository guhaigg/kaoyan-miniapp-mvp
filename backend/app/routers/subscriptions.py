from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_portal_user_optional
from ..models import PortalUserSubscription
from ..schemas import SubscriptionCreateRequest, SubscriptionItem, SubscriptionListResponse

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _require_portal_user(request: Request, db: Session):
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return user


@router.post("", response_model=SubscriptionItem)
def create_subscription(payload: SubscriptionCreateRequest, request: Request, db: Session = Depends(get_db)) -> SubscriptionItem:
    user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"subscription_create:{user.id}")

    value = payload.value.strip()
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
            db.commit()
            db.refresh(existing)
        return _to_subscription_item(existing)

    item = PortalUserSubscription(
        user_id=user.id,
        subscription_type=payload.subscription_type,
        value=value,
        category=payload.category,
        status="active",
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
        category=item.category,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
