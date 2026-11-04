
"""Expose administrator-only MCP tool management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth.dependencies import current_user
from auth.permissions import Role
from models.user import User
from models.tool_config import (
    CreateToolRequest,
    ToolRecord,
    ToolStatusRequest,
    UpdateToolRequest,
)
from services.tool_registry import tool_registry


router = APIRouter(
    prefix="/api/admin/tools",
    tags=["Tool Management"],
)


def require_admin(
    user: User = Depends(current_user),
) -> User:
    """Require an authenticated administrator.

    Args:
        user (User): Authenticated account.

    Returns:
        User: Authorized administrator.

    Raises:
        HTTPException: If the user is not an Admin.
    """
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )

    return user


@router.get("", response_model=list[ToolRecord])
def list_tools(
    admin: User = Depends(require_admin),
) -> list[ToolRecord]:
    """List all registered tools for an administrator.

    Args:
        admin (User): Authorized administrator.

    Returns:
        list[ToolRecord]: Non-deleted tool records.

    Raises:
        HTTPException: If authorization fails.
    """
    return tool_registry.list_tools()


@router.get("/{name}", response_model=ToolRecord)
def get_tool(
    name: str,
    admin: User = Depends(require_admin),
) -> ToolRecord:
    """Retrieve a registered tool.

    Args:
        name (str): Registered tool name.
        admin (User): Authorized administrator.

    Returns:
        ToolRecord: Matching tool configuration.

    Raises:
        HTTPException: If the tool is not found.
    """
    tool = tool_registry.get_tool(name)

    if tool is None:
        raise HTTPException(
            status_code=404,
            detail="Tool not found.",
        )

    return tool


@router.post(
    "",
    response_model=ToolRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_tool(
    request: CreateToolRequest,
    admin: User = Depends(require_admin),
) -> ToolRecord:
    """Register a tool using an approved backend handler.

    Args:
        request (CreateToolRequest): New tool configuration.
        admin (User): Authorized administrator.

    Returns:
        ToolRecord: Created tool configuration.

    Raises:
        HTTPException: If the handler or name is invalid.
    """
    try:
        return tool_registry.create_tool(
            name=request.name,
            description=request.description,
            handler=request.handler,
            kind=request.kind,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.patch("/{name}", response_model=ToolRecord)
def update_tool(
    name: str,
    request: UpdateToolRequest,
    admin: User = Depends(require_admin),
) -> ToolRecord:
    """Update a registered tool configuration.

    Args:
        name (str): Registered tool name.
        request (UpdateToolRequest): Requested changes.
        admin (User): Authorized administrator.

    Returns:
        ToolRecord: Updated tool.

    Raises:
        HTTPException: If the tool does not exist.
    """
    updated = tool_registry.update_tool(
        name=name,
        description=request.description,
        enabled=request.enabled,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Tool not found.",
        )

    return updated


@router.patch(
    "/{name}/status",
    response_model=ToolRecord,
)
def set_tool_status(
    name: str,
    request: ToolStatusRequest,
    admin: User = Depends(require_admin),
) -> ToolRecord:
    """Enable or disable a registered tool.

    Args:
        name (str): Registered tool name.
        request (ToolStatusRequest): Desired status.
        admin (User): Authorized administrator.

    Returns:
        ToolRecord: Updated tool configuration.

    Raises:
        HTTPException: If the tool does not exist.
    """
    updated = tool_registry.set_enabled(
        name=name,
        enabled=request.enabled,
    )

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="Tool not found.",
        )

    return updated


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_tool(
    name: str,
    admin: User = Depends(require_admin),
) -> Response:
    """Soft-delete a custom tool configuration.

    Args:
        name (str): Registered tool name.
        admin (User): Authorized administrator.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        HTTPException: If the tool is missing or built-in.
    """
    try:
        deleted = tool_registry.delete_tool(name)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Tool not found.",
        )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
