"""Brand managers are the only accounts assigned to a brand."""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.keycloak import KeycloakAdmin


def create_brand_manager(
    db: Session,
    tenant: models.Tenant,
    details: schemas.BrandManagerCreate,
    keycloak: KeycloakAdmin,
) -> models.User:
    existing = (
        db.query(models.User)
        .filter(func.lower(models.User.username) == details.username.lower())
        .first()
    )
    if existing:
        raise HTTPException(409, "Username already registered")
    role = db.query(models.Role).filter(models.Role.name == "Tenant").one()
    account_id = keycloak.create_user(
        details.username, details.name, details.password.get_secret_value()
    )
    user = models.User(
        name=details.name,
        username=details.username,
        role_id=role.id,
        tenant_id=tenant.id,
    )
    try:
        db.add(user)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        try:
            keycloak.delete_created_user(account_id)
        except HTTPException:
            raise HTTPException(
                503,
                "Local account creation failed; remove the new Keycloak username before retrying",
            ) from None
        if isinstance(error, IntegrityError):
            raise HTTPException(409, "Username already registered") from None
        raise HTTPException(
            503, "Could not save the brand account; please retry"
        ) from None
    db.refresh(user)
    return user


def remove_brand_access(db: Session, user: models.User):
    """Removing a manager keeps their shopper account and purchase history."""
    customer_role = db.query(models.Role).filter(models.Role.name == "User").one()
    user.role_id = customer_role.id
    user.tenant_id = None
