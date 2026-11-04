
"""Define user identity and authentication API models."""

from pydantic import BaseModel, ConfigDict, Field

from auth.permissions import Role


class User(BaseModel):
    """Represent a public application user.

    Attributes:
        id (str): Unique user identifier.
        username (str): Unique login username.
        role (Role): Assigned application role.
        is_active (bool): Whether the account is active.

    Functions:
        None.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    username: str
    role: Role
    is_active: bool


class LoginRequest(BaseModel):
    """Represent credentials submitted during login.

    Attributes:
        username (str): Submitted username.
        password (str): Submitted plaintext password.

    Functions:
        None.
    """

    username: str = Field(
        min_length=1,
        max_length=150,
    )
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Represent a successful authentication response.

    Attributes:
        access_token (str): Signed JWT access token.
        token_type (str): Authentication scheme.
        expires_in (int): Token lifetime in seconds.

    Functions:
        None.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupRequest(BaseModel):
    """Represent credentials for public user registration.

    Attributes:
        username (str): Unique username for the new account.
        password (str): Password containing at least 12 characters.
    """

    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=1,
        max_length=150,
    )
    password: str = Field(
        min_length=12,
        max_length=1024,
    )


class CreateManagerRequest(BaseModel):
    """Represent a manager account creation request.

    Attributes:
        username (str): Unique manager username.
        password (str): Manager password.
    """

    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=1,
        max_length=150,
    )
    password: str = Field(
        min_length=12,
        max_length=1024,
    )

class CreateUserRequest(BaseModel):
    """Represent a regular User account creation request.

    Attributes:
        username (str): Unique account username.
        password (str): Initial account password.
    """

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=12, max_length=1024)


class UpdateUserRequest(BaseModel):
    """Represent changes to an existing account.

    Attributes:
        username (str | None): Replacement username.
        is_active (bool | None): Replacement account status.
    """

    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    """Represent an administrator-initiated password reset.

    Attributes:
        new_password (str): Replacement account password.
    """

    model_config = ConfigDict(extra="forbid")

    new_password: str = Field(
        min_length=12,
        max_length=1024,
    )
