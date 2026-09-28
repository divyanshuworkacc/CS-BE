"""Small, shared permission and lookup helpers."""

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.database import get_db


class Pagination:
    def __init__(
        self, skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)
    ):
        self.skip = skip
        self.limit = limit


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role.name != "Admin":
        raise HTTPException(status_code=403, detail="Platform admin access required")
    return user


def get_tenant_or_404(db: Session, tenant_name: str) -> models.Tenant:
    tenant = db.query(models.Tenant).filter(models.Tenant.name == tenant_name).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return tenant


def require_brand_manager(
    tenant_name: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Tenant:
    tenant = get_tenant_or_404(db, tenant_name)
    if user.role.name == "Admin":
        return tenant
    if user.role.name == "Tenant" and user.tenant_id == tenant.id:
        return tenant
    raise HTTPException(status_code=403, detail="You cannot manage this brand")


def get_brand_manager(db: Session, tenant_id: int, username: str) -> models.User:
    user = (
        db.query(models.User)
        .join(models.Role)
        .filter(
            models.User.username == username,
            models.User.tenant_id == tenant_id,
            models.Role.name == "Tenant",
        )
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="Brand manager not found")
    return user
