
"""Unit tests for the MCP TTL cache."""

import pytest

from services.mcp_cache import MCPTTLCache


@pytest.fixture
def cache() -> MCPTTLCache:
    """Create an isolated MCP cache.

    Args:
        None.

    Returns:
        MCPTTLCache: Empty test cache.

    Raises:
        None.
    """
    return MCPTTLCache()


def test_cache_miss(cache: MCPTTLCache) -> None:
    """Verify that an unknown key returns a cache miss.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify the result.

    Raises:
        AssertionError: If a miss is not returned.
    """
    hit, value = cache.get("unknown")

    assert hit is False
    assert value is None


def test_cache_hit(cache: MCPTTLCache) -> None:
    """Verify that a stored result can be retrieved.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify retrieval.

    Raises:
        AssertionError: If retrieval fails.
    """
    key = cache.build_key(
        "agent-1",
        "read_mcp_resource",
        {"uri": "project://architecture"},
    )

    cache.set(
        agent_id="agent-1",
        key=key,
        value="Architecture details",
        ttl_seconds=300,
    )

    hit, value = cache.get(key)

    assert hit is True
    assert value == "Architecture details"


def test_cache_key_is_deterministic(
    cache: MCPTTLCache,
) -> None:
    """Verify that argument ordering does not change the key.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify key stability.

    Raises:
        AssertionError: If equivalent inputs produce different keys.
    """
    first = cache.build_key(
        "agent-1",
        "get_mcp_prompt",
        {"name": "example", "arguments": {"a": 1, "b": 2}},
    )

    second = cache.build_key(
        "agent-1",
        "get_mcp_prompt",
        {"arguments": {"b": 2, "a": 1}, "name": "example"},
    )

    assert first == second


def test_cache_keys_isolate_agents(
    cache: MCPTTLCache,
) -> None:
    """Verify that different agents use different cache keys.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify agent isolation.

    Raises:
        AssertionError: If agent keys collide.
    """
    arguments = {"uri": "project://requirements"}

    first = cache.build_key(
        "agent-1",
        "read_mcp_resource",
        arguments,
    )

    second = cache.build_key(
        "agent-2",
        "read_mcp_resource",
        arguments,
    )

    assert first != second


def test_cache_expiration(
    cache: MCPTTLCache,
    monkeypatch,
) -> None:
    """Verify that entries expire after their TTL.

    Args:
        cache (MCPTTLCache): Test cache.
        monkeypatch (pytest.MonkeyPatch): Time patching utility.

    Returns:
        None: Assertions verify expiration.

    Raises:
        AssertionError: If expired entries remain accessible.
    """
    clock = {"now": 100.0}

    monkeypatch.setattr(
        "services.mcp_cache.time.monotonic",
        lambda: clock["now"],
    )

    cache.set(
        agent_id="agent-1",
        key="test-key",
        value="Cached result",
        ttl_seconds=10,
    )

    clock["now"] = 109.0

    assert cache.get("test-key") == (
        True,
        "Cached result",
    )

    clock["now"] = 110.0

    assert cache.get("test-key") == (
        False,
        None,
    )


def test_invalidate_agent(
    cache: MCPTTLCache,
) -> None:
    """Verify that invalidation affects only one agent.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify selective invalidation.

    Raises:
        AssertionError: If unrelated entries are removed.
    """
    cache.set(
        "agent-1",
        "key-1",
        "Result 1",
        300,
    )

    cache.set(
        "agent-2",
        "key-2",
        "Result 2",
        300,
    )

    cache.invalidate_agent("agent-1")

    assert cache.get("key-1") == (False, None)
    assert cache.get("key-2") == (True, "Result 2")


def test_clear_cache(
    cache: MCPTTLCache,
) -> None:
    """Verify that clearing removes all entries.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify clearing.

    Raises:
        AssertionError: If entries remain.
    """
    cache.set("agent-1", "key-1", "Value", 300)

    cache.clear()

    assert cache.get("key-1") == (False, None)


def test_reject_invalid_ttl(
    cache: MCPTTLCache,
) -> None:
    """Verify that nonpositive TTL values are rejected.

    Args:
        cache (MCPTTLCache): Test cache.

    Returns:
        None: Assertions verify TTL validation.

    Raises:
        AssertionError: If invalid TTL values are accepted.
    """
    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        cache.set(
            agent_id="agent-1",
            key="key-1",
            value="Result",
            ttl_seconds=0,
        )
