from sqlalchemy import Column, Integer, String, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    orders = relationship("Order", back_populates="tenant")
    users = relationship("User", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    username = Column(String, unique=True, index=True)

    # Only brand managers have a tenant. Customers and platform admins do not.
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"))

    favourite = relationship("Favourite", back_populates="user")
    role = relationship("Role", back_populates="users")
    tenant = relationship("Tenant", back_populates="users")
    orders = relationship("Order", back_populates="user")


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_product_tenant_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String, index=True)
    price = Column(Float)
    quantity = Column(Integer)

    tenant_id = Column(Integer, ForeignKey("tenants.id"))

    favourite = relationship("Favourite", back_populates="product")
    tenant = relationship("Tenant", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")


class Favourite(Base):
    __tablename__ = "favourites"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("products.id"))

    user = relationship("User", back_populates="favourite")
    product = relationship("Product", back_populates="favourite")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    total_quantity = Column(Integer)
    amount = Column(Float)

    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")
    tenant = relationship("Tenant", back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    quantity = Column(Integer)

    product_id = Column(Integer, ForeignKey("products.id"))
    order_id = Column(Integer, ForeignKey("orders.id"))

    product = relationship("Product", back_populates="order_items")
    order = relationship("Order", back_populates="order_items")
