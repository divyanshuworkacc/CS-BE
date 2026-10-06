"""Public brand catalog; changes require permission to manage that brand."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import Pagination, get_tenant_or_404, require_brand_manager
from app.services.catalog import ProductSort, order_products

router = APIRouter(tags=["Products"])


def find_product(db, tenant_id, product_id):
    product = (
        db.query(models.Product).filter_by(id=product_id, tenant_id=tenant_id).first()
    )
    if product is None:
        raise HTTPException(404, "Product not found")
    return product


def save_product(db, product):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Product name already exists for this brand")
    db.refresh(product)
    return product


@router.post("/{tenant_name}/products", response_model=schemas.ProductResponse)
def add_product(
    product: schemas.ProductCreate,
    tenant=Depends(require_brand_manager),
    db: Session = Depends(get_db),
):
    row = models.Product(**product.model_dump(), tenant_id=tenant.id)
    db.add(row)
    return save_product(db, row)


@router.get("/categories", response_model=list[str])
def get_categories(tenant_name: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Product.category)
    if tenant_name:
        tenant = get_tenant_or_404(db, tenant_name)
        query = query.filter(models.Product.tenant_id == tenant.id)
    return [
        category
        for (category,) in query.distinct().order_by(models.Product.category).all()
    ]



@router.get("/{tenant_name}/products", response_model=list[schemas.ProductResponse])
def get_products(
    tenant_name: str,
    search: str | None = None,
    category: str | None = None,
    sort: ProductSort = "featured",
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    tenant = get_tenant_or_404(db, tenant_name)
    query = db.query(models.Product).filter_by(tenant_id=tenant.id)
    if category:
        query = query.filter(models.Product.category == category)
    if search:
        query = query.filter(models.Product.name.contains(search, autoescape=True))
    return order_products(query, sort).offset(page.skip).limit(page.limit).all()


@router.get("/products", response_model=list[schemas.ProductResponse])
def get_all_products(
    search: str | None = None,
    category: str | None = None,
    sort: ProductSort = "featured",
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
):
    query = db.query(models.Product)
    if category:
        query = query.filter(models.Product.category == category)
    if search:
        query = query.filter(models.Product.name.contains(search, autoescape=True))
    return (
        order_products(query, sort)
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )

@router.patch(
    "/{tenant_name}/products/{product_id}", response_model=schemas.ProductResponse
)
def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    tenant=Depends(require_brand_manager),
    db: Session = Depends(get_db),
):
    product = find_product(db, tenant.id, product_id)
    for field, value in product_update.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    return save_product(db, product)


@router.delete(
    "/{tenant_name}/products/{product_id}", response_model=schemas.ProductResponse
)
def delete_product(
    product_id: int,
    tenant=Depends(require_brand_manager),
    db: Session = Depends(get_db),
):
    product = find_product(db, tenant.id, product_id)
    if db.query(models.OrderItem).filter_by(product_id=product.id).first():
        raise HTTPException(
            409, "This product has order history; set its quantity to zero instead"
        )
    result = schemas.ProductResponse.model_validate(product)
    db.query(models.Favourite).filter_by(product_id=product.id).delete()
    db.delete(product)
    db.commit()
    return result


