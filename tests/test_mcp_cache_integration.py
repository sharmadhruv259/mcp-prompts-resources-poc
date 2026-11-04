
"""Tests for cache-aware MCP operation execution."""

from unittest.mock import AsyncMock

import pytest

import agent as agent_module
from models.agent_config import AgentConfig, CacheConfig
from services.mcp_cache import MCPTTLCache
from services.mcp_discovery import (
    MCPCapabilities,
    MCPResourceInfo,
    MCPToolInfo,
)


def make_agent(
    cache_enabled: bool = True,
) -> AgentConfig:
    """Create a test agent with explicit MCP permissions.

    Args:
        cache_enabled (bool): Whether caching is enabled.

    Returns:
        AgentConfig: Valid test agent.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id="cache-test-agent",
        name="Cache Test Agent",
        description="Tests MCP caching.",
        system_prompt="Use MCP to answer questions.",
        tool_access="all",
        allowed_resources=["project://architecture"],
        cache=CacheConfig(
            enabled=cache_enabled,
            ttl_seconds=300,
        ),
    )


@pytest.fixture
def capabilities() -> MCPCapabilities:
    """Create discovered MCP capabilities for cache tests.

    Args:
        None.

    Returns:
        MCPCapabilities: Discovered test tool and resource.

    Raises:
        None.
    """
    return MCPCapabilities(
        tools=[
            MCPToolInfo(
                name="example",
                description="Example MCP tool.",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ],
        resources=[
            MCPResourceInfo(
                uri="project://architecture",
                name="Architecture",
            ),
        ],
        prompts=[],
    )

@pytest.mark.asyncio
async def test_native_tool_is_not_cached(
    monkeypatch,
    capabilities,
) -> None:
    """Verify native MCP tools always execute.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.
        capabilities (MCPCapabilities): Discovered capabilities.

    Returns:
        None: Assertions verify execution count.

    Raises:
        AssertionError: If a native tool result is cached.
    """
    dispatcher = AsyncMock(return_value="Tool result")

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()
    agent = make_agent()

    for _ in range(2):
        result, hit = await agent_module.execute_agent_operation(
            client=None,
            agent=agent,
            capabilities=capabilities,
            function_name="mcp_tool__example",
            arguments={},
            cache=cache,
        )

        assert result == "Tool result"
        assert hit is False

    assert dispatcher.await_count == 2


@pytest.mark.asyncio
async def test_cache_disabled_executes_every_time(
    monkeypatch,
    capabilities,
) -> None:
    """Verify disabled caching never reuses results.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.
        capabilities (MCPCapabilities): Discovered capabilities.

    Returns:
        None: Assertions verify execution count.

    Raises:
        AssertionError: If disabled caching reuses results.
    """
    dispatcher = AsyncMock(return_value="Fresh result")

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()
    agent = make_agent(cache_enabled=False)

    for _ in range(2):
        result, hit = await agent_module.execute_agent_operation(
            client=None,
            agent=agent,
            capabilities=capabilities,
            function_name="read_mcp_resource",
            arguments={"uri": "project://architecture"},
            cache=cache,
        )

        assert result == "Fresh result"
        assert hit is False

    assert dispatcher.await_count == 2


@pytest.mark.asyncio
async def test_unavailable_resource_is_not_cached(
    monkeypatch,
    capabilities,
) -> None:
    """Verify unavailable resources cannot be cached.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.
        capabilities (MCPCapabilities): Discovered capabilities.

    Returns:
        None: Assertions verify resource validation.

    Raises:
        AssertionError: If an unavailable resource is accepted.
    """
    dispatcher = AsyncMock(return_value="Result")

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    with pytest.raises(
        ValueError,
        match="Unknown MCP resource",
    ):
        await agent_module.execute_agent_operation(
            client=None,
            agent=make_agent(),
            capabilities=capabilities,
            function_name="read_mcp_resource",
            arguments={"uri": "project://missing"},
            cache=MCPTTLCache(),
        )

    dispatcher.assert_not_awaited()
