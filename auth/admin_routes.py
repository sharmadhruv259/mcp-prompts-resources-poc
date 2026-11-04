
"""Define administrator-only account management endpoints."""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)

from auth.dependencies import (
    get_user_service,
    require_permission,
)
from auth.permissions import Role
from models.user import (
    CreateManagerRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    User,
)
from services.user_service import UserService


router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
)


def get_manager_or_404(
    manager_id: str,
    service: UserService,
) -> User:
    """Retrieve a Manager account and validate its role.

    Args:
        manager_id (str): Identifier of the Manager account.
        service (UserService): Persistent user service.

    Returns:
        User: Matching Manager account.

    Raises:
        HTTPException: If the account does not exist or is not
            a Manager account.
    """
    manager = service.get_user(manager_id)

    if manager is None or manager.role != Role.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found.",
        )

    return manager


@router.get(
    "/users",
    response_model=list[User],
)
def list_accounts(
    role: Role | None = None,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> list[User]:
    """List platform accounts with an optional role filter.

    Args:
        role (Role | None): Optional role filter.
        admin (User): Authenticated administrator.
        service (UserService): Persistent user service.

    Returns:
        list[User]: Matching accounts.

    Raises:
        HTTPException: If the caller lacks permission.
    """
    return service.list_users(role=role)


@router.post(
    "/managers",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
)
def create_manager(
    request: CreateManagerRequest,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> User:
    """Create a Manager account as an authenticated Admin.

    Args:
        request (CreateManagerRequest): Manager credentials.
        admin (User): Authorized administrator.
        service (UserService): Persistent user service.

    Returns:
        User: Newly created Manager profile.

    Raises:
        HTTPException: If the username exists or input is invalid.
    """
    try:
        return service.create_user(
            username=request.username,
            password=request.password,
            role=Role.MANAGER,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get(
    "/managers/{manager_id}",
    response_model=User,
)
def get_manager(
    manager_id: str,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> User:
    """Retrieve an existing Manager account.

    Args:
        manager_id (str): Identifier of the Manager.
        admin (User): Authorized administrator.
        service (UserService): Persistent user service.

    Returns:
        User: Manager account details.

    Raises:
        HTTPException: If access is denied or Manager is missing.
    """
    return get_manager_or_404(manager_id, service)


@router.patch(
    "/managers/{manager_id}",
    response_model=User,
)
def update_manager(
    manager_id: str,
    request: UpdateUserRequest,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> User:
    """Update a Manager username or activation status.

    Args:
        manager_id (str): Identifier of the Manager.
        request (UpdateUserRequest): Requested account changes.
        admin (User): Authorized administrator.
        service (UserService): Persistent user service.

    Returns:
        User: Updated Manager profile.

    Raises:
        HTTPException: If the Manager is missing or the
            username conflicts with another account.
    """
    get_manager_or_404(manager_id, service)

    try:
        updated = service.update_user(
            user_id=manager_id,
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
            detail="Manager not found.",
        )

    return updated


@router.post(
    "/managers/{manager_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
)
def reset_manager_password(
    manager_id: str,
    request: ResetPasswordRequest,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> Response:
    """Reset an existing Manager account password.

    Args:
        manager_id (str): Identifier of the Manager.
        request (ResetPasswordRequest): Replacement password.
        admin (User): Authorized administrator.
        service (UserService): Persistent user service.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        HTTPException: If the Manager is missing or password
            validation fails.
    """
    get_manager_or_404(manager_id, service)

    try:
        updated = service.reset_password(
            user_id=manager_id,
            new_password=request.new_password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.delete(
    "/managers/{manager_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_manager(
    manager_id: str,
    admin: User = Depends(
        require_permission("users:manage")
    ),
    service: UserService = Depends(get_user_service),
) -> Response:
    """Delete a Manager account.

    Args:
        manager_id (str): Identifier of the Manager.
        admin (User): Authorized administrator.
        service (UserService): Persistent user service.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        HTTPException: If the Manager is missing or deletion fails.
    """
    get_manager_or_404(manager_id, service)

    deleted = service.delete_user(
        user_id=manager_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
