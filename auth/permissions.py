
"""Define application roles and role-based permissions."""

from enum import Enum


class Role(str, Enum):
    """Represent an application role."""

    USER = "user"
    MANAGER = "manager"
    ADMIN = "admin"


USER_PERMISSIONS = frozenset({
    "agents:create",
    "agents:submit",
    "agents:use",
    "tool_requests:create",
    "tool_requests:read:own",
})

MANAGER_PERMISSIONS = USER_PERMISSIONS | frozenset({
    "agents:review",
    "tool_requests:review",
    "workflows:manage",
    "logs:read:team",
    "users:reset_password:assigned",
    "users:manage:regular",
})

ADMIN_PERMISSIONS = MANAGER_PERMISSIONS | frozenset({
    "users:manage",
    "roles:assign",
    "policies:manage",
    "logs:read:all",
})


ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.USER: USER_PERMISSIONS,
    Role.MANAGER: MANAGER_PERMISSIONS,
    Role.ADMIN: ADMIN_PERMISSIONS,
}


def has_permission(role: Role, permission: str) -> bool:
    """Check whether a role grants a permission.

    Args:
        role (Role): User's assigned application role.
        permission (str): Permission identifier to check.

    Returns:
        bool: Whether the role grants the permission.

    Raises:
        None.
    """
    return permission in ROLE_PERMISSIONS.get(
        role,
        frozenset(),
    )
