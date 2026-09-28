from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.dependencies import Pagination, get_tenant_or_404

router = APIRouter()


@router.post(
    "/{tenant_name}/orders", response_model=schemas.OrderResponse, tags=["Orders"]
)
def create_order(
    tenant_name: str,
    order: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):

    db_tenant = get_tenant_or_404(db, tenant_name)

    total_quantity = sum([item.quantity for item in order.order_items])
    total_amount = 0.0

    order_items_list = []

    for item in order.order_items:
        product = (
            db.query(models.Product)
            .filter(
                models.Product.id == item.product_id,
                models.Product.tenant_id == db_tenant.id,
            )
            .first()
        )

        if not product:
            raise HTTPException(
                status_code=404, detail=f"Product ID {item.product_id} not found"
            )

        total_amount += product.price * item.quantity

        if (
            product.quantity > item.quantity
        ):  # The assignment asks the condition to be ">" instead of ">="
            product.quantity -= item.quantity
        else:
            raise HTTPException(status_code=400, detail="Insufficient product quantity")

        new_order_item = models.OrderItem(
            product_id=item.product_id, quantity=item.quantity
        )

        order_items_list.append(new_order_item)

    db_order = models.Order(
        total_quantity=total_quantity,
        amount=total_amount,
        user_id=current_user.id,
        tenant_id=db_tenant.id,
        order_items=order_items_list,
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return db_order


@router.get(
    "/{tenant_name}/orders", response_model=list[schemas.OrderResponse], tags=["Orders"]
)
def get_orders(
    tenant_name: str,
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_tenant = get_tenant_or_404(db, tenant_name)

    orders = (
        db.query(models.Order)
        .filter(
            models.Order.user_id == current_user.id,
            models.Order.tenant_id == db_tenant.id,
        )
        .order_by(models.Order.id.desc())
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )

    return orders


@router.get("/orders", response_model=list[schemas.OrderResponse], tags=["Orders"])
def all_my_orders(
    page: Pagination = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """A customer's purchase history across all brands, including manager purchases."""
    return (
        db.query(models.Order)
        .filter_by(user_id=current_user.id)
        .order_by(models.Order.id.desc())
        .offset(page.skip)
        .limit(page.limit)
        .all()
    )
