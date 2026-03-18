from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import (
    AccountBindCode,
    AccountEntitlement,
    AccountIdentity,
    AccountPaymentOrder,
    AccountRole,
    PortalUser,
    new_id,
    utcnow,
)

IDENTITY_TYPE_PASSWORD = "password"
IDENTITY_TYPE_WECHAT_MINIAPP = "wechat_miniapp"
ROLE_ADMIN = "admin"
ENTITLEMENT_PREMIUM_MONITORING = "premium_monitoring"
ENTITLEMENT_SOURCE_WEB_PAY = "web_pay"
ENTITLEMENT_SOURCE_WECHAT_PAY = "wechat_pay"
ENTITLEMENT_SOURCE_ADMIN_GRANT = "admin_grant"
ENTITLEMENT_SOURCE_MIGRATION = "migration"
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_PAID = "paid"
ORDER_STATUS_CANCELED = "canceled"
ORDER_STATUS_EXPIRED = "expired"
BIND_TYPE_WECHAT_MINIAPP = "wechat_miniapp"
_BIND_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class PortalAccessState:
    is_admin: bool
    is_premium: bool
    premium_expires_at: datetime | None
    expired_premium: bool


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_login_name(login_name: str) -> str:
    return login_name.strip().lower()


def ensure_password_identity(db: Session, user: PortalUser) -> AccountIdentity:
    identity = (
        db.query(AccountIdentity)
        .filter(
            AccountIdentity.account_id == user.id,
            AccountIdentity.identity_type == IDENTITY_TYPE_PASSWORD,
        )
        .one_or_none()
    )
    login_name = normalize_login_name(user.username)
    if identity is None:
        identity = AccountIdentity(
            account_id=user.id,
            identity_type=IDENTITY_TYPE_PASSWORD,
            login_name=login_name,
            password_hash=user.password_hash,
            status="active",
            verified_at=user.created_at,
            last_login_at=user.last_login_at,
        )
        db.add(identity)
        db.flush()
        return identity

    changed = False
    if identity.login_name != login_name:
        identity.login_name = login_name
        changed = True
    if identity.password_hash != user.password_hash:
        identity.password_hash = user.password_hash
        changed = True
    if identity.status != "active":
        identity.status = "active"
        changed = True
    if identity.last_login_at != user.last_login_at:
        identity.last_login_at = user.last_login_at
        changed = True
    if changed:
        db.flush()
    return identity


def find_password_login_account(db: Session, login_name: str) -> tuple[PortalUser | None, AccountIdentity | None]:
    normalized = normalize_login_name(login_name)
    identity = (
        db.query(AccountIdentity)
        .join(PortalUser, PortalUser.id == AccountIdentity.account_id)
        .filter(
            AccountIdentity.identity_type == IDENTITY_TYPE_PASSWORD,
            AccountIdentity.login_name == normalized,
            AccountIdentity.status == "active",
            PortalUser.status == "active",
        )
        .one_or_none()
    )
    if identity is not None:
        return identity.account, identity

    user = db.query(PortalUser).filter(PortalUser.username == normalized, PortalUser.status == "active").one_or_none()
    if user is None:
        return None, None
    identity = ensure_password_identity(db, user)
    return user, identity


def set_password_hash(db: Session, user: PortalUser, password_hash: str) -> None:
    user.password_hash = password_hash
    identity = ensure_password_identity(db, user)
    identity.password_hash = password_hash
    identity.status = "active"
    db.flush()


def find_wechat_identity_account(
    db: Session,
    *,
    provider_subject: str,
    provider_app_id: str,
    provider_unionid: str | None = None,
) -> tuple[PortalUser | None, AccountIdentity | None]:
    identity: AccountIdentity | None = None
    if provider_unionid:
        identity = (
            db.query(AccountIdentity)
            .join(PortalUser, PortalUser.id == AccountIdentity.account_id)
            .filter(
                AccountIdentity.identity_type == IDENTITY_TYPE_WECHAT_MINIAPP,
                AccountIdentity.provider_unionid == provider_unionid,
            )
            .one_or_none()
        )
    if identity is None:
        identity = (
            db.query(AccountIdentity)
            .join(PortalUser, PortalUser.id == AccountIdentity.account_id)
            .filter(
                AccountIdentity.identity_type == IDENTITY_TYPE_WECHAT_MINIAPP,
                AccountIdentity.provider_subject == provider_subject,
                AccountIdentity.provider_app_id == provider_app_id,
            )
            .one_or_none()
        )
    if identity is None:
        return None, None
    return identity.account, identity


