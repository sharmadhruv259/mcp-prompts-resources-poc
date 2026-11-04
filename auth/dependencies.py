
"""Provide FastAPI authentication and authorization dependencies."""

import os
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt import InvalidTokenError

from auth.permissions import has_permission
from auth.tokens import verify_access_token
from models.user import User
from services.user_service import UserService


bearer_scheme = HTTPBearer(auto_error=False)


def get_user_service() -> UserService:
    """Initialize user storage using the configured database.

    Args:
        None.

    Returns:
        UserService: Initialized user storage service.

    Raises:
        OSError: If the database directory is inaccessible.
    """
    return UserService(
        os.getenv("DATABASE_PATH", "data/agents.db")
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    service: UserService = Depends(get_user_service),
) -> User:
    """Authenticate a user using their JWT bearer token.

    Args:
        credentials (HTTPAuthorizationCredentials | None):
            Bearer credentials from the request.
        service (UserService): User storage service.

    Returns:
        User: Authenticated and active user.

    Raises:
        HTTPException: If the token or account is invalid.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
    ):
        raise unauthorized

    try:
        user_id = verify_access_token(
            credentials.credentials
        )
    except InvalidTokenError as exc:
        raise unauthorized from exc

    user = service.get_user(user_id)

    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_permission(
    permission: str,
) -> Callable[..., User]:
    """Create a dependency that requires a role permission.

    Args:
        permission (str): Exact permission identifier.

    Returns:
        Callable[..., User]: FastAPI authorization dependency.

    Raises:
        HTTPException: When the user lacks permission.
    """

    def checker(
        user: User = Depends(current_user),
    ) -> User:
        """Check the authenticated user's permission.

        Args:
            user (User): Authenticated user.

        Returns:
            User: Authorized user.

        Raises:
            HTTPException: If permission is denied.
        """
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return user

    return checker
