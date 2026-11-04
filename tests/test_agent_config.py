
import pytest
from pydantic import ValidationError

from models.agent_config import AgentConfig, CacheConfig


def test_agent_config_with_all_tools() -> None:
    """Verify that an agent can access all tools.

    Args:
        None.

    Returns:
        None: Assertions validate the configuration.

    Raises:
        AssertionError: If the configuration is incorrect.
    """
    agent = AgentConfig(
        id="project-review",
        name="Project Review Agent",
        description="Reviews project architecture.",
        system_prompt="Analyze project documentation.",
    )

    assert agent.tool_access == "all"
    assert agent.allowed_tools == []
    assert agent.cache.enabled is False


def test_agent_config_with_selected_tools() -> None:
    """Verify selected tool access.

    Args:
        None.

    Returns:
        None: Assertions validate the selected tools.

    Raises:
        AssertionError: If tool selection is incorrect.
    """
    agent = AgentConfig(
        id="technical-agent",
        name="Technical Agent",
        description="Explains technical details.",
        system_prompt="Provide technical explanations.",
        tool_access="selected",
        allowed_tools=["read_mcp_resource"],
        cache=CacheConfig(enabled=True, ttl_seconds=300),
    )

    assert agent.allowed_tools == ["read_mcp_resource"]
    assert agent.cache.enabled is True


def test_selected_tools_cannot_be_empty() -> None:
    """Verify that selected mode requires tools.

    Args:
        None.

    Returns:
        None: The test passes when validation fails as expected.

    Raises:
        AssertionError: If invalid configuration is accepted.
    """
    with pytest.raises(ValidationError):
        AgentConfig(
            id="invalid-agent",
            name="Invalid Agent",
            description="Invalid tool selection.",
            system_prompt="Test prompt.",
            tool_access="selected",
            allowed_tools=[],
        )
