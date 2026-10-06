from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app import models
from app.main import app
from app.services.keycloak import get_keycloak_admin


@pytest.fixture
def keycloak():
    service = Mock()
    service.create_user.return_value = "new-keycloak-id"
    app.dependency_overrides[get_keycloak_admin] = lambda: service
    return service


def test_customer_signup_without_any_brand(client, as_new_signup, db_session):
    response = client.post("/users", json={"name": "New Customer"})
    assert response.status_code == 200
    assert response.json()["tenant_id"] is None
    assert response.json()["username"] == "newbie"
    user = db_session.query(models.User).filter_by(username="newbie").one()
    assert user.role.name == "User"
    assert db_session.query(models.Tenant).count() == 0
    assert client.post("/users", json={"name": "Duplicate"}).status_code == 409


def test_admin_creates_manager_with_keycloak_credentials(
    client, as_admin, keycloak, db_session
):
    response = client.post(
        "/acme/users",
        json={"name": "Manager", "username": "manager", "password": "test-password"},
    )
    assert response.status_code == 200
    assert "password" not in response.text
    manager = db_session.query(models.User).filter_by(username="manager").one()
    assert manager.role.name == "Tenant"
    assert manager.tenant_id == as_admin[1].id
    keycloak.create_user.assert_called_once()


def test_provisioning_failure_does_not_create_local_account(
    client, as_admin, keycloak, db_session
):
    keycloak.create_user.side_effect = HTTPException(503, "Unavailable")
    assert (
        client.post(
            "/acme/users",
            json={
                "name": "Manager",
                "username": "manager",
                "password": "test-password",
            },
        ).status_code
        == 503
    )
    assert db_session.query(models.User).filter_by(username="manager").first() is None


def test_only_admin_can_create_managers(client, as_user, keycloak):
    assert (
        client.post(
            "/acme/users",
            json={
                "name": "Manager",
                "username": "manager",
                "password": "test-password",
            },
        ).status_code
        == 403
    )
    keycloak.create_user.assert_not_called()


def test_admin_can_reset_manager_password(client, as_admin, make_tenant_user, keycloak):
    manager, _ = make_tenant_user()
    response = client.patch(
        f"/acme/users/{manager.username}", json={"password": "new-password"}
    )
    assert response.status_code == 200
    keycloak.reset_password.assert_called_once_with(manager.username, "new-password")


def test_removing_manager_preserves_customer_account(
    client, as_admin, make_tenant_user, db_session
):
    manager, _ = make_tenant_user()
    response = client.delete(f"/acme/users/{manager.username}")
    assert response.status_code == 200
    db_session.expire_all()
    assert manager.tenant_id is None
    assert manager.role.name == "User"
    assert client.delete(f"/acme/users/{manager.username}").status_code == 404


def test_non_admin_cannot_list_managers(client, as_tenant):
    assert client.get("/acme/users").status_code == 403


def test_password_validation_does_not_echo_secret(client, as_admin):
    response = client.post(
        "/acme/users",
        json={"name": "Manager", "username": "manager", "password": "SECRET"},
    )
    assert response.status_code == 422
    assert "SECRET" not in response.text
