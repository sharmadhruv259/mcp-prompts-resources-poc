
"""Integration tests for PostgreSQL-backed agent management."""

from uuid import uuid4

import pytest

from auth.permissions import Role
from models.agent_config import AgentConfig
from services.agent_registry import AgentRegistry
from services.user_service import UserService
from tests.postgres_test_db import get_test_session_factory


@pytest.fixture
def registry_context():
    """Provide isolated agent storage and temporary test users.

    Args:
        None.

    Returns:
        dict: Registry, owner, reviewer, and test user service.

    Raises:
        RuntimeError: If the test database is not configured safely.
    """
    session_factory = get_test_session_factory()

    user_service = UserService(
        session_factory=session_factory
    )

    registry = AgentRegistry(
        session_factory=session_factory
    )

    owner = user_service.create_user(
        username=f"agent_owner_{uuid4().hex[:12]}",
        password=f"Owner_{uuid4().hex}!",
        role=Role.USER,
    )

    reviewer = user_service.create_user(
        username=f"agent_reviewer_{uuid4().hex[:12]}",
        password=f"Reviewer_{uuid4().hex}!",
        role=Role.MANAGER,
    )

    agent_ids = []

    context = {
        "registry": registry,
        "owner": owner,
        "reviewer": reviewer,
        "agent_ids": agent_ids,
    }

    try:
        yield context
    finally:
        for agent_id in agent_ids:
            registry.delete_agent(agent_id)

        user_service.delete_user(reviewer.id)
        user_service.delete_user(owner.id)



def create_test_agent(
    agent_id: str,
    name: str = "PostgreSQL Test Agent",
) -> AgentConfig:
    """Create a valid agent configuration for integration testing.

    Args:
        agent_id (str): Unique agent identifier.
        name (str): Agent display name.

    Returns:
        AgentConfig: Valid agent configuration.

    Raises:
        ValueError: If the configuration violates model validation.
    """
    return AgentConfig(
        id=agent_id,
        name=name,
        description="Temporary agent for PostgreSQL integration testing.",
        system_prompt="You are a test assistant. Respond clearly.",
    )


def test_agent_creation_and_ownership(registry_context) -> None:
    """Verify agent creation, retrieval, and ownership restrictions.

    Args:
        registry_context (dict): Isolated registry and test users.

    Returns:
        None: Ownership assertions pass.

    Raises:
        AssertionError: If ownership behavior is incorrect.
    """
    registry = registry_context["registry"]
    owner = registry_context["owner"]
    reviewer = registry_context["reviewer"]

    agent_id = f"pg_agent_{uuid4().hex[:12]}"
    registry_context["agent_ids"].append(agent_id)

    agent = create_test_agent(agent_id)

    registry.create_agent(
        agent=agent,
        owner_id=owner.id,
    )

    record = registry.get_agent_record(agent_id)

    assert record is not None
    assert record["owner_id"] == owner.id
    assert record["approval_status"] == "draft"
    assert record["version"] == 1

    assert registry.get_agent(agent_id) is not None

    owned_records = registry.list_agent_records(
        owner_id=owner.id
    )

    assert any(
        item["id"] == agent_id
        for item in owned_records
    )

    # Another user cannot update the owner's agent.
    assert registry.update_agent(
        agent_id=agent_id,
        agent=agent,
        owner_id=reviewer.id,
        expected_version=1,
    ) is None

    # Another user cannot delete the owner's agent.
    assert registry.delete_agent(
        agent_id=agent_id,
        owner_id=reviewer.id,
    ) is False


