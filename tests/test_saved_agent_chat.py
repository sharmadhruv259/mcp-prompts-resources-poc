
"""Tests for authenticated saved-agent execution through the chat API."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import api
from agent import AgentAuthorizationError
from auth.dependencies import current_user
from auth.permissions import Role
from models.agent_config import AgentConfig
from services.agent_registry import AgentRegistry


OWNER_ID = "test-owner-1"
REVIEWER_ID = "test-manager-1"


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Create an authenticated API client with isolated agent storage.

    Args:
        tmp_path (Path): Temporary directory for the test database.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Yields:
        TestClient: Authenticated FastAPI test client.

    Raises:
        None.
    """
    registry = AgentRegistry(tmp_path / "agents.db")

    monkeypatch.setattr(
        api,
        "registry",
        registry,
    )

    test_user = SimpleNamespace(
        id=OWNER_ID,
        role=Role.USER,
    )

    api.app.dependency_overrides[current_user] = (
        lambda: test_user
    )

    try:
        with TestClient(api.app) as test_client:
            yield test_client
    finally:
        api.app.dependency_overrides.pop(
            current_user,
            None,
        )


def make_agent() -> AgentConfig:
    """Create a saved test agent.

    Args:
        None.

    Returns:
        AgentConfig: Valid test agent configuration.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id="architecture-agent",
        name="Architecture Agent",
        description="Explains project architecture.",
        system_prompt="Explain project architecture using MCP.",
        tool_access="all",
        allowed_tools=[],
        allowed_resources=[],
        allowed_prompts=[],
    )


def create_approved_agent() -> None:
    """Create, submit, and approve an agent for chat testing.

    Args:
        None.

    Returns:
        None: The agent is saved and approved in the test registry.

    Raises:
        AssertionError: If submission or approval fails.
    """
    agent = make_agent()

    api.registry.create_agent(
        agent,
        owner_id=OWNER_ID,
    )

    submitted = api.registry.submit_agent(
        agent_id=agent.id,
        owner_id=OWNER_ID,
        expected_version=1,
    )

    assert submitted is True

    approved = api.registry.approve_agent(
        agent_id=agent.id,
        reviewer_id=REVIEWER_ID,
        expected_version=1,
    )

    assert approved is True

    record = api.registry.get_agent_record(agent.id)

    assert record is not None
    assert record["approval_status"] == "approved"
    assert record["owner_id"] == OWNER_ID


def test_chat_uses_saved_agent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chat executes an approved saved agent.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify saved-agent execution.

    Raises:
        AssertionError: If execution fails.
    """
    create_approved_agent()

    mock_run_agent = AsyncMock(
        return_value=(
            "Architecture explained.",
            [],
        ),
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "agent_id": "architecture-agent",
            "message": "Explain the architecture.",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Architecture explained."
    )

    mock_run_agent.assert_awaited_once()

    selected_agent = (
        mock_run_agent.await_args.kwargs["agent"]
    )

    assert selected_agent.id == "architecture-agent"
    assert selected_agent.system_prompt == (
        "Explain project architecture using MCP."
    )

    assert mock_run_agent.await_args.kwargs[
        "agent_version"
    ] == 1

    assert callable(
        mock_run_agent.await_args.kwargs[
            "validate_authorization"
        ]
    )


def test_chat_rejects_unknown_agent(
    client: TestClient,
) -> None:
    """Verify unknown saved agents return HTTP 404.

    Args:
        client (TestClient): Authenticated API test client.

    Returns:
        None: Assertions verify missing-agent handling.

    Raises:
        AssertionError: If an unknown agent is accepted.
    """
    response = client.post(
        "/api/chat",
        json={
            "agent_id": "missing-agent",
            "message": "Hello",
        },
    )

    assert response.status_code == 404


def test_chat_without_agent_uses_default_assistant(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify chat without an agent ID uses the Default Assistant.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify default assistant execution.

    Raises:
        AssertionError: If the Default Assistant is not selected.
    """
    mock_assistant = AsyncMock()
    mock_assistant.chat.return_value = (
        "Hello from Default Assistant."
    )

    monkeypatch.setattr(
        api,
        "DefaultAssistant",
        lambda: mock_assistant,
    )

    response = client.post(
        "/api/chat",
        json={"message": "Hello"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Hello from Default Assistant."
    )
    assert response.json()["events"] == []

    mock_assistant.chat.assert_awaited_once_with(
        "Hello"
    )


def test_chat_rejects_multiple_agent_sources(
    client: TestClient,
) -> None:
    """Verify inline agent configurations cannot accompany saved agent IDs.

    Args:
        client (TestClient): Authenticated API test client.

    Returns:
        None: Assertions verify inline-agent rejection.

    Raises:
        AssertionError: If conflicting agent sources are accepted.
    """
    response = client.post(
        "/api/chat",
        json={
            "message": "Hello",
            "agent_id": "architecture-agent",
            "agent": make_agent().model_dump(),
        },
    )

    assert response.status_code == 422


def test_chat_rejects_unapproved_agent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify draft agents cannot execute through chat.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify approval enforcement.

    Raises:
        AssertionError: If an unapproved agent executes.
    """
    api.registry.create_agent(
        make_agent(),
        owner_id=OWNER_ID,
    )

    mock_run_agent = AsyncMock(
        return_value=(
            "Should not execute.",
            [],
        ),
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "agent_id": "architecture-agent",
            "message": "Explain the architecture.",
        },
    )

    assert response.status_code == 403

    mock_run_agent.assert_not_awaited()


