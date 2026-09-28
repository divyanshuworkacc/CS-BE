from app import models
from app.database import init_db
from tests.helpers import add_product


def test_history_survives_manager_access_removal(
    client, as_admin, make_tenant_user, login_as
):
    admin, brand = as_admin
    product = add_product(client, brand.name, quantity=10)
    manager, _ = make_tenant_user()
    login_as(manager)
    order = client.post(
        "/acme/orders",
        json={"order_items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert order.status_code == 200
    login_as(admin)
    assert client.delete(f'/acme/products/{product["id"]}').status_code == 409
    assert client.delete("/tenants/acme").status_code == 409
    assert client.delete(f"/acme/users/{manager.username}").status_code == 200
    # Use the real account lookup after revocation, not a cached fixture identity.
    from app.auth import get_current_user, get_token_payload
    from app.main import app

    app.dependency_overrides.pop(get_current_user)
    app.dependency_overrides[get_token_payload] = lambda: {
        "preferred_username": manager.username
    }
    assert client.get("/users/me").json()["role"] == "User"
    assert client.get("/acme/dashboard").status_code == 403
    assert client.get("/orders").json()[0]["id"] == order.json()["id"]


def test_manager_shops_elsewhere_but_cannot_manage_it(
    client, make_tenant_user, make_admin, login_as
):
    manager, own_brand = make_tenant_user(tenant_name="nike")
    admin, other_brand = make_admin(tenant_name="adidas")
    login_as(admin)
    product = add_product(client, other_brand.name, quantity=10)
    login_as(manager)
    assert client.get("/nike/dashboard").status_code == 200
    assert client.get("/adidas/dashboard").status_code == 403
    assert (
        client.patch(
            f'/adidas/products/{product["id"]}', json={"quantity": 40}
        ).status_code
        == 403
    )
    response = client.post(
        "/adidas/orders",
        json={"order_items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == other_brand.id
    assert len(client.get("/orders").json()) == 1
    assert client.get("/users/me").json()["tenant_name"] == own_brand.name


def test_customer_cannot_enter_management(client, as_user):
    assert client.get("/acme/dashboard").status_code == 403


def test_upgrade_detaches_only_customers_and_admins(
    db_session, make_admin, make_regular_user, make_tenant_user
):
    admin, brand = make_admin()
    customer, _ = make_regular_user()
    manager, _ = make_tenant_user()
    admin.tenant_id = brand.id
    customer.tenant_id = brand.id
    db_session.commit()
    init_db()
    init_db()
    db_session.expire_all()
    assert admin.tenant_id is None
    assert customer.tenant_id is None
    assert manager.tenant_id == brand.id
    assert db_session.query(models.User).count() == 3


def test_brand_removal_turns_its_manager_into_customer(
    client, as_admin, make_tenant_user, db_session
):
    manager, brand = make_tenant_user()
    assert client.delete(f"/tenants/{brand.name}").status_code == 200
    db_session.expire_all()
    assert manager.tenant_id is None
    assert manager.role.name == "User"


def test_customer_history_is_private_across_brands(
    client, as_user, make_regular_user, login_as
):
    assert client.get("/orders").json() == []
    assert client.get("/orders?limit=0").status_code == 422


def test_existing_local_username_does_not_create_keycloak_account(
    client, as_admin, make_regular_user
):
    from unittest.mock import Mock
    from app.main import app
    from app.services.keycloak import get_keycloak_admin

    customer, _ = make_regular_user()
    keycloak = Mock()
    app.dependency_overrides[get_keycloak_admin] = lambda: keycloak
    response = client.post(
        "/acme/users",
        json={
            "name": "Manager",
            "username": customer.username,
            "password": "test-password",
        },
    )
    assert response.status_code == 409
    keycloak.create_user.assert_not_called()
