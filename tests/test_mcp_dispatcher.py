
"""Test authorization and execution of MCP operations."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from mcp.types import TextContent, TextResourceContents

from models.agent_config import AgentConfig
from services.mcp_discovery import (
    MCPCapabilities,
    MCPPromptInfo,
    MCPResourceInfo,
    MCPToolInfo,
)
from unittest.mock import patch
from services.tool_registry import ToolRegistry

from services.mcp_dispatcher import (
    execute_mcp_operation,
)


def make_agent(
    selected: bool = False,
) -> AgentConfig:
    """Create a test agent with explicit MCP permissions.

    Args:
        selected (bool): Whether to restrict native tool access.

    Returns:
        AgentConfig: Valid agent configuration.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
        id="test-agent",
        name="Test Agent",
        description="Test MCP execution.",
        system_prompt="Use MCP capabilities.",
        tool_access="selected" if selected else "all",
        allowed_tools=(
            ["get_project_overview"] if selected else []
        ),
        allowed_resources=[
            "project://requirements",
        ],
        allowed_prompts=[
            "explain_technical",
        ],
    )

def make_capabilities() -> MCPCapabilities:
    """Create discovered capabilities for tests.

    Args:
        None.

    Returns:
        MCPCapabilities: Sample MCP capabilities.

    Raises:
        None.
    """
    return MCPCapabilities(
        tools=[
            MCPToolInfo(
                name="get_project_overview",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            ),
            MCPToolInfo(
                name="restricted_tool",
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


@pytest.mark.asyncio
async def test_execute_native_mcp_tool() -> None:
    """Verify a permitted native MCP tool executes.

    Args:
        None.

    Returns:
        None: Assertions verify the result.

    Raises:
        AssertionError: If execution fails.
    """
    client = SimpleNamespace(
        call_tool=AsyncMock(
            return_value=SimpleNamespace(
                is_error=False,
                content=[
                    TextContent(
                        type="text",
                        text="Project overview",
                    ),
                ],
            ),
        ),
    )

    result = await execute_mcp_operation(
        client=client,
        agent=make_agent(selected=True),
        capabilities=make_capabilities(),
        function_name="mcp_tool__get_project_overview",
        arguments={},
    )

    assert result == "Project overview"
    client.call_tool.assert_awaited_once_with(
        "get_project_overview",
        {},
    )


@pytest.mark.asyncio
async def test_reject_disallowed_tool() -> None:
    """Verify tool permissions are enforced.

    Args:
        None.

    Returns:
        None: Assertions verify rejection.

    Raises:
        AssertionError: If unauthorized execution succeeds.
    """
    client = SimpleNamespace(
        call_tool=AsyncMock(),
    )

    with pytest.raises(ValueError, match="not allowed"):
        await execute_mcp_operation(
            client=client,
            agent=make_agent(selected=True),
            capabilities=make_capabilities(),
            function_name="mcp_tool__restricted_tool",
            arguments={},
        )

    client.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_mcp_resource() -> None:
    """Verify discovered resources can be read.

    Args:
        None.

    Returns:
        None: Assertions verify resource text.

    Raises:
        AssertionError: If resource retrieval fails.
    """
    client = SimpleNamespace(
        read_resource=AsyncMock(
            return_value=SimpleNamespace(
                contents=[
                    TextResourceContents(
                        uri="project://requirements",
                        text="Project requirements",
                    ),
                ],
            ),
        ),
    )

    result = await execute_mcp_operation(
        client=client,
        agent=make_agent(),
        capabilities=make_capabilities(),
        function_name="read_mcp_resource",
        arguments={"uri": "project://requirements"},
    )

    assert result == "Project requirements"


@pytest.mark.asyncio
async def test_get_mcp_prompt() -> None:
    """Verify MCP prompts are retrieved.

    Args:
        None.

    Returns:
        None: Assertions verify prompt text.

    Raises:
        AssertionError: If prompt retrieval fails.
    """
    client = SimpleNamespace(
        get_prompt=AsyncMock(
            return_value=SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        content=TextContent(
                            type="text",
                            text="Explain technical architecture.",
                        ),
                    ),
                ],
            ),
        ),
    )

    result = await execute_mcp_operation(
        client=client,
        agent=make_agent(),
        capabilities=make_capabilities(),
        function_name="get_mcp_prompt",
        arguments={
            "name": "explain_technical",
            "audience": "developer",
        },
    )

    assert result == "Explain technical architecture."
    client.get_prompt.assert_awaited_once_with(
        "explain_technical",
        {"audience": "developer"},
    )


