
"""Define protected regular-user management endpoints."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from auth.dependencies import (
    current_user,
    get_user_service,
)
from auth.permissions import Role, has_permission
from models.user import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    User,
)
from services.user_service import UserService


router = APIRouter(
    prefix="/api/management/users",
    tags=["User Management"],
)


def require_user_manager(
    actor: User = Depends(current_user),
) -> User:
    """Require permission to manage regular User accounts.

    Args:
        actor (User): Authenticated account.

    Returns:
        User: Authorized Admin or Manager.

    Raises:
        HTTPException: If permission is denied.
    """
    if not (
        has_permission(actor.role, "users:manage")
        or has_permission(actor.role, "users:manage:regular")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions.",
        )

    return actor


def get_regular_user(
    user_id: str,
    service: UserService,
) -> User:
    """Retrieve a regular User account.

    Args:
        user_id (str): Requested account identifier.
        service (UserService): Persistent user service.

    Returns:
        User: Matching regular User account.

    Raises:
        HTTPException: If the account is missing or privileged.
    """
    account = service.get_user(user_id)

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    if account.role != Role.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint manages regular Users only.",
        )

    return account


@router.get("", response_model=list[User])
def list_regular_users(
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> list[User]:
    """List regular User accounts.

    Args:
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        list[User]: Registered regular User accounts.

    Raises:
        HTTPException: If access is denied.
    """
    return service.list_users(role=Role.USER)


@router.post(
    "",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
def create_regular_user(
    request: CreateUserRequest,
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> User:
    """Create a regular User account.

    Args:
        request (CreateUserRequest): New account credentials.
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        User: Newly created regular User account.

    Raises:
        HTTPException: If the username already exists.
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


@router.get("/{user_id}", response_model=User)
def get_regular_user_details(
    user_id: str,
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> User:
    """Retrieve regular User account details.

    Args:
        user_id (str): Requested account identifier.
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        User: Account details without credentials.

    Raises:
        HTTPException: If the account cannot be accessed.
    """
    return get_regular_user(user_id, service)


@router.patch("/{user_id}", response_model=User)
def update_regular_user(
    user_id: str,
    request: UpdateUserRequest,
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> User:
    """Update a regular User account.

    Args:
        user_id (str): Account identifier.
        request (UpdateUserRequest): Requested changes.
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        User: Updated account.

    Raises:
        HTTPException: If the account is invalid or missing.
    """
    get_regular_user(user_id, service)

    try:
        updated = service.update_user(
            user_id=user_id,
            username=request.username,
            is_active=request.is_active,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )

    return updated


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_regular_user_password(
    user_id: str,
    request: ResetPasswordRequest,
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> None:
    """Reset a regular User account password.

    Args:
        user_id (str): Account identifier.
        request (ResetPasswordRequest): New password.
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        None: Password is replaced.

    Raises:
        HTTPException: If the account is invalid or missing.
    """
    get_regular_user(user_id, service)

    updated = service.reset_password(
        user_id,
        request.new_password,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_regular_user(
    user_id: str,
    actor: User = Depends(require_user_manager),
    service: UserService = Depends(get_user_service),
) -> None:
    """Delete a regular User account.

    Args:
        user_id (str): Account identifier.
        actor (User): Authorized Admin or Manager.
        service (UserService): Persistent user service.

    Returns:
        None: Account is deleted.

    Raises:
        HTTPException: If the account is invalid or missing.
    """
    get_regular_user(user_id, service)

    deleted = service.delete_user(user_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )
