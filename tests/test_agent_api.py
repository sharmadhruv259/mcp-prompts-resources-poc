
"""Tests for authenticated custom agent management API endpoints."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import api
from auth.dependencies import current_user
from auth.permissions import Role
from services.agent_registry import AgentRegistry


OWNER_ID = "test-owner-1"
OTHER_USER_ID = "test-owner-2"


@pytest.fixture
def authenticated_user() -> SimpleNamespace:
    """Create an authenticated test user.

    Args:
        None.

    Returns:
        SimpleNamespace: Test user with ID and role.

    Raises:
        None.
    """
    return SimpleNamespace(
        id=OWNER_ID,
        role=Role.USER,
    )


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authenticated_user: SimpleNamespace,
):
    """Create an authenticated API client with isolated storage.

    Args:
        tmp_path (Path): Temporary test directory.
        monkeypatch (pytest.MonkeyPatch): Patching utility.
        authenticated_user (SimpleNamespace): Test identity.

    Yields:
        TestClient: Isolated authenticated test client.

    Raises:
        None.
    """
    test_registry = AgentRegistry(
        tmp_path / "test_agents.db"
    )

    monkeypatch.setattr(
        api,
        "registry",
        test_registry,
    )

    api.app.dependency_overrides[current_user] = (
        lambda: authenticated_user
    )

    try:
        with TestClient(api.app) as test_client:
            yield test_client
    finally:
        api.app.dependency_overrides.pop(
            current_user,
            None,
        )


@pytest.fixture
def agent_payload() -> dict:
    """Create a valid agent payload.

    Args:
        None.

    Returns:
        dict: Agent configuration data.

    Raises:
        None.
    """
    return {
        "id": "test-agent",
        "name": "Test Agent",
        "description": "A test custom agent.",
        "system_prompt": "Answer using MCP.",
        "tool_access": "all",
        "allowed_tools": [],
        "allowed_resources": [],
        "allowed_prompts": [],
        "cache": {
            "enabled": False,
            "ttl_seconds": 300,
        },
    }


def make_update_payload(
    agent: dict,
    expected_version: int = 1,
) -> dict:
    """Build a version-controlled agent update request.

    Args:
        agent (dict): Replacement agent configuration.
        expected_version (int): Expected configuration version.

    Returns:
        dict: API update request body.

    Raises:
        None.
    """
    return {
        "agent": agent,
        "expected_version": expected_version,
    }


def test_create_agent(client, agent_payload) -> None:
    """Verify an authenticated user can create an agent.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.

    Returns:
        None: Assertions verify creation.

    Raises:
        AssertionError: If creation fails.
    """
    response = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert response.status_code == 201
    assert response.json()["id"] == "test-agent"

    record = api.registry.get_agent_record("test-agent")

    assert record is not None
    assert record["owner_id"] == OWNER_ID
    assert record["approval_status"] == "draft"
    assert record["version"] == 1


def test_list_agents(client, agent_payload) -> None:
    """Verify an owner can list their agents.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.

    Returns:
        None: Assertions verify listing.

    Raises:
        AssertionError: If listing fails.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    response = client.get("/api/agents")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "test-agent"