@pytest.mark.asyncio
async def test_reject_unknown_resource() -> None:
    """Verify undiscovered resources cannot be accessed.

    Args:
        None.

    Returns:
        None: Assertions verify rejection.

    Raises:
        AssertionError: If an unknown resource is accepted.
    """
    client = SimpleNamespace(
        read_resource=AsyncMock(),
    )

    with pytest.raises(ValueError, match="Unknown MCP resource"):
        await execute_mcp_operation(
            client=client,
            agent=make_agent(),
            capabilities=make_capabilities(),
            function_name="read_mcp_resource",
            arguments={"uri": "project://unknown"},
        )

    client.read_resource.assert_not_awaited()


@pytest.fixture
def isolated_tool_registry(tmp_path) -> ToolRegistry:
    """Create an isolated registry for dispatcher tests.

    Args:
        tmp_path (Path): Temporary pytest directory.

    Returns:
        ToolRegistry: Registry with seeded MCP operations.

    Raises:
        sqlite3.Error: If registry initialization fails.
    """
    return ToolRegistry(
        db_path=tmp_path / "dispatcher_tools.db"
    )


@pytest.mark.asyncio
async def test_disabled_native_tool_cannot_execute(
    isolated_tool_registry: ToolRegistry,
) -> None:
    """Verify Admin-disabled native tools cannot execute.

    Args:
        isolated_tool_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify execution is blocked.

    Raises:
        AssertionError: If the disabled tool executes.
    """
    isolated_tool_registry.set_enabled(
        name="get_project_overview",
        enabled=False,
    )

    client = SimpleNamespace(
        call_tool=AsyncMock(),
    )

    with patch(
        "services.mcp_dispatcher.tool_registry",
        isolated_tool_registry,
    ):
        with pytest.raises(
            ValueError,
            match="disabled or unavailable",
        ):
            await execute_mcp_operation(
                client=client,
                agent=make_agent(selected=True),
                capabilities=make_capabilities(),
                function_name="mcp_tool__get_project_overview",
                arguments={},
            )

    client.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_reenabled_native_tool_can_execute(
    isolated_tool_registry: ToolRegistry,
) -> None:
    """Verify re-enabled native tools execute successfully.

    Args:
        isolated_tool_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify execution succeeds.

    Raises:
        AssertionError: If the tool remains blocked.
    """
    isolated_tool_registry.set_enabled(
        name="get_project_overview",
        enabled=False,
    )

    isolated_tool_registry.set_enabled(
        name="get_project_overview",
        enabled=True,
    )

    client = SimpleNamespace(
        call_tool=AsyncMock(
            return_value=SimpleNamespace(
                is_error=False,
                content=[
                    TextContent(
                        type="text",
                        text="Project overview",
                    ),
                ],
            ),
        ),
    )

    with patch(
        "services.mcp_dispatcher.tool_registry",
        isolated_tool_registry,
    ):
        result = await execute_mcp_operation(
            client=client,
            agent=make_agent(selected=True),
            capabilities=make_capabilities(),
            function_name="mcp_tool__get_project_overview",
            arguments={},
        )

    assert result == "Project overview"

    client.call_tool.assert_awaited_once_with(
        "get_project_overview",
        {},
    )


@pytest.mark.asyncio
async def test_disabled_resource_operation_cannot_execute(
    isolated_tool_registry: ToolRegistry,
) -> None:
    """Verify Admin-disabled resource operations are blocked.

    Args:
        isolated_tool_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify resource access is blocked.

    Raises:
        AssertionError: If the resource is read.
    """
    isolated_tool_registry.set_enabled(
        name="read_mcp_resource",
        enabled=False,
    )

    client = SimpleNamespace(
        read_resource=AsyncMock(),
    )

    with patch(
        "services.mcp_dispatcher.tool_registry",
        isolated_tool_registry,
    ):
        with pytest.raises(
            ValueError,
            match="disabled or unavailable",
        ):
            await execute_mcp_operation(
                client=client,
                agent=make_agent(),
                capabilities=make_capabilities(),
                function_name="read_mcp_resource",
                arguments={
                    "uri": "project://requirements",
                },
            )

    client.read_resource.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_prompt_operation_cannot_execute(
    isolated_tool_registry: ToolRegistry,
) -> None:
    """Verify Admin-disabled prompt operations are blocked.

    Args:
        isolated_tool_registry (ToolRegistry): Test registry.

    Returns:
        None: Assertions verify prompt retrieval is blocked.

    Raises:
        AssertionError: If the prompt is retrieved.
    """
    isolated_tool_registry.set_enabled(
        name="get_mcp_prompt",
        enabled=False,
    )

    client = SimpleNamespace(
        get_prompt=AsyncMock(),
    )

    with patch(
        "services.mcp_dispatcher.tool_registry",
        isolated_tool_registry,
    ):
        with pytest.raises(
            ValueError,
            match="disabled or unavailable",
        ):
            await execute_mcp_operation(
                client=client,
                agent=make_agent(),
                capabilities=make_capabilities(),
                function_name="get_mcp_prompt",
                arguments={
                    "name": "explain_technical",
                    "audience": "developer",
                },
            )

    client.get_prompt.assert_not_awaited()
