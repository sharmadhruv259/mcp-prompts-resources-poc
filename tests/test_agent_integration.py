
"""Integration tests for custom agent execution."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import TextContent

import agent as agent_module
from models.agent_config import AgentConfig
from services.mcp_discovery import (
    MCPCapabilities,
    MCPPromptInfo,
    MCPResourceInfo,
    MCPToolInfo,
)


def make_agent(
    tool_access: str = "all",
    allowed_tools: list[str] | None = None,
) -> AgentConfig:
    """Create a test custom agent.

    Args:
        tool_access (str): Tool access policy.
        allowed_tools (list[str] | None): Permitted native tools.

    Returns:
        AgentConfig: Valid agent configuration.

    Raises:
        ValueError: If configuration validation fails.
    """
    return AgentConfig(
    id="test-agent",
    name="Test Agent",
    description="Tests MCP execution.",
    system_prompt="Use MCP to answer accurately.",
    tool_access=tool_access,
    allowed_tools=allowed_tools or [],
    allowed_resources=["project://requirements"],
    allowed_prompts=["explain_technical"],
)


def make_capabilities() -> MCPCapabilities:
    """Create a representative MCP capability collection.

    Args:
        None.

    Returns:
        MCPCapabilities: Test tools, resources, and prompts.

    Raises:
        None.
    """
    return MCPCapabilities(
        tools=[
            MCPToolInfo(
                name="get_project_overview",
                description="Get the project overview.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )
        ],
        resources=[
            MCPResourceInfo(
                uri="project://requirements",
                name="Requirements",
            )
        ],
        prompts=[
            MCPPromptInfo(
                name="explain_technical",
                description="Explain technical details.",
                arguments=["audience"],
            )
        ],
    )


def make_tool_call(
    name: str,
    arguments: dict,
) -> SimpleNamespace:
    """Create a simulated Groq tool call.

    Args:
        name (str): Function name.
        arguments (dict): Function arguments.

    Returns:
        SimpleNamespace: Simulated Groq tool call.

    Raises:
        TypeError: If arguments cannot be JSON encoded.
    """
    return SimpleNamespace(
        id="call-123",
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments),
        ),
    )


def make_message(
    content: str | None = None,
    calls: list | None = None,
) -> SimpleNamespace:
    """Create a simulated Groq assistant message.

    Args:
        content (str | None): Assistant text.
        calls (list | None): Requested function calls.

    Returns:
        SimpleNamespace: Simulated assistant message.

    Raises:
        None.
    """
    return SimpleNamespace(
        content=content,
        tool_calls=calls or [],
    )


@pytest.fixture
def mock_environment(monkeypatch):
    """Prepare mocked Groq and MCP discovery dependencies.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest patch utility.

    Returns:
        tuple: Mock MCP client and Groq completion function.


    Raises:
        None.
    """
    client = MagicMock()
    client.call_tool = AsyncMock()
    client.read_resource = AsyncMock()
    client.get_prompt = AsyncMock()

    discovery = AsyncMock(
        return_value=make_capabilities()
    )

    completion = AsyncMock()

    monkeypatch.setattr(
        agent_module,
        "GROQ_API_KEY",
        "test-key",
    )
    monkeypatch.setattr(
        agent_module,
        "Groq",
        MagicMock(),
    )
    monkeypatch.setattr(
        agent_module,
        "discover_mcp_capabilities",
        discovery,
    )
    monkeypatch.setattr(
        agent_module,
        "request_completion",
        completion,
    )

    return client, completion


@pytest.mark.asyncio
async def test_agent_executes_native_mcp_tool(
    mock_environment,
) -> None:
    """Verify that an agent executes a native MCP tool.

    Args:
        mock_environment (tuple): Mocked execution dependencies.

    Returns:
        None: Assertions verify execution.

    Raises:
        AssertionError: If execution results are incorrect.
    """
    client, completion = mock_environment

    client.call_tool.return_value = SimpleNamespace(
    is_error=False,
    content=[
        TextContent(
            type="text",
            text="The project uses FastAPI and MCP.",
        )
    ],
)

    completion.side_effect = [
        make_message(
            calls=[
                make_tool_call(
                    "mcp_tool__get_project_overview",
                    {},
                )
            ]
        ),
        make_message(
            content="The project uses FastAPI and MCP."
        ),
    ]

    answer, events = await agent_module.run_agent(
        client=client,
        question="Explain the project.",
        agent=make_agent(),
    )

    assert "FastAPI" in answer
    assert len(events) == 1
    assert events[0]["status"] == "completed"

    client.call_tool.assert_awaited_once_with(
        "get_project_overview",
        {},
    )


@pytest.mark.asyncio
async def test_agent_reads_mcp_resource(
    mock_environment,
) -> None:
    """Verify that an agent reads an MCP resource.

    Args:
        mock_environment (tuple): Mocked execution dependencies.

    Returns:
        None: Assertions verify resource retrieval.

    Raises:
        AssertionError: If retrieval is incorrect.
    """
    client, completion = mock_environment

    from mcp.types import TextResourceContents

    client.read_resource.return_value = (
        SimpleNamespace(
            contents=[
                TextResourceContents(
                    uri="project://requirements",
                    text="The system requires MCP.",
                )
            ]
        )
    )

    completion.side_effect = [
        make_message(
            calls=[
                make_tool_call(
                    "read_mcp_resource",
                    {
                        "uri": "project://requirements"
                    },
                )
            ]
        ),
        make_message(
            content="The system requires MCP."
        ),
    ]

    answer, events = await agent_module.run_agent(
        client=client,
        question="What are the requirements?",
        agent=make_agent(),
    )

    assert "requires MCP" in answer
    assert events[0]["status"] == "completed"
    client.read_resource.assert_awaited_once_with(
        "project://requirements"
    )


@pytest.mark.asyncio
async def test_agent_rejects_unauthorized_tool_call(
    mock_environment,
) -> None:
    """Verify that unauthorized tool calls are rejected.

    Args:
        mock_environment (tuple): Mocked execution dependencies.

    Returns:
        None: Assertions verify authorization.

    Raises:
        AssertionError: If unauthorized execution occurs.
    """
    client, completion = mock_environment

    completion.side_effect = [
        make_message(
            calls=[
                make_tool_call(
                    "mcp_tool__get_project_overview",
                    {},
                )
            ]
        ),
        make_message(
            content="I cannot access that tool."
        ),
    ]

    # Selected access permits only the named tool.
    # Here the requested tool is deliberately absent
    # from the agent's available function schemas.
    restricted_agent = make_agent(
        tool_access="selected",
        allowed_tools=["another_tool"],
    )

    with pytest.raises(
        ValueError,
        match="Unknown or unavailable MCP tools",
    ):
        await agent_module.run_agent(
            client=client,
            question="Explain the project.",
            agent=restricted_agent,
        )

    client.call_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_handles_mcp_tool_failure(
    mock_environment,
) -> None:
    """Verify that MCP failures produce failed execution events.

    Args:
        mock_environment (tuple): Mocked execution dependencies.

    Returns:
        None: Assertions verify failure handling.

    Raises:
        AssertionError: If the failure is not handled.
    """
    client, completion = mock_environment

    client.call_tool.return_value = SimpleNamespace(
        isError=True,
        content=[
            TextContent(
                type="text",
                text="Internal MCP failure.",
            )
        ],
    )

    completion.side_effect = [
        make_message(
            calls=[
                make_tool_call(
                    "mcp_tool__get_project_overview",
                    {},
                )
            ]
        ),
        make_message(
            content="The project information is unavailable."
        ),
    ]

    answer, events = await agent_module.run_agent(
        client=client,
        question="Explain the project.",
        agent=make_agent(),
    )

    assert "unavailable" in answer
    assert len(events) == 1
    assert events[0]["status"] == "failed"
