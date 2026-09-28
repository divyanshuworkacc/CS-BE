"""Isolated SQLite database and authentication overrides for API tests."""

import os
from tempfile import TemporaryDirectory

# Override even an inherited production DATABASE_URL before importing the app.
_test_directory = TemporaryDirectory(prefix="assignment-tests-")
_original_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_directory.name}/test.db"

import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app
from app.database import engine, SessionLocal
from app.auth import get_current_user, get_token_payload


@pytest.fixture
def db_session():
    """Fresh schema + reseeded roles before every test."""
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    for role_name in ["Admin", "Tenant", "User"]:
        db.add(models.Role(name=role_name))
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _make_user_row(db, username, role_name, tenant_name):
    tenant = db.query(models.Tenant).filter(models.Tenant.name == tenant_name).first()
    if not tenant:
        tenant = models.Tenant(name=tenant_name)
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

    role = db.query(models.Role).filter(models.Role.name == role_name).first()
    user = models.User(
        name=username,
        username=username,
        tenant_id=tenant.id if role_name == "Tenant" else None,
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, tenant


@pytest.fixture
def make_admin(db_session):
    return lambda username="test_admin", tenant_name="acme": _make_user_row(
        db_session, username, "Admin", tenant_name
    )


@pytest.fixture
def make_tenant_user(db_session):
    return lambda username="test_tenant", tenant_name="acme": _make_user_row(
        db_session, username, "Tenant", tenant_name
    )


@pytest.fixture
def make_regular_user(db_session):
    return lambda username="test_user", tenant_name="acme": _make_user_row(
        db_session, username, "User", tenant_name
    )


@pytest.fixture
def login_as():
    """Switch the 'logged in' identity mid-test. Call login_as(user) again to switch."""

    def _login_as(user):
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_token_payload] = lambda: {
            "preferred_username": user.username
        }
        return user

    return _login_as


@pytest.fixture
def as_admin(make_admin, login_as):
    user, tenant = make_admin()
    login_as(user)
    return user, tenant


@pytest.fixture
def as_tenant(make_tenant_user, login_as):
    user, tenant = make_tenant_user()
    login_as(user)
    return user, tenant


@pytest.fixture
def as_user(make_regular_user, login_as):
    user, tenant = make_regular_user()
    login_as(user)
    return user, tenant


@pytest.fixture
def as_new_signup():
    """A verified Keycloak token for someone with NO local row yet — for testing POST /users."""
    app.dependency_overrides[get_token_payload] = lambda: {
        "preferred_username": "newbie"
    }
    return "newbie"


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    _test_directory.cleanup()
    if _original_database_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = _original_database_url