def test_chat_rejects_other_users_agent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify users cannot execute agents owned by another user.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify agent ownership enforcement.

    Raises:
        AssertionError: If unauthorized execution succeeds.
    """
    agent = make_agent()

    api.registry.create_agent(
        agent,
        owner_id="another-user",
    )

    mock_run_agent = AsyncMock(
        return_value=(
            "Should not execute.",
            [],
        ),
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "agent_id": agent.id,
            "message": "Explain the architecture.",
        },
    )

    assert response.status_code == 404

    mock_run_agent.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        "update",
        "revoke",
        "delete",
    ],
    ids=[
        "agent-updated",
        "approval-revoked",
        "agent-deleted",
    ],
)
def test_chat_rejects_runtime_authorization_change(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    """Reject chat when the saved agent changes during execution.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.
        change (str): Agent state change to simulate.

    Returns:
        None: Assertions verify HTTP 403.

    Raises:
        AssertionError: If the unauthorized response is returned.
    """
    create_approved_agent()

    async def simulated_run_agent(
        **kwargs: object,
    ) -> tuple[str, list[dict[str, str]]]:
        """Simulate an agent change while chat is running.

        Args:
            **kwargs (object): Agent execution arguments.

        Returns:
            tuple[str, list[dict[str, str]]]: Simulated response.

        Raises:
            AgentAuthorizationError: If runtime validation fails.
        """
        validate_authorization = kwargs[
            "validate_authorization"
        ]

        await validate_authorization()

        if change == "update":
            updated_agent = make_agent().model_copy(
                update={
                    "system_prompt": (
                        "Updated architecture instructions."
                    ),
                }
            )

            updated = api.registry.update_agent(
                agent_id="architecture-agent",
                agent=updated_agent,
                owner_id=OWNER_ID,
                expected_version=1,
            )

            assert updated is not None

        elif change == "revoke":
            # Simulate administrative revocation of approval.
            with api.registry._connect() as connection:
                connection.execute(
                    """
                    UPDATE agents
                    SET approval_status = 'rejected',
                        approved_by = NULL,
                        approved_at = NULL
                    WHERE id = ?
                    """,
                    ("architecture-agent",),
                )

        elif change == "delete":
            deleted = api.registry.delete_agent(
                "architecture-agent"
            )

            assert deleted is True

        await validate_authorization()

        return "This answer must not be returned.", []

    mocked_run_agent = AsyncMock(
        side_effect=simulated_run_agent,
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mocked_run_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "agent_id": "architecture-agent",
            "message": "Explain the architecture.",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]

    mocked_run_agent.assert_awaited_once()


def test_chat_allows_unchanged_agent_with_runtime_validation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Allow chat when the saved agent remains approved and unchanged.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching utility.

    Returns:
        None: Assertions verify successful runtime authorization.

    Raises:
        AssertionError: If the approved agent is rejected.
    """
    create_approved_agent()

    validation_count = 0

    async def simulated_run_agent(
        **kwargs: object,
    ) -> tuple[str, list[dict[str, str]]]:
        """Validate the approved agent during simulated execution.

        Args:
            **kwargs (object): Agent execution arguments.

        Returns:
            tuple[str, list[dict[str, str]]]: Simulated answer and events.

        Raises:
            AgentAuthorizationError: If authorization fails.
        """
        nonlocal validation_count

        validate_authorization = kwargs[
            "validate_authorization"
        ]

        await validate_authorization()
        validation_count += 1

        await validate_authorization()
        validation_count += 1

        return "Authorized architecture explanation.", []

    mocked_run_agent = AsyncMock(
        side_effect=simulated_run_agent,
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mocked_run_agent,
    )

    response = client.post(
        "/api/chat",
        json={
            "agent_id": "architecture-agent",
            "message": "Explain the architecture.",
        },
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Authorized architecture explanation."
    )
    assert response.json()["events"] == []

    assert validation_count == 2
    mocked_run_agent.assert_awaited_once()
