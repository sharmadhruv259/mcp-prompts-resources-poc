
"""Test cache invalidation during authenticated agent lifecycle operations."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import services.agent_registry as registry_module
import api
from auth.dependencies import current_user
from auth.permissions import Role
from services.agent_registry import AgentRegistry
from services.mcp_cache import MCPTTLCache


OWNER_ID = "cache-test-owner"


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Create an authenticated API client with isolated storage and cache.

    Args:
        tmp_path (Path): Temporary test directory.
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Yields:
        tuple[TestClient, MCPTTLCache]: API client and isolated cache.

    Raises:
        None.
    """
    registry = AgentRegistry(tmp_path / "agents.db")
    cache = MCPTTLCache()

    monkeypatch.setattr(api, "registry", registry)
    monkeypatch.setattr(registry_module, "mcp_cache", cache)

    test_user = SimpleNamespace(
        id=OWNER_ID,
        role=Role.USER,
    )

    api.app.dependency_overrides[current_user] = (
        lambda: test_user
    )

    try:
        with TestClient(api.app) as test_client:
            yield test_client, cache
    finally:
        api.app.dependency_overrides.pop(
            current_user,
            None,
        )


@pytest.fixture
def payload() -> dict:
    """Build a valid agent configuration.

    Args:
        None.

    Returns:
        dict: Agent configuration payload.

    Raises:
        None.
    """
    return {
        "id": "cache-agent",
        "name": "Cache Agent",
        "description": "Agent cache testing.",
        "system_prompt": "Use MCP for answers.",
        "tool_access": "all",
        "allowed_tools": [],
        "allowed_resources": [],
        "allowed_prompts": [],
        "cache": {
            "enabled": True,
            "ttl_seconds": 300,
        },
    }


def test_create_invalidates_old_cache(
    client,
    payload,
) -> None:
    """Verify cache invalidation after agent creation.

    Args:
        client (tuple): Authenticated API client and cache.
        payload (dict): Agent configuration.

    Returns:
        None: Assertions verify invalidation.

    Raises:
        AssertionError: If stale data remains.
    """
    test_client, cache = client

    cache.set(
        "cache-agent",
        "key",
        "old",
        300,
    )

    response = test_client.post(
        "/api/agents",
        json=payload,
    )

    assert response.status_code == 201
    assert cache.get("key") == (False, None)


def test_update_invalidates_cache(
    client,
    payload,
) -> None:
    """Verify cache invalidation after agent updates.

    Args:
        client (tuple): Authenticated API client and cache.
        payload (dict): Agent configuration.

    Returns:
        None: Assertions verify invalidation.

    Raises:
        AssertionError: If stale data remains.
    """
    test_client, cache = client

    created = test_client.post(
        "/api/agents",
        json=payload,
    )

    assert created.status_code == 201

    cache.set(
        "cache-agent",
        "key",
        "old",
        300,
    )

    updated = {
        **payload,
        "system_prompt": "Updated instructions.",
    }

    response = test_client.put(
        "/api/agents/cache-agent",
        json={
            "agent": updated,
            "expected_version": 1,
        },
    )

    assert response.status_code == 200
    assert cache.get("key") == (False, None)

    record = api.registry.get_agent_record(
        "cache-agent"
    )

    assert record is not None
    assert record["version"] == 2
    assert record["approval_status"] == "draft"


def test_delete_invalidates_cache(
    client,
    payload,
) -> None:
    """Verify cache invalidation after agent deletion.

    Args:
        client (tuple): Authenticated API client and cache.
        payload (dict): Agent configuration.

    Returns:
        None: Assertions verify invalidation.

    Raises:
        AssertionError: If stale data remains.
    """
    test_client, cache = client

    created = test_client.post(
        "/api/agents",
        json=payload,
    )

    assert created.status_code == 201

    cache.set(
        "cache-agent",
        "key",
        "old",
        300,
    )

    response = test_client.delete(
        "/api/agents/cache-agent"
    )

    assert response.status_code == 204
    assert cache.get("key") == (False, None)


def test_stale_update_does_not_invalidate_cache(
    client,
    payload,
) -> None:
    """Verify a rejected stale update does not invalidate cached data.

    Args:
        client (tuple): Authenticated API client and cache.
        payload (dict): Agent configuration.

    Returns:
        None: Assertions verify unsuccessful updates preserve cache state.

    Raises:
        AssertionError: If a rejected update invalidates the cache.
    """
    test_client, cache = client

    created = test_client.post(
        "/api/agents",
        json=payload,
    )

    assert created.status_code == 201

    first_update = test_client.put(
        "/api/agents/cache-agent",
        json={
            "agent": {
                **payload,
                "name": "Version Two",
            },
            "expected_version": 1,
        },
    )

    assert first_update.status_code == 200

    cache.set(
        "cache-agent",
        "key",
        "current",
        300,
    )

    stale_update = test_client.put(
        "/api/agents/cache-agent",
        json={
            "agent": {
                **payload,
                "name": "Stale Version",
            },
            "expected_version": 1,
        },
    )

    assert stale_update.status_code == 409
    assert cache.get("key") == (True, "current")
