
"""Unit tests for the SQLite custom agent registry."""

from pathlib import Path

import pytest

from models.agent_config import AgentConfig, CacheConfig
from services.agent_registry import AgentRegistry


OWNER_ID = "user-1"
OTHER_USER_ID = "user-2"
REVIEWER_ID = "manager-1"


@pytest.fixture
def registry(tmp_path: Path) -> AgentRegistry:
    """Create an isolated test agent registry.

    Args:
        tmp_path (Path): Pytest temporary directory.

    Returns:
        AgentRegistry: Registry backed by a temporary database.

    Raises:
        sqlite3.Error: If registry initialization fails.
    """
    return AgentRegistry(
        db_path=tmp_path / "test_agents.db"
    )


def make_agent(
    agent_id: str = "agent-1",
    name: str = "Test Agent",
) -> AgentConfig:
    """Create a valid agent for testing.

    Args:
        agent_id (str): Unique agent identifier.
        name (str): Display name.

    Returns:
        AgentConfig: Valid custom agent configuration.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id=agent_id,
        name=name,
        description="An agent for registry testing.",
        system_prompt="Answer questions using MCP.",
        tool_access="all",
        cache=CacheConfig(
            enabled=False,
            ttl_seconds=300,
        ),
    )


def test_create_and_get_agent(
    registry: AgentRegistry,
) -> None:
    """Verify that an agent can be created and retrieved.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify persistence.

    Raises:
        AssertionError: If persistence fails.
    """
    agent = make_agent()

    saved = registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )
    loaded = registry.get_agent(agent.id)
    record = registry.get_agent_record(agent.id)

    assert saved == agent
    assert loaded == agent
    assert record is not None
    assert record["owner_id"] == OWNER_ID
    assert record["approval_status"] == "draft"
    assert record["version"] == 1


def test_reject_duplicate_agent_id(
    registry: AgentRegistry,
) -> None:
    """Verify that duplicate agent identifiers are rejected.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify uniqueness.

    Raises:
        AssertionError: If duplicates are accepted.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    with pytest.raises(
        ValueError,
        match="Agent already exists",
    ):
        registry.create_agent(
            agent,
            owner_id=OWNER_ID,
        )


def test_list_agents(
    registry: AgentRegistry,
) -> None:
    """Verify that saved agents can be listed.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify listing.

    Raises:
        AssertionError: If listing is incorrect.
    """
    registry.create_agent(
        make_agent("agent-b", "Agent B"),
        owner_id=OWNER_ID,
    )
    registry.create_agent(
        make_agent("agent-a", "Agent A"),
        owner_id=OWNER_ID,
    )

    agents = registry.list_agents()

    assert len(agents) == 2
    assert [
        agent.id for agent in agents
    ] == [
        "agent-a",
        "agent-b",
    ]


