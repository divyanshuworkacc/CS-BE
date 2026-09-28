"""Shared ordering for product catalog queries."""

from typing import Literal

from sqlalchemy import func

from app import models

ProductSort = Literal["featured", "price-low", "price-high", "name"]


def order_products(query, sort: ProductSort):
    """Apply deterministic sorting before pagination to a Product query."""
    if sort == "price-low":
        return query.order_by(models.Product.price.asc(), models.Product.id.asc())
    if sort == "price-high":
        return query.order_by(models.Product.price.desc(), models.Product.id.asc())
    if sort == "name":
        return query.order_by(
            func.lower(models.Product.name).asc(), models.Product.id.asc()
        )
    return query.order_by(models.Product.tenant_id.asc(), models.Product.id.asc())