def ensure_wechat_identity(
    db: Session,
    *,
    user: PortalUser,
    provider_subject: str,
    provider_app_id: str,
    provider_unionid: str | None = None,
) -> AccountIdentity:
    account, identity = find_wechat_identity_account(
        db,
        provider_subject=provider_subject,
        provider_app_id=provider_app_id,
        provider_unionid=provider_unionid,
    )
    if identity is not None and account is not None and account.id != user.id:
        raise ValueError("wechat identity already linked to another account")

    if identity is None:
        identity = AccountIdentity(
            account_id=user.id,
            identity_type=IDENTITY_TYPE_WECHAT_MINIAPP,
            provider_subject=provider_subject,
            provider_unionid=provider_unionid,
            provider_app_id=provider_app_id,
            status="active",
            verified_at=utcnow(),
            last_login_at=user.last_login_at,
        )
        db.add(identity)
        db.flush()
        return identity

    identity.account_id = user.id
    identity.provider_subject = provider_subject
    identity.provider_app_id = provider_app_id
    if provider_unionid:
        identity.provider_unionid = provider_unionid
    identity.status = "active"
    if identity.verified_at is None:
        identity.verified_at = utcnow()
    identity.last_login_at = user.last_login_at
    db.flush()
    return identity


def _normalize_bind_code(code: str) -> str:
    return "".join(code.strip().upper().split())


def expire_stale_bind_codes(db: Session, *, account_id: str | None = None, bind_type: str = BIND_TYPE_WECHAT_MINIAPP) -> int:
    now = utcnow()
    query = db.query(AccountBindCode).filter(
        AccountBindCode.bind_type == bind_type,
        AccountBindCode.status == "active",
        AccountBindCode.expires_at <= now,
    )
    if account_id is not None:
        query = query.filter(AccountBindCode.account_id == account_id)
    rows = query.all()
    for row in rows:
        row.status = "expired"
    if rows:
        db.flush()
    return len(rows)


def revoke_active_bind_codes(
    db: Session,
    *,
    account_id: str,
    bind_type: str = BIND_TYPE_WECHAT_MINIAPP,
    keep_id: str | None = None,
) -> int:
    rows = (
        db.query(AccountBindCode)
        .filter(
            AccountBindCode.account_id == account_id,
            AccountBindCode.bind_type == bind_type,
            AccountBindCode.status == "active",
        )
        .all()
    )
    affected = 0
    for row in rows:
        if keep_id is not None and row.id == keep_id:
            continue
        row.status = "revoked"
        affected += 1
    if affected:
        db.flush()
    return affected


def issue_wechat_bind_code(
    db: Session,
    *,
    user: PortalUser,
    ttl_seconds: int,
) -> AccountBindCode:
    expire_stale_bind_codes(db, account_id=user.id)
    revoke_active_bind_codes(db, account_id=user.id)
    expires_at = utcnow() + timedelta(seconds=max(int(ttl_seconds or 0), 60))
    for _ in range(8):
        code = "".join(secrets.choice(_BIND_CODE_ALPHABET) for _ in range(8))
        exists = db.query(AccountBindCode.id).filter(AccountBindCode.code == code).first()
        if exists is not None:
            continue
        row = AccountBindCode(
            account_id=user.id,
            code=code,
            bind_type=BIND_TYPE_WECHAT_MINIAPP,
            status="active",
            expires_at=expires_at,
        )
        db.add(row)
        db.flush()
        return row
    raise ValueError("unable to generate bind code")


