
"""Generate and validate JWT access tokens."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError


TOKEN_ALGORITHM = "HS256"
TOKEN_ISSUER = "mcp-playground"
TOKEN_AUDIENCE = "mcp-playground-api"
TOKEN_LIFETIME_SECONDS = 900


def get_jwt_secret() -> str:
    """Retrieve the JWT signing secret.

    Args:
        None.

    Returns:
        str: Configured JWT signing secret.

    Raises:
        RuntimeError: If the secret is missing or too short.
    """
    secret = os.getenv("AUTH_JWT_SECRET", "")

    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "AUTH_JWT_SECRET must contain at least 32 bytes."
        )

    return secret


def create_access_token(user_id: str) -> str:
    """Generate a signed JWT for a user.

    Args:
        user_id (str): Unique user identifier.

    Returns:
        str: Signed JWT access token.

    Raises:
        RuntimeError: If JWT configuration is invalid.
    """
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(
            seconds=TOKEN_LIFETIME_SECONDS
        ),
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=TOKEN_ALGORITHM,
    )


def verify_access_token(token: str) -> str:
    """Validate a JWT and return its user ID.

    Args:
        token (str): JWT access token.

    Returns:
        str: Authenticated user's ID.

    Raises:
        InvalidTokenError: If the JWT is invalid or expired.
        RuntimeError: If JWT configuration is invalid.
    """
    payload = jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[TOKEN_ALGORITHM],
        audience=TOKEN_AUDIENCE,
        issuer=TOKEN_ISSUER,
        options={
            "require": [
                "sub",
                "iss",
                "aud",
                "iat",
                "nbf",
                "exp",
            ],
        },
    )

    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id:
        raise InvalidTokenError(
            "Invalid token subject."
        )

    return user_id