def test_get_agent(client, agent_payload) -> None:
    """Verify an owner can retrieve their agent.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.

    Returns:
        None: Assertions verify retrieval.

    Raises:
        AssertionError: If retrieval fails.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    response = client.get(
        "/api/agents/test-agent"
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Test Agent"


def test_update_agent(client, agent_payload) -> None:
    """Verify an owner can update an agent using its version.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Original agent configuration.

    Returns:
        None: Assertions verify the update.

    Raises:
        AssertionError: If updating fails.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    updated_agent = {
        **agent_payload,
        "name": "Updated Agent",
    }

    response = client.put(
        "/api/agents/test-agent",
        json=make_update_payload(
            updated_agent,
            expected_version=1,
        ),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Agent"

    record = api.registry.get_agent_record("test-agent")

    assert record is not None
    assert record["version"] == 2
    assert record["approval_status"] == "draft"


def test_delete_agent(client, agent_payload) -> None:
    """Verify an owner can delete their agent.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.

    Returns:
        None: Assertions verify deletion.

    Raises:
        AssertionError: If deletion fails.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    response = client.delete(
        "/api/agents/test-agent"
    )

    assert response.status_code == 204

    missing = client.get(
        "/api/agents/test-agent"
    )

    assert missing.status_code == 404


def test_reject_duplicate_agent(
    client,
    agent_payload,
) -> None:
    """Verify duplicate agent identifiers return HTTP 409.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.

    Returns:
        None: Assertions verify conflict handling.

    Raises:
        AssertionError: If duplicates are accepted.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    response = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert response.status_code == 409


def test_reject_agent_id_change(
    client,
    agent_payload,
) -> None:
    """Verify that an agent's identifier cannot change.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Original agent configuration.

    Returns:
        None: Assertions verify ID immutability.

    Raises:
        AssertionError: If ID changes are accepted.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    updated_agent = {
        **agent_payload,
        "id": "different-agent",
    }

    response = client.put(
        "/api/agents/test-agent",
        json=make_update_payload(updated_agent),
    )

    assert response.status_code == 422


def test_missing_agent_returns_404(client) -> None:
    """Verify missing agents return HTTP 404.

    Args:
        client (TestClient): Authenticated test client.

    Returns:
        None: Assertions verify missing-agent handling.

    Raises:
        AssertionError: If missing agents are mishandled.
    """
    response = client.get(
        "/api/agents/unknown-agent"
    )

    assert response.status_code == 404


def test_stale_update_returns_409(
    client,
    agent_payload,
) -> None:
    """Verify stale updates are rejected with HTTP 409.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Original agent configuration.

    Returns:
        None: Assertions verify version conflict handling.

    Raises:
        AssertionError: If stale updates succeed.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    first_update = {
        **agent_payload,
        "name": "Version Two",
    }

    successful = client.put(
        "/api/agents/test-agent",
        json=make_update_payload(
            first_update,
            expected_version=1,
        ),
    )

    assert successful.status_code == 200

    stale_update = {
        **agent_payload,
        "name": "Stale Update",
    }

    response = client.put(
        "/api/agents/test-agent",
        json=make_update_payload(
            stale_update,
            expected_version=1,
        ),
    )

    assert response.status_code == 409

    record = api.registry.get_agent_record("test-agent")

    assert record is not None
    assert record["version"] == 2
    assert record["configuration"].name == "Version Two"


def test_other_user_cannot_access_agent(
    client,
    agent_payload,
    authenticated_user,
) -> None:
    """Verify that another user cannot access an owned agent.

    Args:
        client (TestClient): Authenticated test client.
        agent_payload (dict): Agent configuration.
        authenticated_user (SimpleNamespace): Mutable test identity.

    Returns:
        None: Assertions verify ownership isolation.

    Raises:
        AssertionError: If another user gains access.
    """
    created = client.post(
        "/api/agents",
        json=agent_payload,
    )

    assert created.status_code == 201

    authenticated_user.id = OTHER_USER_ID

    response = client.get(
        "/api/agents/test-agent"
    )

    assert response.status_code == 404

    update_response = client.put(
        "/api/agents/test-agent",
        json=make_update_payload(
            {
                **agent_payload,
                "name": "Unauthorized Change",
            }
        ),
    )

    assert update_response.status_code == 404

    delete_response = client.delete(
        "/api/agents/test-agent"
    )

    assert delete_response.status_code == 404

    record = api.registry.get_agent_record("test-agent")

    assert record is not None
    assert record["owner_id"] == OWNER_ID
    assert record["configuration"].name == "Test Agent"


def test_unauthenticated_request_returns_401(
    client,
) -> None:
    """Verify that agent management requires authentication.

    Args:
        client (TestClient): Isolated API client.

    Returns:
        None: Assertions verify authentication enforcement.

    Raises:
        AssertionError: If anonymous access is permitted.
    """
    override = api.app.dependency_overrides.pop(
        current_user
    )

    try:
        response = client.get("/api/agents")

        assert response.status_code == 401
    finally:
        api.app.dependency_overrides[current_user] = override
