"""Grant platform admin access to an existing Keycloak username (no brand needed)."""

import argparse

from app import models
from app.database import SessionLocal, init_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    args = parser.parse_args()
    username = args.username.strip().lower()
    if not username:
        parser.error("username must not be empty")
    init_db()
    with SessionLocal() as db:
        role = db.query(models.Role).filter_by(name="Admin").one()
        user = db.query(models.User).filter_by(username=username).first()
        if user is None:
            user = models.User(name=username, username=username)
            db.add(user)
        user.role_id = role.id
        user.tenant_id = None
        db.commit()
    print(f"{username} is now a platform Admin, without a brand assignment.")


if __name__ == "__main__":
    main()
