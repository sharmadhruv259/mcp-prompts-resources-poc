"""Regression tests for centralized registry-driven MCP cache invalidation."""

from pathlib import Path

import pytest

import services.agent_registry as registry_module
from models.agent_config import AgentConfig
from services.agent_registry import AgentRegistry
from services.mcp_cache import MCPTTLCache


@pytest.fixture
def registry_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide an isolated registry and its shared cache.

    Args:
        tmp_path (Path): Temporary directory for SQLite storage.
        monkeypatch (pytest.MonkeyPatch): Fixture for cache injection.

    Returns:
        tuple[AgentRegistry, MCPTTLCache]: Registry and isolated cache.

    Raises:
        None.
    """
    cache = MCPTTLCache()
    monkeypatch.setattr(registry_module, "mcp_cache", cache)
    registry = AgentRegistry(tmp_path / "agents.db")
    return registry, cache


@pytest.fixture
def agent_config() -> AgentConfig:
    """Build a valid saved-agent configuration.

    Args:
        None.

    Returns:
        AgentConfig: Test agent configuration.

    Raises:
        None.
    """
    return AgentConfig.model_validate({
        "id": "cache-regression-agent",
        "name": "Cache Regression Agent",
        "description": "Registry cache regression test.",
        "system_prompt": "Use MCP for answers.",
        "tool_access": "all",
        "allowed_tools": [],
        "allowed_resources": [],
        "allowed_prompts": [],
        "cache": {"enabled": True, "ttl_seconds": 300},
    })


def test_direct_registry_update_invalidates(registry_cache, agent_config):
    """Check that a registry update invalidates without API involvement.

    Args:
        registry_cache (tuple): Isolated registry and cache.
        agent_config (AgentConfig): Valid agent configuration.

    Returns:
        None: Assertions verify invalidation.

    Raises:
        AssertionError: If the stale entry remains.
    """
    registry, cache = registry_cache
    registry.create_agent(agent_config, owner_id="owner")
    cache.set(agent_config.id, "cached", "old", 300)
    assert registry.update_agent(agent_config.id, agent_config, "owner", 1) is not None
    assert cache.get("cached") == (False, None)


def test_failed_registry_mutations_preserve_cache(registry_cache, agent_config):
    """Check that rejected updates and deletes leave cache unchanged.

    Args:
        registry_cache (tuple): Isolated registry and cache.
        agent_config (AgentConfig): Valid agent configuration.

    Returns:
        None: Assertions verify cache preservation.

    Raises:
        AssertionError: If a failed mutation clears the cache.
    """
    registry, cache = registry_cache
    registry.create_agent(agent_config, owner_id="owner")
    cache.set(agent_config.id, "cached", "valid", 300)
    assert registry.update_agent(agent_config.id, agent_config, "owner", 99) is None
    assert registry.delete_agent(agent_config.id, owner_id="intruder") is False
    assert cache.get("cached") == (True, "valid")
    assert registry.get_agent_record(agent_config.id) is not None


def test_delete_recreate_does_not_reuse_cache(registry_cache, agent_config):
    """Check that deleting and recreating an ID removes old cached values.

    Args:
        registry_cache (tuple): Isolated registry and cache.
        agent_config (AgentConfig): Valid agent configuration.

    Returns:
        None: Assertions verify cache invalidation and recreation.

    Raises:
        AssertionError: If a deleted agent's cached value survives.
    """
    registry, cache = registry_cache
    registry.create_agent(agent_config, owner_id="owner")
    cache.set(agent_config.id, "cached", "old", 300)
    assert registry.delete_agent(agent_config.id, owner_id="owner") is True
    assert cache.get("cached") == (False, None)
    registry.create_agent(agent_config, owner_id="owner")
    assert cache.get("cached") == (False, None)
    assert registry.get_agent_record(agent_config.id)["approval_status"] == "draft"


def test_inflight_cache_write_rejected_after_invalidation(registry_cache, agent_config):
    """Check generation tracking prevents an outdated operation from writing.

    Args:
        registry_cache (tuple): Isolated registry and cache.
        agent_config (AgentConfig): Valid agent configuration.

    Returns:
        None: Assertions verify stale-write protection.

    Raises:
        AssertionError: If an outdated result is cached.
    """
    registry, cache = registry_cache
    registry.create_agent(agent_config, owner_id="owner")
    generation = cache.get_generation(agent_config.id)
    registry.update_agent(agent_config.id, agent_config, "owner", 1)
    cache.set(agent_config.id, "inflight", "stale", 300, expected_generation=generation)
    assert cache.get("inflight") == (False, None)
