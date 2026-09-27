import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password


def create_admin_if_missing(db: Session) -> None:
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        return  # nothing configured, skip silently

    existing = db.scalar(select(User).where(User.email == admin_email.lower()))
    if existing is not None:
        return  # admin already exists

    admin = User(
        email=admin_email.lower(),
        hashed_password=hash_password(admin_password),
        role=Role.admin,
    )
    db.add(admin)
    db.commit()
