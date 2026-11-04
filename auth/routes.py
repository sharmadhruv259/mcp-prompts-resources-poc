
"""Define authentication endpoints for the MCP Playground."""
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from auth.dependencies import (
    current_user,
    get_user_service,
)
from auth.tokens import (
    TOKEN_LIFETIME_SECONDS,
    create_access_token,
)
from models.user import (
    LoginRequest,
    TokenResponse,
    User,
)
from services.user_service import UserService

from auth.permissions import Role
from models.user import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    User,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    """Authenticate a user and issue a JWT access token.

    Args:
        request (LoginRequest): Submitted login credentials.
        service (UserService): User database service.

    Returns:
        TokenResponse: JWT access token and expiry.

    Raises:
        HTTPException: If the credentials are invalid.
    """
    user = service.authenticate(
        username=request.username,
        password=request.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=TOKEN_LIFETIME_SECONDS,
    )


@router.post(
    "/signup",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
def signup(
    request: SignupRequest,
    service: UserService = Depends(get_user_service),
) -> User:
    """Register a new account with the regular User role.

    Args:
        request (SignupRequest): Submitted registration credentials.
        service (UserService): User database service.

    Returns:
        User: Newly registered public user profile.

    Raises:
        HTTPException: If registration input is invalid,
            the username exists, or persistence fails.
    """
    try:
        return service.create_user(
            username=request.username,
            password=request.password,
            role=Role.USER,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register user.",
        ) from exc

@router.get(
    "/me",
    response_model=User,
)
def get_me(
    user: User = Depends(current_user),
) -> User:
    """Retrieve the authenticated user's profile.

    Args:
        user (User): Authenticated user from JWT.

    Returns:
        User: Public user profile.

    Raises:
        HTTPException: If authentication fails.
    """
    return user
