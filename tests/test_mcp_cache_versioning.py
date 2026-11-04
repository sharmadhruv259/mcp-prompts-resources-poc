
"""Tests for MCP cache version isolation and invalidation safety."""

import asyncio
from unittest.mock import AsyncMock

import pytest

import agent as agent_module
from models.agent_config import AgentConfig
from services.mcp_cache import MCPTTLCache
from services.mcp_discovery import (
    MCPCapabilities,
    MCPResourceInfo,
)


def make_agent() -> AgentConfig:
    """Create an agent with MCP resource caching enabled.

    Args:
        None.

    Returns:
        AgentConfig: Agent with resource access and caching enabled.

    Raises:
        ValueError: If agent configuration is invalid.
    """
    return AgentConfig(
        id="versioned-agent",
        name="Versioned Agent",
        description="Tests version-aware MCP caching.",
        system_prompt="Use authorized MCP resources.",
        tool_access="all",
        allowed_resources=["project://architecture"],
        allowed_prompts=[],
        cache={
            "enabled": True,
            "ttl_seconds": 300,
        },
    )


def make_capabilities() -> MCPCapabilities:
    """Create MCP capabilities for cache tests.

    Args:
        None.

    Returns:
        MCPCapabilities: Available MCP architecture resource.

    Raises:
        ValueError: If capability validation fails.
    """
    return MCPCapabilities(
        tools=[],
        resources=[
            MCPResourceInfo(
                uri="project://architecture",
                name="Architecture",
            )
        ],
        prompts=[],
    )


def test_cache_keys_are_version_isolated() -> None:
    """Verify identical operations use different keys across versions.

    Args:
        None.

    Returns:
        None: Assertions verify cache-key isolation.

    Raises:
        AssertionError: If different versions share a key.
    """
    cache = MCPTTLCache()

    arguments = {
        "uri": "project://architecture",
    }

    key_v1 = cache.build_key(
        agent_id="versioned-agent",
        operation="read_mcp_resource",
        arguments=arguments,
        version=1,
    )

    key_v2 = cache.build_key(
        agent_id="versioned-agent",
        operation="read_mcp_resource",
        arguments=arguments,
        version=2,
    )

    assert key_v1 != key_v2


@pytest.mark.asyncio
async def test_agent_versions_do_not_share_cached_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify different agent versions execute independently.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify version-specific cache behavior.

    Raises:
        AssertionError: If a version reuses another version's result.
    """
    cache = MCPTTLCache()
    test_agent = make_agent()
    capabilities = make_capabilities()

    mock_execute = AsyncMock(
        side_effect=[
            "Architecture version 1",
            "Architecture version 2",
        ]
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        mock_execute,
    )

    arguments = {
        "uri": "project://architecture",
    }

    result_v1, hit_v1 = await agent_module.execute_agent_operation(
        client=None,
        agent=test_agent,
        capabilities=capabilities,
        function_name="read_mcp_resource",
        arguments=arguments,
        cache=cache,
        agent_version=1,
    )

    result_v2, hit_v2 = await agent_module.execute_agent_operation(
        client=None,
        agent=test_agent,
        capabilities=capabilities,
        function_name="read_mcp_resource",
        arguments=arguments,
        cache=cache,
        agent_version=2,
    )

    assert result_v1 == "Architecture version 1"
    assert result_v2 == "Architecture version 2"
    assert hit_v1 is False
    assert hit_v2 is False

    assert mock_execute.await_count == 2


@pytest.mark.asyncio
async def test_inflight_operation_cannot_restore_invalidated_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalidation prevents an older operation from caching.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify stale-write prevention.

    Raises:
        AssertionError: If an invalidated operation restores the cache.
    """
    cache = MCPTTLCache()
    test_agent = make_agent()
    capabilities = make_capabilities()

    started = asyncio.Event()
    resume = asyncio.Event()

    async def delayed_execute(**kwargs) -> str:
        """Simulate an MCP operation paused during execution.

        Args:
            **kwargs (Any): MCP operation arguments.

        Returns:
            str: Simulated resource content.

        Raises:
            None.
        """
        started.set()
        await resume.wait()
        return "Old architecture content"

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        delayed_execute,
    )

    arguments = {
        "uri": "project://architecture",
    }

    task = asyncio.create_task(
        agent_module.execute_agent_operation(
            client=None,
            agent=test_agent,
            capabilities=capabilities,
            function_name="read_mcp_resource",
            arguments=arguments,
            cache=cache,
            agent_version=1,
        )
    )

    await asyncio.wait_for(
        started.wait(),
        timeout=2,
    )

    cache.invalidate_agent(test_agent.id)

    resume.set()

    result, cache_hit = await asyncio.wait_for(
        task,
        timeout=2,
    )

    assert result == "Old architecture content"
    assert cache_hit is False

    old_key = cache.build_key(
        agent_id=test_agent.id,
        operation="read_mcp_resource",
        arguments=arguments,
        version=1,
    )

    hit, cached_result = cache.get(old_key)

    assert hit is False
    assert cached_result is None
