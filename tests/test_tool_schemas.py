
"""Test dynamic Groq schemas for custom agents."""

import pytest

from models.agent_config import AgentConfig
from services.mcp_discovery import (
    MCPCapabilities,
    MCPPromptInfo,
    MCPResourceInfo,
    MCPToolInfo,
)
from tool_schemas import build_agent_tool_schemas
from unittest.mock import patch

from services.tool_registry import ToolRegistry

def make_agent(
    tool_access: str = "all",
    allowed_tools: list[str] | None = None,
) -> AgentConfig:
    """Create an agent with explicit MCP capability permissions.

    Args:
        tool_access (str): Native tool access mode.
        allowed_tools (list[str] | None): Permitted native MCP tools.

    Returns:
        AgentConfig: Valid agent configuration.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id="test-agent",
        name="Test Agent",
        description="Tests MCP execution.",
        system_prompt="Use MCP tools when appropriate.",
        tool_access=tool_access,
        allowed_tools=allowed_tools or [],
        allowed_resources=[
            "project://requirements",
        ],
        allowed_prompts=[
            "explain_technical",
        ],
    )

def make_capabilities() -> MCPCapabilities:
    """Create sample MCP capabilities.

    Args:
        None.

    Returns:
        MCPCapabilities: Sample discovery results.

    Raises:
        None.
    """
    return MCPCapabilities(
        tools=[
            MCPToolInfo(
                name="get_project_overview",
                description="Get project overview.",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MCPToolInfo(
                name="get_project_status",
                description="Get project status.",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ],
        resources=[
            MCPResourceInfo(
                uri="project://requirements",
                name="project_requirements",
            ),
        ],
        prompts=[
            MCPPromptInfo(
                name="explain_technical",
                arguments=["audience"],
            ),
        ],
    )


def test_all_tools_available() -> None:
    """Verify all discovered capabilities are exposed.

    Args:
        None.

    Returns:
        None: Assertions verify the schemas.

    Raises:
        AssertionError: If expected schemas are missing.
    """
    schemas = build_agent_tool_schemas(
        make_capabilities(),
        make_agent(),
    )

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert names == {
    "mcp_tool__get_project_overview",
    "read_mcp_resource",
    "get_mcp_prompt",
    }


def test_selected_tool_access() -> None:
    """Verify disallowed native MCP tools are excluded.

    Args:
        None.

    Returns:
        None: Assertions verify permission filtering.

    Raises:
        AssertionError: If a disallowed tool is exposed.
    """
    schemas = build_agent_tool_schemas(
        make_capabilities(),
        make_agent(
            tool_access="selected",
            allowed_tools=["get_project_overview"],
        ),
    )

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert "mcp_tool__get_project_overview" in names
    assert "mcp_tool__get_project_status" not in names


def test_unknown_selected_tool_rejected() -> None:
    """Verify unknown MCP tool permissions are rejected.

    Args:
        None.

    Returns:
        None: The test expects a validation failure.

    Raises:
        AssertionError: If unknown tools are accepted.
    """
    with pytest.raises(ValueError, match="Unknown"):
        build_agent_tool_schemas(
            make_capabilities(),
            make_agent(
                tool_access="selected",
                allowed_tools=["nonexistent_tool"],
            ),
        )


@pytest.fixture
def isolated_schema_registry(tmp_path) -> ToolRegistry:
    """Create an isolated Tool Registry for schema tests.

    Args:
        tmp_path (Path): Temporary pytest directory.

    Returns:
        ToolRegistry: Registry backed by isolated SQLite storage.

    Raises:
        sqlite3.Error: If registry initialization fails.
    """
    return ToolRegistry(
        db_path=tmp_path / "schema_tools.db"
    )


def test_disabled_tool_excluded_from_groq_schemas(
    isolated_schema_registry: ToolRegistry,
) -> None:
    """Verify disabled tools are excluded from Groq schemas.

    Args:
        isolated_schema_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify schema filtering.

    Raises:
        AssertionError: If disabled tools remain exposed.
    """
    isolated_schema_registry.set_enabled(
        name="get_project_overview",
        enabled=False,
    )

    with patch(
        "tool_schemas.tool_registry",
        isolated_schema_registry,
    ):
        schemas = build_agent_tool_schemas(
            make_capabilities(),
            make_agent(),
        )

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert "mcp_tool__get_project_overview" not in names
    assert "mcp_tool__get_project_status" not in names
    assert "read_mcp_resource" in names
    assert "get_mcp_prompt" in names


def test_disabled_resource_excluded_from_groq_schemas(
    isolated_schema_registry: ToolRegistry,
) -> None:
    """Verify disabled resource operations are hidden from Groq.

    Args:
        isolated_schema_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify resource filtering.

    Raises:
        AssertionError: If disabled resources remain exposed.
    """
    isolated_schema_registry.set_enabled(
        name="read_mcp_resource",
        enabled=False,
    )

    with patch(
        "tool_schemas.tool_registry",
        isolated_schema_registry,
    ):
        schemas = build_agent_tool_schemas(
            make_capabilities(),
            make_agent(),
        )

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert "read_mcp_resource" not in names
    assert "mcp_tool__get_project_overview" in names
    assert "get_mcp_prompt" in names


def test_disabled_prompt_excluded_from_groq_schemas(
    isolated_schema_registry: ToolRegistry,
) -> None:
    """Verify disabled prompt operations are hidden from Groq.

    Args:
        isolated_schema_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify prompt filtering.

    Raises:
        AssertionError: If disabled prompts remain exposed.
    """
    isolated_schema_registry.set_enabled(
        name="get_mcp_prompt",
        enabled=False,
    )

    with patch(
        "tool_schemas.tool_registry",
        isolated_schema_registry,
    ):
        schemas = build_agent_tool_schemas(
            make_capabilities(),
            make_agent(),
        )

    names = {
        item["function"]["name"]
        for item in schemas
    }

    assert "get_mcp_prompt" not in names
    assert "mcp_tool__get_project_overview" in names
    assert "read_mcp_resource" in names


def test_reenabled_tool_restored_to_groq_schemas(
    isolated_schema_registry: ToolRegistry,
) -> None:
    """Verify re-enabled tools become available to Groq.

    Args:
        isolated_schema_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify tool restoration.

    Raises:
        AssertionError: If the enabled tool remains hidden.
    """
    isolated_schema_registry.set_enabled(
        name="get_project_overview",
        enabled=False,
    )

    with patch(
        "tool_schemas.tool_registry",
        isolated_schema_registry,
    ):
        disabled_schemas = build_agent_tool_schemas(
            make_capabilities(),
            make_agent(),
        )

        isolated_schema_registry.set_enabled(
            name="get_project_overview",
            enabled=True,
        )

        enabled_schemas = build_agent_tool_schemas(
            make_capabilities(),
            make_agent(),
        )

    disabled_names = {
        item["function"]["name"]
        for item in disabled_schemas
    }

    enabled_names = {
        item["function"]["name"]
        for item in enabled_schemas
    }

    assert "mcp_tool__get_project_overview" not in disabled_names
    assert "mcp_tool__get_project_overview" in enabled_names
