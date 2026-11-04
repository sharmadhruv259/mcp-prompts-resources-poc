
"""Provision the initial MCP Playground administrator."""

import os
import sqlite3

from auth.permissions import Role
from services.user_service import UserService


def bootstrap_admin() -> None:
    """Initialize the administrator account for the application.

    Args:
        None.

    Returns:
        None: Creates or optionally resets the Admin account.

    Raises:
        ValueError: If Admin credentials are invalid.
        sqlite3.Error: If database operations fail.
    """
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    database_path = os.getenv("DATABASE_PATH", "data/agents.db")

    reset_password = (
        os.getenv("RESET_ADMIN_PASSWORD", "false").lower() == "true"
    )

    if not username or not 12 <= len(password) <= 1024:
        raise ValueError(
            "Set ADMIN_USERNAME and an ADMIN_PASSWORD "
            "containing 12 to 1024 characters."
        )

    service = UserService(database_path)
    admins = service.list_users(role=Role.ADMIN)

    if not admins:
        admin = service.create_user(
            username=username,
            password=password,
            role=Role.ADMIN,
        )
        print(f"Admin account created: {admin.username}")
        return

    admin = next(
        (
            user
            for user in admins
            if user.username.casefold() == username.casefold()
        ),
        None,
    )

    if admin is None:
        raise ValueError(
            "An Admin account already exists with a different username. "
            "Existing Admin credentials were not changed."
        )

    if reset_password:
        if not admin.is_active:
            raise ValueError(
                "Admin account is inactive. Password was not changed."
            )

        if service.reset_password(admin.id, password):
            print("Admin password reset successfully.")
        else:
            raise RuntimeError("Admin password reset failed.")
    else:
        print("Admin already exists. No changes made.")


if __name__ == "__main__":
    bootstrap_admin()
