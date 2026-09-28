"""Brands are managed by platform admins, not by customers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import (
    Pagination,
    get_tenant_or_404,
    require_admin,
    require_brand_manager,
)
from app.services.accounts import remove_brand_access

router = APIRouter(tags=["Tenants"])


@router.post(
    "/tenants",
    response_model=schemas.TenantResponse,
    dependencies=[Depends(require_admin)],
)
def create_tenant(tenant: schemas.TenantCreate, db: Session = Depends(get_db)):
    row = models.Tenant(name=tenant.name)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Brand already exists")
    db.refresh(row)
    return row


@router.get("/tenants", response_model=list[schemas.TenantResponse])
def get_tenants(page: Pagination = Depends(), db: Session = Depends(get_db)):
    return (
        db.query(models.Tenant)
        .order_by(models.Tenant.id)
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )


@router.get("/{tenant_name}/dashboard", response_model=schemas.TenantResponse)
def brand_dashboard(tenant=Depends(require_brand_manager)):
    """Frontend management entry point: reject another brand's manager."""
    return tenant


@router.delete(
    "/tenants/{tenant_name}",
    response_model=schemas.TenantResponse,
    dependencies=[Depends(require_admin)],
)
def delete_tenant(tenant_name: str, db: Session = Depends(get_db)):
    tenant = get_tenant_or_404(db, tenant_name)
    if db.query(models.Order).filter_by(tenant_id=tenant.id).first():
        raise HTTPException(409, "This brand has order history and cannot be deleted")
    result = schemas.TenantResponse.model_validate(tenant)
    for user in db.query(models.User).filter_by(tenant_id=tenant.id).all():
        remove_brand_access(db, user)
    for product in db.query(models.Product).filter_by(tenant_id=tenant.id).all():
        db.query(models.Favourite).filter_by(product_id=product.id).delete()
        db.delete(product)
    db.flush()
    db.delete(tenant)
    db.commit()
    return result
