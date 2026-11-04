
"""Integration tests for MCP Playground FastAPI endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import api
from auth.dependencies import current_user
from auth.permissions import Role
from models.agent_config import AgentConfig
from services.agent_registry import AgentRegistry


OWNER_ID = "integration-owner-1"
REVIEWER_ID = "integration-manager-1"
AGENT_ID = "test-agent"


@pytest.fixture
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Create an authenticated API client with isolated storage.

    Args:
        tmp_path (Path): Temporary test directory.
        monkeypatch (pytest.MonkeyPatch): Pytest patching fixture.

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
    """Create a valid custom agent for integration testing.

    Args:
        None.

    Returns:
        AgentConfig: Valid agent configuration.

    Raises:
        ValueError: If agent validation fails.
    """
    return AgentConfig(
        id=AGENT_ID,
        name="Test Agent",
        description="Tests MCP execution.",
        system_prompt="Answer using MCP project information.",
        tool_access="all",
        allowed_tools=[],
        allowed_resources=[],
        allowed_prompts=[],
    )


def make_chat_payload(
    agent_id: str | None = AGENT_ID,
) -> dict:
    """Create a chat request referencing a saved agent.

    Args:
        agent_id (str | None): Saved agent identifier, or None
            for the Default Assistant.

    Returns:
        dict: Valid chat request payload.

    Raises:
        None.
    """
    payload = {
        "message": "Explain the project architecture.",
    }

    if agent_id is not None:
        payload["agent_id"] = agent_id

    return payload


def create_approved_agent() -> AgentConfig:
    """Create and approve an agent in the isolated test registry.

    Args:
        None.

    Returns:
        AgentConfig: Saved and approved agent.

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

    return agent


def test_health_endpoint(
    client: TestClient,
) -> None:
    """Verify that the health endpoint responds successfully.

    Args:
        client (TestClient): Isolated API test client.

    Returns:
        None: Assertions verify the response.

    Raises:
        AssertionError: If the health response is incorrect.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_default_assistant_chat_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that chat without an agent ID uses the Default Assistant.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching fixture.

    Returns:
        None: Assertions verify Default Assistant execution.

    Raises:
        AssertionError: If the Default Assistant is not selected.
    """
    mock_assistant = AsyncMock()
    mock_assistant.chat.return_value = (
        "Hello from the Default Assistant."
    )

    monkeypatch.setattr(
        api,
        "DefaultAssistant",
        lambda: mock_assistant,
    )

    response = client.post(
        "/api/chat",
        json={
            "message": "Hello",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "Hello from the Default Assistant."
    )
    assert data["events"] == []

    mock_assistant.chat.assert_awaited_once_with(
        "Hello"
    )


def test_chat_endpoint_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify successful execution of an approved saved agent.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching fixture.

    Returns:
        None: Assertions verify execution and MCP events.

    Raises:
        AssertionError: If execution or response handling fails.
    """
    create_approved_agent()

    mock_run_agent = AsyncMock(
        return_value=(
            "The project uses FastAPI and MCP.",
            [
                {
                    "id": "event-1",
                    "tool": "mcp_tool__get_project_overview",
                    "status": "completed",
                    "description": "Executed MCP operation.",
                }
            ],
        )
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/api/chat",
        json=make_chat_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == (
        "The project uses FastAPI and MCP."
    )
    assert len(data["events"]) == 1
    assert data["events"][0]["status"] == "completed"
    assert data["events"][0]["tool"] == (
        "mcp_tool__get_project_overview"
    )

    mock_run_agent.assert_awaited_once()

    kwargs = mock_run_agent.await_args.kwargs

    assert kwargs["question"] == (
        "Explain the project architecture."
    )
    assert kwargs["agent"].id == AGENT_ID


def test_chat_rejects_empty_message(
    client: TestClient,
) -> None:
    """Verify that empty messages are rejected.

    Args:
        client (TestClient): Authenticated API test client.

    Returns:
        None: Assertions verify request validation.

    Raises:
        AssertionError: If an empty message is accepted.
    """
    payload = make_chat_payload()
    payload["message"] = "   "

    response = client.post(
        "/api/chat",
        json=payload,
    )

    assert response.status_code == 422


def test_chat_rejects_invalid_agent(
    client: TestClient,
) -> None:
    """Verify that invalid inline agent configurations are rejected.

    Args:
        client (TestClient): Authenticated API test client.

    Returns:
        None: Assertions verify agent configuration validation.

    Raises:
        AssertionError: If invalid configuration is accepted.
    """
    invalid_agent = make_agent().model_dump()

    invalid_agent["tool_access"] = "selected"
    invalid_agent["allowed_tools"] = []

    response = client.post(
        "/api/chat",
        json={
            "message": "Explain the architecture.",
            "agent": invalid_agent,
        },
    )

    assert response.status_code == 422


def test_chat_rejects_valid_inline_agent(
    client: TestClient,
) -> None:
    """Verify that valid inline agents cannot bypass saved-agent approval.

    Args:
        client (TestClient): Authenticated API test client.

    Returns:
        None: Assertions verify inline-agent rejection.

    Raises:
        AssertionError: If inline execution is accepted.
    """
    response = client.post(
        "/api/chat",
        json={
            "message": "Explain the architecture.",
            "agent": make_agent().model_dump(),
        },
    )

    assert response.status_code == 422
    assert "Inline agent configurations" in (
        response.json()["detail"]
    )


def test_chat_handles_agent_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify execution failures return HTTP 502 without leaking details.

    Args:
        client (TestClient): Authenticated API test client.
        monkeypatch (pytest.MonkeyPatch): Pytest patching fixture.

    Returns:
        None: Assertions verify safe error handling.

    Raises:
        AssertionError: If execution errors are exposed or mishandled.
    """
    create_approved_agent()

    mock_run_agent = AsyncMock(
        side_effect=RuntimeError(
            "Simulated Groq failure."
        )
    )

    monkeypatch.setattr(
        api,
        "run_agent",
        mock_run_agent,
    )

    response = client.post(
        "/api/chat",
        json=make_chat_payload(),
    )

    assert response.status_code == 502

    detail = response.json()["detail"]

    assert "Unable to execute" in detail
    assert "Simulated Groq failure" not in detail

    mock_run_agent.assert_awaited_once()
