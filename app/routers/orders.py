from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import get_current_user
from app.database import get_db
from app.dependencies import Pagination, get_tenant_or_404

router = APIRouter()


@router.post("/orders", response_model=list[schemas.OrderResponse], tags=["Orders"])
def create_marketplace_checkout(
    order: schemas.OrderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Place one marketplace checkout across brands as one database transaction.

    Orders remain brand-scoped in storage, so checkout creates one order per
    brand while validating stock and committing every order together.
    """
    requested: dict[int, int] = {}
    for item in order.order_items:
        requested[item.product_id] = requested.get(item.product_id, 0) + item.quantity

    products = (
        db.query(models.Product)
        .filter(models.Product.id.in_(requested))
        .with_for_update()
        .all()
    )
    products_by_id = {product.id: product for product in products}
    if len(products_by_id) != len(requested):
        missing = next(product_id for product_id in requested if product_id not in products_by_id)
        raise HTTPException(status_code=404, detail=f"Product ID {missing} not found")

    for product_id, quantity in requested.items():
        if products_by_id[product_id].quantity <= quantity:
            raise HTTPException(status_code=400, detail="Insufficient product quantity")

    grouped: dict[int, list[models.OrderItem]] = {}
    for product_id, quantity in requested.items():
        product = products_by_id[product_id]
        product.quantity -= quantity
        grouped.setdefault(product.tenant_id, []).append(
            models.OrderItem(product_id=product_id, quantity=quantity)
        )

    created_orders = []
    for tenant_id, order_items in sorted(grouped.items()):
        amount = sum(products_by_id[item.product_id].price * item.quantity for item in order_items)
        created_orders.append(
            models.Order(
                total_quantity=sum(item.quantity for item in order_items),
                amount=amount,
                user_id=current_user.id,
                tenant_id=tenant_id,
                order_items=order_items,
            )
        )

    try:
        db.add_all(created_orders)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for created_order in created_orders:
        db.refresh(created_order)
    return created_orders


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
