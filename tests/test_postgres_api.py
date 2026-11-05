
"""Integration tests for FastAPI authentication and agent endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

import api as api_module
from auth.dependencies import get_user_service
from database.models import AgentModel, UserModel
from services.agent_registry import AgentRegistry
from services.user_service import UserService
from tests.postgres_test_db import get_test_session_factory


@pytest.fixture
def api_context(monkeypatch: pytest.MonkeyPatch):
    """Configure FastAPI services to use the Neon testing branch.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.

    Yields:
        dict: Test client, service, and temporary record identifiers.

    Raises:
        RuntimeError: If test database isolation is unsafe.
    """
    session_factory = get_test_session_factory()

    user_service = UserService(session_factory=session_factory)
    agent_registry = AgentRegistry(session_factory=session_factory)

    monkeypatch.setattr(
        api_module,
        "registry",
        agent_registry,
    )

    api_module.app.dependency_overrides[get_user_service] = (
        lambda: user_service
    )

    context = {
        "client": TestClient(api_module.app),
        "session_factory": session_factory,
        "user_ids": [],
        "agent_ids": [],
    }

    try:
        yield context
    finally:
        api_module.app.dependency_overrides.pop(
            get_user_service,
            None,
        )

        # Remove agents first because they reference user IDs.
        with session_factory.begin() as session:
            for agent_id in context["agent_ids"]:
                session.execute(
                    delete(AgentModel).where(
                        AgentModel.id == agent_id
                    )
                )

            for user_id in context["user_ids"]:
                session.execute(
                    delete(UserModel).where(
                        UserModel.id == user_id
                    )
                )

        context["client"].close()


def register_test_user(context: dict) -> dict:
    """Create a temporary user through the public signup endpoint.

    Args:
        context (dict): Isolated API test context.

    Returns:
        dict: Username, password, and registered user information.

    Raises:
        AssertionError: If user registration fails.
    """
    username = f"pg_api_{uuid4().hex[:12]}"
    password = "TestPassword123!"

    response = context["client"].post(
        "/api/auth/signup",
        json={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 201, response.text

    user = response.json()
    context["user_ids"].append(user["id"])

    return {
        "username": username,
        "password": password,
        "user": user,
    }


def login_test_user(context: dict, user: dict) -> str:
    """Authenticate a temporary user and return their access token.

    Args:
        context (dict): Isolated API test context.
        user (dict): Registered test user's credentials.

    Returns:
        str: JWT access token.

    Raises:
        AssertionError: If authentication fails.
    """
    response = context["client"].post(
        "/api/auth/login",
        json={
            "username": user["username"],
            "password": user["password"],
        },
    )

    assert response.status_code == 200, response.text

    token = response.json()["access_token"]

    assert isinstance(token, str)
    assert token

    return token


def auth_headers(token: str) -> dict[str, str]:
    """Construct JWT bearer authorization headers.

    Args:
        token (str): Valid JWT access token.

    Returns:
        dict[str, str]: Authorization header.

    Raises:
        None.
    """
    return {"Authorization": f"Bearer {token}"}


def make_test_agent() -> dict:
    """Build a minimal valid agent configuration for API testing.

    Args:
        None.

    Returns:
        dict: Agent configuration request payload.

    Raises:
        None.
    """
    return {
        "id": f"pg_agent_{uuid4().hex[:12]}",
        "name": "PostgreSQL API Test Agent",
        "description": "Temporary agent for API integration tests.",
        "system_prompt": "You are a helpful testing assistant.",
    }


def test_api_signup(api_context: dict) -> None:
    """Verify signup creates a user in PostgreSQL.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Signup assertions pass.

    Raises:
        AssertionError: If registration fails.
    """
    registered = register_test_user(api_context)
    user = registered["user"]

    assert user["username"] == registered["username"]
    assert user["role"] == "user"
    assert user["is_active"] is True
    assert "password_hash" not in user


def test_api_login_and_me(api_context: dict) -> None:
    """Verify login and authenticated profile retrieval.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Authentication assertions pass.

    Raises:
        AssertionError: If authentication behaves incorrectly.
    """
    registered = register_test_user(api_context)
    token = login_test_user(api_context, registered)

    response = api_context["client"].get(
        "/api/auth/me",
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == registered["user"]["id"]
    assert response.json()["username"] == registered["username"]


def test_api_invalid_login(api_context: dict) -> None:
    """Verify incorrect passwords are rejected.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Invalid login assertions pass.

    Raises:
        AssertionError: If invalid credentials are accepted.
    """
    registered = register_test_user(api_context)

    response = api_context["client"].post(
        "/api/auth/login",
        json={
            "username": registered["username"],
            "password": "IncorrectPassword123!",
        },
    )

    assert response.status_code == 401


def test_api_me_requires_authentication(api_context: dict) -> None:
    """Verify profile access requires a valid JWT.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Unauthorized access assertions pass.

    Raises:
        AssertionError: If unauthenticated access succeeds.
    """
    response = api_context["client"].get("/api/auth/me")

    assert response.status_code == 401

    invalid_response = api_context["client"].get(
        "/api/auth/me",
        headers=auth_headers("invalid.jwt.token"),
    )

    assert invalid_response.status_code == 401


def test_api_create_and_list_agent(api_context: dict) -> None:
    """Verify authenticated users can create and list their agents.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Agent creation and listing assertions pass.

    Raises:
        AssertionError: If agent API operations fail.
    """
    registered = register_test_user(api_context)
    token = login_test_user(api_context, registered)

    agent = make_test_agent()
    api_context["agent_ids"].append(agent["id"])

    response = api_context["client"].post(
        "/api/agents",
        json=agent,
        headers=auth_headers(token),
    )

    assert response.status_code == 201, response.text
    assert response.json()["id"] == agent["id"]

    list_response = api_context["client"].get(
        "/api/agents",
        headers=auth_headers(token),
    )

    assert list_response.status_code == 200, list_response.text
    assert any(
        item["id"] == agent["id"]
        for item in list_response.json()
    )

    record_response = api_context["client"].get(
        "/api/agents/records",
        headers=auth_headers(token),
    )

    assert record_response.status_code == 200
    assert any(
        record["configuration"]["id"] == agent["id"]
        and record["owner_id"] == registered["user"]["id"]
        for record in record_response.json()
    )


def test_api_agent_ownership(api_context: dict) -> None:
    """Verify users cannot access agents owned by other users.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Ownership restriction assertions pass.

    Raises:
        AssertionError: If unauthorized agent access succeeds.
    """
    owner = register_test_user(api_context)
    other_user = register_test_user(api_context)

    owner_token = login_test_user(api_context, owner)
    other_token = login_test_user(api_context, other_user)

    agent = make_test_agent()
    api_context["agent_ids"].append(agent["id"])

    create_response = api_context["client"].post(
        "/api/agents",
        json=agent,
        headers=auth_headers(owner_token),
    )

    assert create_response.status_code == 201, create_response.text

    owner_response = api_context["client"].get(
        f"/api/agents/{agent['id']}",
        headers=auth_headers(owner_token),
    )

    assert owner_response.status_code == 200

    other_response = api_context["client"].get(
        f"/api/agents/{agent['id']}",
        headers=auth_headers(other_token),
    )

    assert other_response.status_code == 404

    list_response = api_context["client"].get(
        "/api/agents",
        headers=auth_headers(other_token),
    )

    assert list_response.status_code == 200
    assert all(
        item["id"] != agent["id"]
        for item in list_response.json()
    )


def test_api_agent_requires_authentication(api_context: dict) -> None:
    """Verify agent creation and listing require authentication.

    Args:
        api_context (dict): Isolated API test context.

    Returns:
        None: Unauthorized request assertions pass.

    Raises:
        AssertionError: If an unauthenticated request succeeds.
    """
    list_response = api_context["client"].get("/api/agents")

    assert list_response.status_code == 401

    create_response = api_context["client"].post(
        "/api/agents",
        json=make_test_agent(),
    )

    assert create_response.status_code == 401