def find_active_wechat_bind_code(db: Session, code: str) -> AccountBindCode | None:
    expire_stale_bind_codes(db)
    normalized = _normalize_bind_code(code)
    if not normalized:
        return None
    return (
        db.query(AccountBindCode)
        .filter(
            AccountBindCode.bind_type == BIND_TYPE_WECHAT_MINIAPP,
            AccountBindCode.code == normalized,
            AccountBindCode.status == "active",
        )
        .one_or_none()
    )


def claim_wechat_bind_code(
    db: Session,
    *,
    bind_code: AccountBindCode,
    shadow_user_id: str,
) -> AccountBindCode:
    bind_code.status = "claimed"
    bind_code.claimed_by_shadow_user_id = shadow_user_id
    bind_code.claimed_at = utcnow()
    revoke_active_bind_codes(db, account_id=bind_code.account_id, keep_id=bind_code.id)
    db.flush()
    return bind_code


def get_active_admin_user_ids(db: Session) -> set[str]:
    return {
        row[0]
        for row in db.query(AccountRole.account_id)
        .filter(AccountRole.role_code == ROLE_ADMIN, AccountRole.status == "active")
        .all()
    }


def is_portal_admin_account(db: Session, portal_user_id: str) -> bool:
    return portal_user_id in get_active_admin_user_ids(db)


def ensure_account_role(
    db: Session,
    *,
    user_id: str,
    role_code: str,
    operator_account_id: str | None = None,
    source: str = "manual",
    active: bool = True,
) -> AccountRole:
    role = (
        db.query(AccountRole)
        .filter(AccountRole.account_id == user_id, AccountRole.role_code == role_code)
        .one_or_none()
    )
    next_status = "active" if active else "inactive"
    if role is None:
        role = AccountRole(
            account_id=user_id,
            role_code=role_code,
            status=next_status,
            source=source,
            granted_by_account_id=operator_account_id,
        )
        db.add(role)
    else:
        role.status = next_status
        role.source = source
        role.granted_by_account_id = operator_account_id
    db.flush()
    return role


def expire_stale_entitlements(db: Session, *, user_id: str | None = None) -> int:
    now = utcnow()
    query = db.query(AccountEntitlement).filter(
        AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
        AccountEntitlement.status == "active",
        AccountEntitlement.expires_at.is_not(None),
        AccountEntitlement.expires_at <= now,
    )
    if user_id is not None:
        query = query.filter(AccountEntitlement.account_id == user_id)
    rows = query.all()
    for row in rows:
        row.status = "expired"
    if rows:
        db.flush()
    return len(rows)


def get_active_premium_entitlement(db: Session, user_id: str) -> AccountEntitlement | None:
    expire_stale_entitlements(db, user_id=user_id)
    now = utcnow()
    return (
        db.query(AccountEntitlement)
        .filter(
            AccountEntitlement.account_id == user_id,
            AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
            AccountEntitlement.status == "active",
            or_(AccountEntitlement.expires_at.is_(None), AccountEntitlement.expires_at > now),
        )
        .order_by(AccountEntitlement.expires_at.is_(None).desc(), AccountEntitlement.expires_at.desc(), AccountEntitlement.created_at.desc())
        .first()
    )


def upsert_premium_entitlement(
    db: Session,
    *,
    user_id: str,
    operator_account_id: str | None,
    expires_at: datetime | None,
    source: str,
    order_ref: str | None = None,
    meta_json: dict | None = None,
) -> AccountEntitlement:
    active_rows = (
        db.query(AccountEntitlement)
        .filter(
            AccountEntitlement.account_id == user_id,
            AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
            AccountEntitlement.status == "active",
        )
        .all()
    )
    now = utcnow()
    for row in active_rows:
        row.status = "revoked"
        row.revoked_at = now
    row = AccountEntitlement(
        account_id=user_id,
        entitlement_code=ENTITLEMENT_PREMIUM_MONITORING,
        status="active",
        source=source,
        starts_at=now,
        expires_at=expires_at,
        revoked_at=None,
        order_ref=order_ref,
        granted_by_account_id=operator_account_id,
        meta_json=dict(meta_json or {}),
    )
    db.add(row)
    db.flush()
    return row


