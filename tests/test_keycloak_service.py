from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app import schemas
from app.services.keycloak import KeycloakAdmin
from app.services.accounts import create_brand_manager


def test_missing_secret_has_actionable_error(monkeypatch):
    monkeypatch.delenv("KEYCLOAK_ADMIN_CLIENT_SECRET", raising=False)
    with pytest.raises(HTTPException) as error:
        KeycloakAdmin()._token()
    assert error.value.status_code == 503
    assert "KEYCLOAK_ADMIN_CLIENT_SECRET" in error.value.detail


def test_create_uses_keycloak_credentials_and_location():
    service = KeycloakAdmin()
    service._request = Mock(
        return_value=(None, {"Location": "http://keycloak/users/new-id"})
    )
    assert service.create_user("manager", "Manager", "a-password") == "new-id"
    method, path, body = service._request.call_args.args
    assert (method, path) == ("POST", "/users")
    assert body["credentials"][0]["value"] == "a-password"
    assert body["enabled"] is True


def test_reset_resolves_exact_username():
    service = KeycloakAdmin()
    service._request = Mock(side_effect=[([{"id": "user-id"}], {}), (None, {})])
    service.reset_password("manager", "a-password")
    assert "exact=true" in service._request.call_args_list[0].args[1]
    assert service._request.call_args.args[:2] == (
        "PUT",
        "/users/user-id/reset-password",
    )


@pytest.mark.parametrize(
    "upstream,expected", [(400, 400), (401, 503), (403, 503), (409, 409), (500, 502)]
)
def test_upstream_errors_are_safe(monkeypatch, upstream, expected):
    monkeypatch.setattr(
        "app.services.keycloak.urlopen",
        Mock(side_effect=HTTPError("url", upstream, "private details", {}, None)),
    )
    with pytest.raises(HTTPException) as error:
        KeycloakAdmin()._send(Mock())
    assert error.value.status_code == expected
    assert "private details" not in error.value.detail


def test_local_failure_removes_only_new_external_account():
    db = Mock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.one.return_value = Mock(id=2)
    db.commit.side_effect = IntegrityError("insert", {}, Exception())
    keycloak = Mock()
    keycloak.create_user.return_value = "new-id"
    details = schemas.BrandManagerCreate(
        name="Manager", username="manager", password="test-password"
    )
    with pytest.raises(HTTPException) as error:
        create_brand_manager(db, Mock(id=1), details, keycloak)
    assert error.value.status_code == 409
    db.rollback.assert_called_once()
    keycloak.delete_created_user.assert_called_once_with("new-id")
