from app.db import SessionLocal
from app.models import AccountEntitlement, AccountIdentity, AccountPaymentOrder, AccountRole, PortalUser


def _bootstrap_admin_headers(client, username: str = "auth_model_admin", password: str = "StrongPass123") -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "nickname": username},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]
    promote_response = client.post(
        f"/api/v1/admin/users/{user_id}/promote",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert promote_response.status_code == 200
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert login_response.status_code == 200
    return {"X-User-Token": login_response.json()["access_token"]}


def test_register_creates_password_identity(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "identity_user", "password": "StrongPass123", "nickname": "身份用户"},
    )
    assert response.status_code == 200
    user_id = response.json()["user_id"]

    with SessionLocal() as db:
        user = db.query(PortalUser).filter(PortalUser.id == user_id).one()
        identity = (
            db.query(AccountIdentity)
            .filter(AccountIdentity.account_id == user.id, AccountIdentity.identity_type == "password")
            .one()
        )
        assert identity.login_name == "identity_user"
        assert identity.password_hash == user.password_hash
        assert identity.status == "active"


def test_promote_to_admin_creates_account_role(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "role_admin_user", "password": "StrongPass123", "nickname": "管理员角色"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    admin_headers = _bootstrap_admin_headers(client, "role_admin_bootstrap")
    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)
    assert promote_response.status_code == 200

    with SessionLocal() as db:
        role = (
            db.query(AccountRole)
            .filter(AccountRole.account_id == user_id, AccountRole.role_code == "admin")
            .one()
        )
        assert role.status == "active"


def test_promote_to_premium_creates_account_entitlement(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "entitlement_user", "password": "StrongPass123", "nickname": "高级权益"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    admin_headers = _bootstrap_admin_headers(client, "entitlement_admin_bootstrap")
    promote_response = client.post(
        f"/api/v1/admin/users/{user_id}/promote",
        json={"target_role": "premium", "premium_days": 7},
        headers=admin_headers,
    )
    assert promote_response.status_code == 200

    with SessionLocal() as db:
        entitlement = (
            db.query(AccountEntitlement)
            .filter(
                AccountEntitlement.account_id == user_id,
                AccountEntitlement.entitlement_code == "premium_monitoring",
                AccountEntitlement.status == "active",
            )
            .one()
        )
        assert entitlement.source == "admin_grant"
        assert entitlement.expires_at is not None

def test_payment_order_mark_paid_creates_entitlement(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "payment_order_user", "password": "StrongPass123", "nickname": "订单用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    user_login = client.post(
        "/api/v1/auth/login",
        json={"username": "payment_order_user", "password": "StrongPass123"},
    )
    token = user_login.json()["access_token"]
    create_order = client.post(
        "/api/v1/auth/me/premium-orders",
        headers={"X-User-Token": token},
        json={"duration_days": 30, "source": "web_pay"},
    )
    assert create_order.status_code == 200
    order_id = create_order.json()["id"]

    admin_headers = _bootstrap_admin_headers(client, "payment_admin_bootstrap")
    mark_paid = client.post(f"/api/v1/admin/payment-orders/{order_id}/mark-paid", json={}, headers=admin_headers)
    assert mark_paid.status_code == 200
    assert mark_paid.json()["status"] == "paid"

    with SessionLocal() as db:
        order = db.query(AccountPaymentOrder).filter(AccountPaymentOrder.id == order_id).one()
        assert order.status == "paid"
        entitlement = (
            db.query(AccountEntitlement)
            .filter(AccountEntitlement.account_id == user_id, AccountEntitlement.order_ref == order.order_ref)
            .one()
        )
        assert entitlement.status == "active"
        assert entitlement.source == "web_pay"
