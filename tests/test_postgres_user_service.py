
"""Integration tests for PostgreSQL-backed user management."""

from uuid import uuid4

import pytest

from auth.permissions import Role
from database.models import UserModel
from services.user_service import UserService
from tests.postgres_test_db import get_test_session_factory


@pytest.fixture
def user_service():
    """Provide a UserService connected to isolated PostgreSQL.

    Args:
        None.

    Returns:
        UserService: Service using the test session factory.

    Raises:
        RuntimeError: If the test database is not configured safely.
    """
    session_factory = get_test_session_factory()

    return UserService(session_factory=session_factory)


def test_user_lifecycle(user_service: UserService) -> None:
    """Verify account creation, authentication, updates, and deletion.

    Args:
        user_service (UserService): Isolated PostgreSQL user service.

    Returns:
        None: All lifecycle assertions pass.

    Raises:
        AssertionError: If a user operation behaves unexpectedly.
    """
    username = f"pg_test_{uuid4().hex[:12]}"
    original_password = f"Original_{uuid4().hex}!"
    new_password = f"Updated_{uuid4().hex}!"

    user_id = None

    try:
        # 1. Create a user.
        created = user_service.create_user(
            username=username,
            password=original_password,
            role=Role.USER,
        )

        user_id = created.id

        assert created.username == username
        assert created.role == Role.USER
        assert created.is_active is True

        # 2. Retrieve the user.
        retrieved = user_service.get_user(user_id)

        assert retrieved is not None
        assert retrieved.id == user_id

        # 3. Authenticate.
        authenticated = user_service.authenticate(
            username=username,
            password=original_password,
        )

        assert authenticated is not None
        assert authenticated.id == user_id

        # 4. Verify case-insensitive login.
        assert user_service.authenticate(
            username=username.upper(),
            password=original_password,
        ) is not None

        # 5. Reject incorrect password.
        assert user_service.authenticate(
            username=username,
            password="IncorrectPassword123!",
        ) is None

        # 6. Update username.
        updated_username = f"{username}_updated"

        updated = user_service.update_user(
            user_id=user_id,
            username=updated_username,
        )

        assert updated is not None
        assert updated.username == updated_username

        # 7. Deactivate the user.
        deactivated = user_service.update_user(
            user_id=user_id,
            is_active=False,
        )

        assert deactivated is not None
        assert deactivated.is_active is False

        assert user_service.authenticate(
            username=updated_username,
            password=original_password,
        ) is None

        # 8. Reactivate the user.
        reactivated = user_service.update_user(
            user_id=user_id,
            is_active=True,
        )

        assert reactivated is not None
        assert reactivated.is_active is True

        # 9. Reset password.
        assert user_service.reset_password(
            user_id=user_id,
            new_password=new_password,
        ) is True

        assert user_service.authenticate(
            username=updated_username,
            password=original_password,
        ) is None

        assert user_service.authenticate(
            username=updated_username,
            password=new_password,
        ) is not None

        # 10. Verify user listing.
        users = user_service.list_users(role=Role.USER)

        assert any(
            user.id == user_id
            for user in users
        )

    finally:
        # Always remove the temporary user.
        if user_id is not None:
            user_service.delete_user(user_id)

    # 11. Verify deletion.
    assert user_service.get_user(user_id) is None


def test_user_validation(user_service: UserService) -> None:
    """Verify invalid account inputs are rejected.

    Args:
        user_service (UserService): Isolated PostgreSQL user service.

    Returns:
        None: Invalid inputs are rejected.

    Raises:
        AssertionError: If validation unexpectedly succeeds.
    """
    with pytest.raises(ValueError):
        user_service.create_user(
            username="   ",
            password="ValidPassword123!",
        )

    with pytest.raises(ValueError):
        user_service.create_user(
            username="test_user",
            password="short",
        )


def test_missing_user_operations(user_service: UserService) -> None:
    """Verify operations on nonexistent accounts.

    Args:
        user_service (UserService): Isolated PostgreSQL user service.

    Returns:
        None: Missing accounts are handled correctly.

    Raises:
        AssertionError: If an operation returns an unexpected result.
    """
    missing_id = str(uuid4())

    assert user_service.get_user(missing_id) is None

    assert user_service.update_user(
        user_id=missing_id,
        username="missing_user",
    ) is None

    assert user_service.reset_password(
        user_id=missing_id,
        new_password="NewPassword123!",
    ) is False

    assert user_service.delete_user(missing_id) is False
