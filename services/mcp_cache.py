
"""Provide thread-safe in-memory TTL caching for MCP operation results."""

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """Represent a cached MCP operation result.

    Attributes:
        value (str): Cached operation result.
        expires_at (float): Expiration timestamp from monotonic time.

    Functions:
        None.
    """

    value: str
    expires_at: float


class MCPTTLCache:
    """Cache successful MCP operation results with expiration.

    Attributes:
        _entries (dict[str, CacheEntry]): Cached results by key.
        _agent_keys (dict[str, set[str]]): Keys associated with each agent.
        _agent_generations (dict[str, int]): Invalidation generation per agent.
        _lock (threading.RLock): Synchronization for cache access.

    Functions:
        build_key: Generate a deterministic version-aware cache key.
        get_generation: Return an agent's current invalidation generation.
        get: Retrieve a valid cached result.
        set: Store a result if its generation is still current.
        invalidate_agent: Invalidate entries and advance generation.
        clear: Remove all cached entries and invalidate pending writes.
    """

    def __init__(self) -> None:
        """Initialize the in-memory cache.

        Args:
            None.

        Returns:
            None: Initializes cache storage.

        Raises:
            None.
        """
        self._entries: dict[str, CacheEntry] = {}
        self._agent_keys: dict[str, set[str]] = {}
        self._agent_generations: dict[str, int] = {}
        self._lock = threading.RLock()

    def build_key(
        self,
        agent_id: str,
        operation: str,
        arguments: dict[str, Any],
        version: int = 1,
    ) -> str:
        """Build a deterministic version-aware cache key.

        Args:
            agent_id (str): Agent identifier.
            operation (str): MCP operation name.
            arguments (dict[str, Any]): Operation arguments.
            version (int): Agent configuration version.

        Returns:
            str: SHA-256 cache key.

        Raises:
            ValueError: If the version is invalid.
            TypeError: If arguments are not JSON serializable.
        """
        if version < 1:
            raise ValueError(
                "Agent version must be at least 1."
            )

        payload = {
            "agent_id": agent_id,
            "version": version,
            "operation": operation,
            "arguments": arguments,
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def get_generation(
        self,
        agent_id: str,
    ) -> int:
        """Return the current invalidation generation for an agent.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            int: Current invalidation generation.

        Raises:
            None.
        """
        with self._lock:
            return self._agent_generations.get(
                agent_id,
                0,
            )

    def get(
        self,
        key: str,
    ) -> tuple[bool, str | None]:
        """Retrieve a cached value if it has not expired.

        Args:
            key (str): Cache key.

        Returns:
            tuple[bool, str | None]: Cache-hit flag and cached
                value, or False and None on a miss.

        Raises:
            None.
        """
        with self._lock:
            entry = self._entries.get(key)

            if entry is None:
                return False, None

            if time.monotonic() >= entry.expires_at:
                self._entries.pop(key, None)
                return False, None

            return True, entry.value

    def set(
        self,
        agent_id: str,
        key: str,
        value: str,
        ttl_seconds: int,
        expected_generation: int | None = None,
    ) -> bool:
        """Store an MCP result only if its generation remains valid.

        Args:
            agent_id (str): Agent identifier.
            key (str): Cache key.
            value (str): Successful MCP operation result.
            ttl_seconds (int): Time to live in seconds.
            expected_generation (int | None): Generation captured
                before execution, or None for legacy writes.

        Returns:
            bool: True if stored, False if invalidated during execution.

        Raises:
            ValueError: If TTL is not positive.
        """
        if ttl_seconds <= 0:
            raise ValueError(
                "Cache TTL must be greater than zero."
            )

        with self._lock:
            current_generation = (
                self._agent_generations.get(
                    agent_id,
                    0,
                )
            )

            if (
                expected_generation is not None
                and expected_generation != current_generation
            ):
                return False

            self._entries[key] = CacheEntry(
                value=value,
                expires_at=time.monotonic() + ttl_seconds,
            )

            self._agent_keys.setdefault(
                agent_id,
                set(),
            ).add(key)

            return True

    def invalidate_agent(
        self,
        agent_id: str,
    ) -> None:
        """Invalidate cached entries and pending writes for an agent.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            None: Invalidates the agent's cached results.

        Raises:
            None.
        """
        with self._lock:
            self._agent_generations[agent_id] = (
                self._agent_generations.get(
                    agent_id,
                    0,
                ) + 1
            )

            keys = self._agent_keys.pop(
                agent_id,
                set(),
            )

            for key in keys:
                self._entries.pop(key, None)

    def clear(self) -> None:
        """Clear cached entries and invalidate pending writes.

        Args:
            None.

        Returns:
            None: Clears cache entries and advances generations.

        Raises:
            None.
        """
        with self._lock:
            for agent_id in self._agent_generations.keys() | self._agent_keys.keys():
                self._agent_generations[agent_id] = (
                    self._agent_generations.get(
                        agent_id,
                        0,
                    ) + 1
                )

            self._entries.clear()
            self._agent_keys.clear()


mcp_cache = MCPTTLCache()
