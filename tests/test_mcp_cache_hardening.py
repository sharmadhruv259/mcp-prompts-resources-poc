
"""Test MCP cache validation, hits, expiration, and failures."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import agent as agent_module
from models.agent_config import AgentConfig, CacheConfig
from services.mcp_cache import MCPTTLCache


def make_agent() -> AgentConfig:
    """Create an agent with caching and explicit MCP permissions.

    Args:
        None.

    Returns:
        AgentConfig: Valid agent configuration for cache tests.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id="hardening-agent",
        name="Hardening Agent",
        description="Test MCP caching.",
        system_prompt="Use MCP operations.",
        tool_access="all",
        allowed_resources=[
            "project://architecture",
        ],
        allowed_prompts=[
            "explain_technical",
        ],
        cache=CacheConfig(
            enabled=True,
            ttl_seconds=10,
        ),
    )

def make_capabilities() -> SimpleNamespace:
    """Create discovered MCP resource and prompt definitions.

    Args:
        None.

    Returns:
        SimpleNamespace: Mock MCP capabilities.

    Raises:
        None.
    """
    return SimpleNamespace(
        tools=[],
        resources=[
            SimpleNamespace(
                uri="project://architecture",
            ),
        ],
        prompts=[
            SimpleNamespace(
                name="explain_technical",
                arguments=[
                    SimpleNamespace(
                        name="topic",
                        required=True,
                    ),
                ],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_resource_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify repeated resource reads reuse cached results.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Returns:
        None: Assertions verify cache reuse.

    Raises:
        AssertionError: If caching fails.
    """
    dispatcher = AsyncMock(
        return_value="Architecture data"
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()

    kwargs = {
        "client": None,
        "agent": make_agent(),
        "capabilities": make_capabilities(),
        "function_name": "read_mcp_resource",
        "arguments": {
            "uri": "project://architecture",
        },
        "cache": cache,
    }

    first = await agent_module.execute_agent_operation(
        **kwargs
    )

    second = await agent_module.execute_agent_operation(
        **kwargs
    )

    assert first == ("Architecture data", False)
    assert second == ("Architecture data", True)
    assert dispatcher.await_count == 1


@pytest.mark.asyncio
async def test_expired_cache_executes_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify expired entries trigger another MCP execution.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Returns:
        None: Assertions verify cache expiration.

    Raises:
        AssertionError: If expired content is reused.
    """
    clock = {"now": 100.0}

    monkeypatch.setattr(
        "services.mcp_cache.time.monotonic",
        lambda: clock["now"],
    )

    dispatcher = AsyncMock(
        side_effect=[
            "First",
            "Second",
        ],
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()

    kwargs = {
        "client": None,
        "agent": make_agent(),
        "capabilities": make_capabilities(),
        "function_name": "read_mcp_resource",
        "arguments": {
            "uri": "project://architecture",
        },
        "cache": cache,
    }

    first = await agent_module.execute_agent_operation(
        **kwargs
    )

    clock["now"] = 111.0

    second = await agent_module.execute_agent_operation(
        **kwargs
    )

    assert first == ("First", False)
    assert second == ("Second", False)
    assert dispatcher.await_count == 2


@pytest.mark.asyncio
async def test_failed_operation_is_not_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify failed MCP executions are never cached.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Returns:
        None: Assertions verify failure handling.

    Raises:
        AssertionError: If a failure is cached.
    """
    dispatcher = AsyncMock(
        side_effect=[
            RuntimeError("MCP unavailable"),
            "Recovered",
        ],
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()

    kwargs = {
        "client": None,
        "agent": make_agent(),
        "capabilities": make_capabilities(),
        "function_name": "read_mcp_resource",
        "arguments": {
            "uri": "project://architecture",
        },
        "cache": cache,
    }

    with pytest.raises(
        RuntimeError,
        match="MCP unavailable",
    ):
        await agent_module.execute_agent_operation(
            **kwargs
        )

    result = await agent_module.execute_agent_operation(
        **kwargs
    )

    assert result == ("Recovered", False)
    assert dispatcher.await_count == 2


@pytest.mark.asyncio
async def test_invalid_prompt_cannot_use_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cached prompts still require valid arguments.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Returns:
        None: Assertions verify prompt validation.

    Raises:
        AssertionError: If invalid arguments are accepted.
    """
    dispatcher = AsyncMock(
        return_value="Prompt content"
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()
    agent = make_agent()
    capabilities = make_capabilities()

    valid_arguments = {
    "name": "explain_technical",
    "topic": "MCP",
}

    first = await agent_module.execute_agent_operation(
        client=None,
        agent=agent,
        capabilities=capabilities,
        function_name="get_mcp_prompt",
        arguments=valid_arguments,
        cache=cache,
    )

    assert first == ("Prompt content", False)

    # Simulate an MCP prompt schema change.
    # The previously cached request must now be rejected.
    capabilities.prompts[0].arguments = [
        SimpleNamespace(
            name="subject",
            required=True,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="Unknown prompt arguments",
    ):
        await agent_module.execute_agent_operation(
            client=None,
            agent=agent,
            capabilities=capabilities,
            function_name="get_mcp_prompt",
            arguments=valid_arguments,
            cache=cache,
        )

    assert dispatcher.await_count == 1


@pytest.mark.asyncio
async def test_prompt_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify repeated valid prompt requests use the cache.

    Args:
        monkeypatch (pytest.MonkeyPatch): Patching fixture.

    Returns:
        None: Assertions verify prompt caching.

    Raises:
        AssertionError: If prompt caching fails.
    """
    dispatcher = AsyncMock(
        return_value="Prompt content"
    )

    monkeypatch.setattr(
        agent_module,
        "execute_mcp_operation",
        dispatcher,
    )

    cache = MCPTTLCache()

    kwargs = {
        "client": None,
        "agent": make_agent(),
        "capabilities": make_capabilities(),
        "function_name": "get_mcp_prompt",
        "arguments": {
            "name": "explain_technical",
            "topic": "MCP",
        },
        "cache": cache,
    }

    first = await agent_module.execute_agent_operation(
        **kwargs
    )

    second = await agent_module.execute_agent_operation(
        **kwargs
    )

    assert first == ("Prompt content", False)
    assert second == ("Prompt content", True)
    assert dispatcher.await_count == 1
