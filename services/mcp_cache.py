
"""Provide in-memory TTL caching for MCP operation results."""

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
        _lock (threading.RLock): Synchronization for cache access.

    Functions:
        build_key: Generate a deterministic operation cache key.
        get: Retrieve a valid cached result.
        set: Store a result with a TTL.
        invalidate_agent: Clear entries belonging to an agent.
        clear: Remove all cached entries.
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
        self._lock = threading.RLock()

    def build_key(
        self,
        agent_id: str,
        operation: str,
        arguments: dict[str, Any],
    ) -> str:
        """Build a deterministic cache key.

        Args:
            agent_id (str): Agent identifier.
            operation (str): MCP operation name.
            arguments (dict[str, Any]): Operation arguments.

        Returns:
            str: SHA-256 cache key.

        Raises:
            TypeError: If arguments are not JSON serializable.
        """
        payload = {
            "agent_id": agent_id,
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
    ) -> None:
        """Store an MCP result until its TTL expires.

        Args:
            agent_id (str): Agent identifier.
            key (str): Cache key.
            value (str): Successful MCP operation result.
            ttl_seconds (int): Time to live in seconds.

        Returns:
            None: Stores the cache entry.

        Raises:
            ValueError: If the TTL is not positive.
        """
        if ttl_seconds <= 0:
            raise ValueError(
                "Cache TTL must be greater than zero."
            )

        entry = CacheEntry(
            value=value,
            expires_at=time.monotonic() + ttl_seconds,
        )

        with self._lock:
            self._entries[key] = entry
            self._agent_keys.setdefault(
                agent_id,
                set(),
            ).add(key)

    def invalidate_agent(
        self,
        agent_id: str,
    ) -> None:
        """Remove all cached entries belonging to an agent.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            None: Removes the agent's cached entries.

        Raises:
            None.
        """
        with self._lock:
            keys = self._agent_keys.pop(
                agent_id,
                set(),
            )

            for key in keys:
                self._entries.pop(key, None)

    def clear(self) -> None:
        """Remove all cached entries.

        Args:
            None.

        Returns:
            None: Clears the cache.

        Raises:
            None.
        """
        with self._lock:
            self._entries.clear()
            self._agent_keys.clear()


mcp_cache = MCPTTLCache()