def test_agent_version_control(registry_context) -> None:
    """Verify optimistic concurrency and approval reset on updates.

    Args:
        registry_context (dict): Isolated registry and test users.

    Returns:
        None: Version and approval assertions pass.

    Raises:
        AssertionError: If version control behaves incorrectly.
    """
    registry = registry_context["registry"]
    owner = registry_context["owner"]
    reviewer = registry_context["reviewer"]

    agent_id = f"pg_agent_{uuid4().hex[:12]}"
    registry_context["agent_ids"].append(agent_id)

    original = create_test_agent(agent_id)

    registry.create_agent(
        agent=original,
        owner_id=owner.id,
    )

    updated = create_test_agent(
        agent_id,
        name="Updated PostgreSQL Agent",
    )

    result = registry.update_agent(
        agent_id=agent_id,
        agent=updated,
        owner_id=owner.id,
        expected_version=1,
    )

    assert result is not None

    record = registry.get_agent_record(agent_id)

    assert record["version"] == 2
    assert record["approval_status"] == "draft"
    assert record["configuration"].name == updated.name

    # Stale versions must not overwrite newer changes.
    assert registry.update_agent(
        agent_id=agent_id,
        agent=original,
        owner_id=owner.id,
        expected_version=1,
    ) is None

    assert registry.submit_agent(
        agent_id=agent_id,
        owner_id=owner.id,
        expected_version=2,
    ) is True

    assert registry.approve_agent(
        agent_id=agent_id,
        reviewer_id=reviewer.id,
        expected_version=2,
    ) is True

    approved = registry.get_agent_record(agent_id)

    assert approved["approval_status"] == "approved"
    assert approved["approved_by"] == reviewer.id
    assert approved["approved_at"] is not None

    # Editing an approved agent invalidates its approval.
    updated_again = create_test_agent(
        agent_id,
        name="Revised After Approval",
    )

    assert registry.update_agent(
        agent_id=agent_id,
        agent=updated_again,
        owner_id=owner.id,
        expected_version=2,
    ) is not None

    revised = registry.get_agent_record(agent_id)

    assert revised["version"] == 3
    assert revised["approval_status"] == "draft"
    assert revised["approved_by"] is None
    assert revised["approved_at"] is None


def test_agent_approval_workflow(registry_context) -> None:
    """Verify submission, approval, and reviewer restrictions.

    Args:
        registry_context (dict): Isolated registry and test users.

    Returns:
        None: Approval workflow assertions pass.

    Raises:
        AssertionError: If workflow transitions are incorrect.
    """
    registry = registry_context["registry"]
    owner = registry_context["owner"]
    reviewer = registry_context["reviewer"]

    agent_id = f"pg_agent_{uuid4().hex[:12]}"
    registry_context["agent_ids"].append(agent_id)

    registry.create_agent(
        agent=create_test_agent(agent_id),
        owner_id=owner.id,
    )

    # A different user cannot submit the agent.
    assert registry.submit_agent(
        agent_id=agent_id,
        owner_id=reviewer.id,
        expected_version=1,
    ) is False

    assert registry.submit_agent(
        agent_id=agent_id,
        owner_id=owner.id,
        expected_version=1,
    ) is True

    pending = registry.get_agent_record(agent_id)

    assert pending["approval_status"] == "pending"

    # The owner cannot approve their own agent.
    assert registry.approve_agent(
        agent_id=agent_id,
        reviewer_id=owner.id,
        expected_version=1,
    ) is False

    # Incorrect version cannot be approved.
    assert registry.approve_agent(
        agent_id=agent_id,
        reviewer_id=reviewer.id,
        expected_version=2,
    ) is False

    assert registry.approve_agent(
        agent_id=agent_id,
        reviewer_id=reviewer.id,
        expected_version=1,
    ) is True

    approved = registry.get_agent_record(agent_id)

    assert approved["approval_status"] == "approved"
    assert approved["approved_by"] == reviewer.id

    # Approved agents cannot be submitted again.
    assert registry.submit_agent(
        agent_id=agent_id,
        owner_id=owner.id,
        expected_version=1,
    ) is False


def test_agent_rejection_workflow(registry_context) -> None:
    """Verify pending-agent rejection and reviewer restrictions.

    Args:
        registry_context (dict): Isolated registry and test users.

    Returns:
        None: Rejection workflow assertions pass.

    Raises:
        AssertionError: If rejection behavior is incorrect.
    """
    registry = registry_context["registry"]
    owner = registry_context["owner"]
    reviewer = registry_context["reviewer"]

    agent_id = f"pg_agent_{uuid4().hex[:12]}"
    registry_context["agent_ids"].append(agent_id)

    registry.create_agent(
        agent=create_test_agent(agent_id),
        owner_id=owner.id,
    )

    assert registry.submit_agent(
        agent_id=agent_id,
        owner_id=owner.id,
        expected_version=1,
    ) is True

    assert registry.reject_agent(
        agent_id=agent_id,
        reviewer_id=owner.id,
        expected_version=1,
    ) is False

    assert registry.reject_agent(
        agent_id=agent_id,
        reviewer_id=reviewer.id,
        expected_version=1,
    ) is True

    rejected = registry.get_agent_record(agent_id)

    assert rejected["approval_status"] == "rejected"
    assert rejected["approved_by"] is None
    assert rejected["approved_at"] is None

    # Rejected agents cannot be approved directly.
    assert registry.approve_agent(
        agent_id=agent_id,
        reviewer_id=reviewer.id,
        expected_version=1,
    ) is False
