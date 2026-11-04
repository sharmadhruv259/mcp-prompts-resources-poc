
"""Test authorization changes during custom agent execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import agent as agent_module
from agent import AgentAuthorizationError, run_agent
from models.agent_config import AgentConfig
from services.mcp_discovery import MCPCapabilities


def make_agent() -> AgentConfig:
    """Create an agent for runtime authorization tests.

    Args:
        None.

    Returns:
        AgentConfig: Test agent configuration.

    Raises:
        ValueError: If the configuration is invalid.
    """
    return AgentConfig(
        id="runtime-agent",
        name="Runtime Agent",
        description="Tests runtime authorization enforcement.",
        system_prompt="Answer using authorized MCP operations.",
        tool_access="all",
        allowed_resources=[],
        allowed_prompts=[],
        cache={
            "enabled": False,
            "ttl_seconds": 300,
        },
    )


def make_response(content: str) -> SimpleNamespace:
    """Create a simulated Groq assistant message.

    Args:
        content (str): Assistant response text.

    Returns:
        SimpleNamespace: Mock response with no tool calls.

    Raises:
        None.
    """
    return SimpleNamespace(
        content=content,
        tool_calls=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    [
        ("version", 2),
        ("approval_status", "rejected"),
        ("exists", False),
    ],
    ids=[
        "agent-updated",
        "approval-revoked",
        "agent-deleted",
    ],
)
async def test_agent_change_blocks_inflight_response(
    changed_field: str,
    changed_value: object,
) -> None:
    """Reject a final response if agent authorization changes.

    Args:
        changed_field (str): Registry field to modify.
        changed_value (object): Replacement field value.

    Returns:
        None: Assertions confirm execution is rejected.

    Raises:
        AssertionError: If an unauthorized response is returned.
    """
    state = {
        "exists": True,
        "version": 1,
        "approval_status": "approved",
        "owner_id": "owner-1",
    }

    async def validate_authorization() -> None:
        """Check the simulated registry state.

        Args:
            None.

        Returns:
            None: Authorization remains valid.

        Raises:
            AgentAuthorizationError: If agent state has changed.
        """
        if not state["exists"]:
            raise AgentAuthorizationError(
                "Agent no longer exists."
            )

        if state["approval_status"] != "approved":
            raise AgentAuthorizationError(
                "Agent is no longer approved."
            )

        if state["version"] != 1:
            raise AgentAuthorizationError(
                "Agent configuration has changed."
            )

        if state["owner_id"] != "owner-1":
            raise AgentAuthorizationError(
                "Agent ownership has changed."
            )

    async def completion_with_change(**kwargs: object) -> SimpleNamespace:
        """Simulate a registry change during Groq completion.

        Args:
            **kwargs (object): Unused completion arguments.

        Returns:
            SimpleNamespace: Simulated Groq response.

        Raises:
            None.
        """
        state[changed_field] = changed_value
        return make_response("This answer must not be returned.")

    with (
        patch.object(agent_module, "GROQ_API_KEY", "test-key"),
        patch.object(
            agent_module,
            "discover_mcp_capabilities",
            new_callable=AsyncMock,
            return_value=MCPCapabilities(
                tools=[],
                resources=[],
                prompts=[],
            ),
        ),
        patch.object(
            agent_module,
            "request_completion",
            side_effect=completion_with_change,
        ) as mocked_completion,
    ):
        with pytest.raises(AgentAuthorizationError):
            await run_agent(
                client=AsyncMock(),
                question="Explain the project.",
                agent=make_agent(),
                agent_version=1,
                validate_authorization=validate_authorization,
            )

    mocked_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_unchanged_approved_agent_returns_answer() -> None:
    """Allow a response when authorization remains valid.

    Args:
        None.

    Returns:
        None: Assertions verify successful execution.

    Raises:
        AssertionError: If valid execution fails.
    """
    validation_count = 0

    async def validate_authorization() -> None:
        """Record each successful authorization check.

        Args:
            None.

        Returns:
            None: Agent remains authorized.

        Raises:
            None.
        """
        nonlocal validation_count
        validation_count += 1

    with (
        patch.object(agent_module, "GROQ_API_KEY", "test-key"),
        patch.object(
            agent_module,
            "discover_mcp_capabilities",
            new_callable=AsyncMock,
            return_value=MCPCapabilities(
                tools=[],
                resources=[],
                prompts=[],
            ),
        ),
        patch.object(
            agent_module,
            "request_completion",
            new_callable=AsyncMock,
            return_value=make_response("Authorized answer."),
        ),
    ):
        answer, events = await run_agent(
            client=AsyncMock(),
            question="Explain the project.",
            agent=make_agent(),
            agent_version=1,
            validate_authorization=validate_authorization,
        )

    assert answer == "Authorized answer."
    assert events == []
    assert validation_count == 2