def revoke_premium_entitlements(db: Session, *, user_id: str) -> int:
    rows = (
        db.query(AccountEntitlement)
        .filter(
            AccountEntitlement.account_id == user_id,
            AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
            AccountEntitlement.status == "active",
        )
        .all()
    )
    now = utcnow()
    for row in rows:
        row.status = "revoked"
        row.revoked_at = now
    if rows:
        db.flush()
    return len(rows)


def create_payment_order(
    db: Session,
    *,
    user_id: str,
    entitlement_code: str,
    source: str,
    duration_days: int,
    amount_cents: int,
    currency: str = "CNY",
    provider_name: str | None = None,
    provider_order_ref: str | None = None,
    meta_json: dict | None = None,
) -> AccountPaymentOrder:
    order = AccountPaymentOrder(
        account_id=user_id,
        entitlement_code=entitlement_code,
        source=source,
        status=ORDER_STATUS_PENDING,
        duration_days=max(int(duration_days or 0), 1),
        amount_cents=max(int(amount_cents or 0), 0),
        currency=(currency or "CNY").strip().upper() or "CNY",
        order_ref=new_id(),
        provider_name=provider_name,
        provider_order_ref=provider_order_ref,
        meta_json=dict(meta_json or {}),
    )
    db.add(order)
    db.flush()
    return order


def mark_payment_order_paid(
    db: Session,
    *,
    order: AccountPaymentOrder,
    operator_account_id: str | None,
    provider_payment_ref: str | None = None,
    meta_json: dict | None = None,
) -> AccountEntitlement:
    if order.status == ORDER_STATUS_PAID:
        entitlement = (
            db.query(AccountEntitlement)
            .filter(AccountEntitlement.order_ref == order.order_ref, AccountEntitlement.account_id == order.account_id)
            .order_by(AccountEntitlement.created_at.desc())
            .first()
        )
        if entitlement is not None:
            return entitlement
    if order.status != ORDER_STATUS_PENDING:
        raise ValueError("payment order is not payable")

    order.status = ORDER_STATUS_PAID
    order.paid_at = utcnow()
    if provider_payment_ref:
        order.provider_payment_ref = provider_payment_ref
    next_meta = dict(order.meta_json or {})
    next_meta.update(meta_json or {})
    order.meta_json = next_meta
    expires_at = utcnow() + timedelta(days=max(int(order.duration_days or 0), 1))
    entitlement = upsert_premium_entitlement(
        db,
        user_id=order.account_id,
        operator_account_id=operator_account_id,
        expires_at=expires_at,
        source=order.source,
        order_ref=order.order_ref,
        meta_json={
            "payment_order_id": order.id,
            "amount_cents": order.amount_cents,
            "currency": order.currency,
            "duration_days": order.duration_days,
        },
    )
    db.flush()
    return entitlement


def resolve_portal_access(db: Session, user: PortalUser) -> PortalAccessState:
    expired_premium = expire_stale_entitlements(db, user_id=user.id) > 0
    is_admin = is_portal_admin_account(db, user.id)
    entitlement = get_active_premium_entitlement(db, user.id)

    if is_admin:
        return PortalAccessState(is_admin=True, is_premium=True, premium_expires_at=None, expired_premium=expired_premium)

    if entitlement is not None:
        return PortalAccessState(
            is_admin=False,
            is_premium=True,
            premium_expires_at=entitlement.expires_at,
            expired_premium=expired_premium,
        )

    return PortalAccessState(is_admin=False, is_premium=False, premium_expires_at=None, expired_premium=expired_premium)


def ensure_admin_and_password_identity(db: Session, user: PortalUser, *, operator_account_id: str | None, source: str) -> None:
    ensure_password_identity(db, user)
    ensure_account_role(
        db,
        user_id=user.id,
        role_code=ROLE_ADMIN,
        operator_account_id=operator_account_id,
        source=source,
        active=True,
    )
    db.flush()


def entitlement_expiry_from_days(days: int | None) -> datetime:
    return utcnow() + timedelta(days=int(days or 30))