def test_update_agent(
    registry: AgentRegistry,
) -> None:
    """Verify an owned agent can be updated with version checking.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify persistence and version increment.

    Raises:
        AssertionError: If the update is incorrect.
    """
    original = make_agent()

    registry.create_agent(
        original,
        owner_id=OWNER_ID,
    )

    updated = original.model_copy(
        update={
            "name": "Updated Agent",
            "system_prompt": "Explain MCP clearly.",
        }
    )

    result = registry.update_agent(
        agent_id=original.id,
        agent=updated,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert result is not None
    assert result.name == "Updated Agent"

    loaded = registry.get_agent(original.id)
    record = registry.get_agent_record(original.id)

    assert loaded is not None
    assert loaded.system_prompt == "Explain MCP clearly."

    assert record is not None
    assert record["version"] == 2
    assert record["approval_status"] == "draft"


def test_reject_agent_id_change(
    registry: AgentRegistry,
) -> None:
    """Verify that agent IDs cannot change during updates.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify ID immutability.

    Raises:
        AssertionError: If an ID change is accepted.
    """
    original = make_agent()

    registry.create_agent(
        original,
        owner_id=OWNER_ID,
    )

    replacement = make_agent(
        agent_id="different-agent"
    )

    with pytest.raises(
        ValueError,
        match="Agent ID cannot be changed",
    ):
        registry.update_agent(
            agent_id=original.id,
            agent=replacement,
            owner_id=OWNER_ID,
            expected_version=1,
        )


def test_delete_agent(
    registry: AgentRegistry,
) -> None:
    """Verify that an agent can be deleted.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify deletion.

    Raises:
        AssertionError: If deletion fails.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    assert registry.delete_agent(agent.id) is True
    assert registry.get_agent(agent.id) is None
    assert registry.delete_agent(agent.id) is False


def test_missing_agent(
    registry: AgentRegistry,
) -> None:
    """Verify that missing agents return None.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify missing-agent behavior.

    Raises:
        AssertionError: If missing agents are mishandled.
    """
    assert registry.get_agent("unknown-agent") is None

    assert registry.update_agent(
        agent_id="unknown-agent",
        agent=make_agent("unknown-agent"),
        owner_id=OWNER_ID,
        expected_version=1,
    ) is None


def test_agents_persist_across_registry_instances(
    tmp_path: Path,
) -> None:
    """Verify persistence across registry instances.

    Args:
        tmp_path (Path): Temporary database directory.

    Returns:
        None: Assertions verify persistent storage.

    Raises:
        AssertionError: If saved agents disappear.
    """
    db_path = tmp_path / "agents.db"

    first_registry = AgentRegistry(db_path)

    agent = make_agent()

    first_registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    second_registry = AgentRegistry(db_path)

    assert second_registry.get_agent(agent.id) == agent

    record = second_registry.get_agent_record(agent.id)

    assert record is not None
    assert record["owner_id"] == OWNER_ID
    assert record["version"] == 1


def test_unauthorized_owner_cannot_update(
    registry: AgentRegistry,
) -> None:
    """Verify that another user cannot update an owned agent.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify ownership enforcement.

    Raises:
        AssertionError: If an unauthorized update succeeds.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    updated = agent.model_copy(
        update={"name": "Unauthorized Change"}
    )

    result = registry.update_agent(
        agent_id=agent.id,
        agent=updated,
        owner_id=OTHER_USER_ID,
        expected_version=1,
    )

    assert result is None

    record = registry.get_agent_record(agent.id)

    assert record is not None
    assert record["configuration"].name == "Test Agent"
    assert record["version"] == 1


def test_stale_version_cannot_update(
    registry: AgentRegistry,
) -> None:
    """Verify that stale configuration versions are rejected.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify optimistic concurrency.

    Raises:
        AssertionError: If a stale update succeeds.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    first_update = agent.model_copy(
        update={"name": "Version Two"}
    )

    result = registry.update_agent(
        agent_id=agent.id,
        agent=first_update,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert result is not None

    stale_update = agent.model_copy(
        update={"name": "Stale Change"}
    )

    result = registry.update_agent(
        agent_id=agent.id,
        agent=stale_update,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert result is None

    record = registry.get_agent_record(agent.id)

    assert record is not None
    assert record["version"] == 2
    assert record["configuration"].name == "Version Two"


def test_update_invalidates_previous_approval(
    registry: AgentRegistry,
) -> None:
    """Verify that editing an approved agent revokes approval.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify approval invalidation.

    Raises:
        AssertionError: If approval remains valid after editing.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    submitted = registry.submit_agent(
        agent_id=agent.id,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert submitted is True

    approved = registry.approve_agent(
        agent_id=agent.id,
        reviewer_id=REVIEWER_ID,
        expected_version=1,
    )

    assert approved is True

    before = registry.get_agent_record(agent.id)

    assert before is not None
    assert before["approval_status"] == "approved"
    assert before["approved_by"] == REVIEWER_ID
    assert before["approved_at"] is not None

    updated = agent.model_copy(
        update={"name": "Modified After Approval"}
    )

    result = registry.update_agent(
        agent_id=agent.id,
        agent=updated,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert result is not None

    after = registry.get_agent_record(agent.id)

    assert after is not None
    assert after["approval_status"] == "draft"
    assert after["approved_by"] is None
    assert after["approved_at"] is None
    assert after["version"] == 2
    assert after["configuration"].name == (
        "Modified After Approval"
    )


def test_invalid_expected_version_is_rejected(
    registry: AgentRegistry,
) -> None:
    """Verify that invalid expected versions are rejected.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify version validation.

    Raises:
        ValueError: If the expected version is invalid.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    with pytest.raises(
        ValueError,
        match="Expected version must be at least 1",
    ):
        registry.update_agent(
            agent_id=agent.id,
            agent=agent,
            owner_id=OWNER_ID,
            expected_version=0,
        )


def test_update_preserves_owner(
    registry: AgentRegistry,
) -> None:
    """Verify that an update does not change agent ownership.

    Args:
        registry (AgentRegistry): Isolated test registry.

    Returns:
        None: Assertions verify ownership preservation.

    Raises:
        AssertionError: If ownership changes.
    """
    agent = make_agent()

    registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    updated = agent.model_copy(
        update={"name": "Updated Name"}
    )

    result = registry.update_agent(
        agent_id=agent.id,
        agent=updated,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert result is not None

    record = registry.get_agent_record(agent.id)

    assert record is not None
    assert record["owner_id"] == OWNER_ID
    assert record["version"] == 2
