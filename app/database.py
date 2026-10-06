import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'ecommerce.db'}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if SQLALCHEMY_DATABASE_URL.startswith("sqlite:")
        else {}
    ),
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create tables and seed roles when the application starts."""
    from app import models

    models.Base.metadata.create_all(bind=engine)
    order_columns = {column["name"] for column in inspect(engine).get_columns("orders")}
    if "address" not in order_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE orders ADD COLUMN address VARCHAR(500)"))
    with SessionLocal() as db:
        for role_name in ("Admin", "Tenant", "User"):
            if not db.query(models.Role).filter(models.Role.name == role_name).first():
                db.add(models.Role(name=role_name))
        db.flush()
        # Upgrade the original data model: only managers belong to a brand.
        independent_roles = db.query(models.Role.id).filter(
            models.Role.name.in_(("Admin", "User"))
        )
        db.query(models.User).filter(
            models.User.role_id.in_(independent_roles),
            models.User.tenant_id.is_not(None),
        ).update({models.User.tenant_id: None}, synchronize_session=False)
        db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
