from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.dependencies import Pagination, get_tenant_or_404
from app.services.catalog import ProductSort, order_products

router = APIRouter()


@router.get(
    "/favourites", response_model=list[schemas.ProductResponse], tags=["Favourites"]
)
def favourites(
    tenant_name: str | None = None,
    search: str | None = None,
    category: str | None = None,
    sort: ProductSort = "featured",
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    fav_products = (
        db.query(models.Product)
        .filter(
            models.Product.id.in_(
                db.query(models.Favourite.product_id).filter(
                    models.Favourite.user_id == current_user.id
                )
            )
        )
    )
    if tenant_name:
        tenant = get_tenant_or_404(db, tenant_name)
        fav_products = fav_products.filter(models.Product.tenant_id == tenant.id)
    if category:
        fav_products = fav_products.filter(models.Product.category == category)
    if search:
        fav_products = fav_products.filter(
            models.Product.name.contains(search, autoescape=True)
        )
    return (
        order_products(fav_products, sort)
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )


@router.post(
    "/favourites/{product_id}",
    response_model=schemas.ProductResponse,
    tags=["Favourites"],
)
def mark_favourite(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_product = (
        db.query(models.Product).filter(models.Product.id == product_id).first()
    )

    if not db_product:
        raise HTTPException(status_code=404, detail="no such product found")

    checkFav = (
        db.query(models.Favourite)
        .filter(
            models.Favourite.product_id == product_id,
            models.Favourite.user_id == current_user.id,
        )
        .first()
    )

    if checkFav:
        db.delete(checkFav)
        db.commit()
    else:
        obj = models.Favourite(user_id=current_user.id, product_id=product_id)
        db.add(obj)
        db.commit()
        db.refresh(obj)

    return db_product
