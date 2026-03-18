import argparse

from app.db import SessionLocal
from app.models import AccountEntitlement, AccountIdentity, AccountRole, AdminAccount, PortalUser, utcnow
from app.services.account_access import (
    ENTITLEMENT_PREMIUM_MONITORING,
    ROLE_ADMIN,
    ensure_account_role,
    ensure_password_identity,
    upsert_premium_entitlement,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill account identity, role, and entitlement records.")
    parser.add_argument("--dry-run", action="store_true", help="Only report changes without committing.")
    args = parser.parse_args()

    scanned_users = 0
    created_identities = 0
    created_roles = 0
    created_entitlements = 0
    created_expired_entitlements = 0

    with SessionLocal() as db:
        admin_ids = {row[0] for row in db.query(AdminAccount.user_id).filter(AdminAccount.status == "active").all()}
        rows = db.query(PortalUser).order_by(PortalUser.created_at.asc()).all()
        for user in rows:
            scanned_users += 1

            identity_exists = (
                db.query(AccountIdentity.id)
                .filter(AccountIdentity.account_id == user.id, AccountIdentity.identity_type == "password")
                .first()
                is not None
            )
            ensure_password_identity(db, user)
            if not identity_exists:
                created_identities += 1

            if user.id in admin_ids:
                role_exists = (
                    db.query(AccountRole.id)
                    .filter(AccountRole.account_id == user.id, AccountRole.role_code == ROLE_ADMIN)
                    .first()
                    is not None
                )
                ensure_account_role(
                    db,
                    user_id=user.id,
                    role_code=ROLE_ADMIN,
                    operator_account_id=None,
                    source="migration",
                    active=True,
                )
                if not role_exists:
                    created_roles += 1
                continue

            if not bool(user.premium_monitoring_enabled):
                continue

            if user.premium_expires_at is None or user.premium_expires_at > utcnow():
                entitlement_exists = (
                    db.query(AccountEntitlement.id)
                    .filter(
                        AccountEntitlement.account_id == user.id,
                        AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
                        AccountEntitlement.status == "active",
                    )
                    .first()
                    is not None
                )
                upsert_premium_entitlement(
                    db,
                    user_id=user.id,
                    operator_account_id=None,
                    expires_at=user.premium_expires_at,
                    source="migration",
                )
                if not entitlement_exists:
                    created_entitlements += 1
                continue

            existing = (
                db.query(AccountEntitlement)
                .filter(
                    AccountEntitlement.account_id == user.id,
                    AccountEntitlement.entitlement_code == ENTITLEMENT_PREMIUM_MONITORING,
                    AccountEntitlement.status == "expired",
                )
                .first()
            )
            if existing is None:
                db.add(
                    AccountEntitlement(
                        account_id=user.id,
                        entitlement_code=ENTITLEMENT_PREMIUM_MONITORING,
                        status="expired",
                        source="migration",
                        starts_at=user.created_at,
                        expires_at=user.premium_expires_at,
                        meta_json={"legacy": True},
                    )
                )
                created_expired_entitlements += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    print(
        "scanned_users={scanned_users} created_identities={created_identities} "
        "created_roles={created_roles} created_entitlements={created_entitlements} "
        "created_expired_entitlements={created_expired_entitlements} dry_run={dry_run}".format(
            scanned_users=scanned_users,
            created_identities=created_identities,
            created_roles=created_roles,
            created_entitlements=created_entitlements,
            created_expired_entitlements=created_expired_entitlements,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
