"""Customer registration and platform-admin management of brand logins."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user, get_token_payload
from app.database import get_db
from app.dependencies import (
    Pagination,
    get_brand_manager,
    get_tenant_or_404,
    require_admin,
)
from app.services.accounts import create_brand_manager, remove_brand_access
from app.services.keycloak import KeycloakAdmin, get_keycloak_admin

router = APIRouter(tags=["Users"])


@router.post("/users", response_model=schemas.UserResponse)
def register_customer(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):  
    username = payload.get("preferred_username")
    given_name = payload.get("given_name", "")
    family_name = payload.get("family_name", "")
    name = f"{given_name} {family_name}".strip()
    if not isinstance(username, str) or not username.strip():
        raise HTTPException(401, "Token missing preferred_username")
    username = username.strip().lower()
    if (
        db.query(models.User)
        .filter(func.lower(models.User.username) == username)
        .first()
    ):
        raise HTTPException(409, "Username already registered")
    role = db.query(models.Role).filter(models.Role.name == "User").one()
    user = models.User(
        name=name, username=username, role_id=role.id, tenant_id=None
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already registered") from None
    db.refresh(user)
    return user


@router.get("/users/me", response_model=schemas.CurrentUserResponse)
def get_my_profile(user: models.User = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "role_id": user.role_id,
        "role": user.role.name,
        "tenant_id": user.tenant_id,
        "tenant_name": user.tenant.name if user.tenant else None,
    }


@router.get(
    "/roles",
    response_model=list[schemas.RoleResponse],
    dependencies=[Depends(require_admin)],
)
def list_roles(db: Session = Depends(get_db)):
    return db.query(models.Role).order_by(models.Role.id).all()


@router.post(
    "/{tenant_name}/users",
    response_model=schemas.UserResponse,
    dependencies=[Depends(require_admin)],
)
def add_brand_manager(
    tenant_name: str,
    details: schemas.BrandManagerCreate,
    db: Session = Depends(get_db),
    keycloak: KeycloakAdmin = Depends(get_keycloak_admin),
):
    tenant = get_tenant_or_404(db, tenant_name)
    return create_brand_manager(db, tenant, details, keycloak)


@router.get(
    "/{tenant_name}/users",
    response_model=list[schemas.UserResponse],
    dependencies=[Depends(require_admin)],
)
def list_brand_managers(
    tenant_name: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    tenant = get_tenant_or_404(db, tenant_name)
    return (
        db.query(models.User)
        .join(models.Role)
        .filter(
            models.User.tenant_id == tenant.id,
            models.Role.name == "Tenant",
        )
        .order_by(models.User.id)
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )


@router.patch(
    "/{tenant_name}/users/{username}",
    response_model=schemas.UserResponse,
    dependencies=[Depends(require_admin)],
)
def update_brand_manager(
    tenant_name: str,
    username: str,
    details: schemas.BrandManagerUpdate,
    db: Session = Depends(get_db),
    keycloak: KeycloakAdmin = Depends(get_keycloak_admin),
):
    tenant = get_tenant_or_404(db, tenant_name)
    user = get_brand_manager(db, tenant.id, username)
    if details.password is not None:
        keycloak.reset_password(user.username, details.password.get_secret_value())
    if details.name is not None:
        user.name = details.name
    db.commit()
    db.refresh(user)
    return user


@router.delete(
    "/{tenant_name}/users/{username}",
    response_model=schemas.UserResponse,
    dependencies=[Depends(require_admin)],
)
def revoke_brand_manager(
    tenant_name: str, username: str, db: Session = Depends(get_db)
):
    tenant = get_tenant_or_404(db, tenant_name)
    user = get_brand_manager(db, tenant.id, username)
    remove_brand_access(db, user)
    db.commit()
    db.refresh(user)
    return user
