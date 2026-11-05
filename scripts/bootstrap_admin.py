
"""Provision the predefined MCP Playground administrator in PostgreSQL."""

import os

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from auth.permissions import Role
from database.connection import SessionLocal
from database.models import UserModel
from services.user_service import UserService


def bootstrap_admin() -> None:
    """Create the initial administrator if one does not exist.

    Args:
        None.

    Returns:
        None: Prints the administrator provisioning result.

    Raises:
        ValueError: If administrator credentials are invalid.
        SQLAlchemyError: If PostgreSQL operations fail.
    """
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")

    if not username or not 12 <= len(password) <= 1024:
        raise ValueError(
            "Set ADMIN_USERNAME and an ADMIN_PASSWORD "
            "containing 12 to 1024 characters."
        )

    with SessionLocal() as session:
        existing_admin = session.scalar(
            select(UserModel).where(
                UserModel.role == Role.ADMIN.value
            ).limit(1)
        )

    if existing_admin is not None:
        print("Admin already exists. No changes made.")
        return

    service = UserService()

    admin = service.create_user(
        username=username,
        password=password,
        role=Role.ADMIN,
    )

    print(f"Admin account created: {admin.username}")


if __name__ == "__main__":
    bootstrap_admin()
