
"""Provision the predefined MCP Playground administrator."""

import os
import sqlite3

from auth.permissions import Role
from services.user_service import UserService


def bootstrap_admin() -> None:
    """Create the initial administrator if one does not exist.

    Args:
        None.

    Returns:
        None: Prints the provisioning result.

    Raises:
        ValueError: If administrator credentials are invalid.
        sqlite3.Error: If database operations fail.
    """
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    database_path = os.getenv("DATABASE_PATH", "data/agents.db")

    if not username or len(password) < 12:
        raise ValueError(
            "Set ADMIN_USERNAME and an ADMIN_PASSWORD "
            "containing at least 12 characters."
        )

    service = UserService(database_path)

    with service._connect() as connection:
        existing_admin = connection.execute(
            """
            SELECT id
            FROM users
            WHERE role = ?
            LIMIT 1
            """,
            (Role.ADMIN.value,),
        ).fetchone()

    if existing_admin is not None:
        print("Admin already exists. No changes made.")
        return

    admin = service.create_user(
        username=username,
        password=password,
        role=Role.ADMIN,
    )

    print(f"Admin account created: {admin.username}")


if __name__ == "__main__":
    bootstrap_admin()
