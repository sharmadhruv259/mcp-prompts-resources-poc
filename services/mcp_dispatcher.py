
"""Execute authorized MCP operations for custom AI agents."""

from typing import Any

from jsonschema import ValidationError, validate
from mcp import Client
from mcp.types import TextContent, TextResourceContents

from models.agent_config import AgentConfig
from services.mcp_discovery import MCPCapabilities
from tool_schemas import (
    MCP_TOOL_PREFIX,
    PROMPT_FUNCTION,
    RESOURCE_FUNCTION,
)


MAX_RESULT_CHARS = 40000
MAX_ERROR_CHARS = 1000


def validate_mcp_tool_access(
    agent: AgentConfig,
    tool_name: str,
    capabilities: MCPCapabilities,
) -> None:
    """Validate an agent's permission to execute an MCP tool.

    Args:
        agent (AgentConfig): Selected custom AI agent.
        tool_name (str): Native MCP tool name.
        capabilities (MCPCapabilities): Discovered MCP capabilities.

    Returns:
        None: The tool is available and permitted.

    Raises:
        ValueError: If the tool is unknown or unauthorized.
    """
    available_tools = {
        tool.name for tool in capabilities.tools
    }

    if tool_name not in available_tools:
        raise ValueError(
            f"Unknown MCP tool: {tool_name}"
        )

    if (
        agent.tool_access == "selected"
        and tool_name not in agent.allowed_tools
    ):
        raise ValueError(
            f"Agent is not allowed to execute: {tool_name}"
        )


def extract_text_content(items: list[Any]) -> str:
    """Extract text from MCP content objects.

    Args:
        items (list[Any]): MCP response content items.

    Returns:
        str: Combined textual content.

    Raises:
        ValueError: If the response has no text or exceeds the limit.
    """
    parts: list[str] = []

    for item in items:
        if isinstance(
            item,
            (TextContent, TextResourceContents),
        ):
            parts.append(item.text)

    if not parts:
        raise ValueError(
            "MCP operation returned no text content."
        )

    result = "\n".join(parts)

    if len(result) > MAX_RESULT_CHARS:
        raise ValueError(
            "MCP result exceeds the maximum context size."
        )

    return result


def extract_mcp_error(items: list[Any]) -> str:
    """Extract a concise error message from an MCP response.

    Args:
        items (list[Any]): MCP error content items.

    Returns:
        str: Error details or a fallback message.

    Raises:
        None: Missing text content is handled safely.
    """
    details = "\n".join(
        item.text
        for item in items
        if isinstance(item, TextContent)
        and item.text
    )

    return (
        details[:MAX_ERROR_CHARS]
        if details
        else "No details returned by the MCP server."
    )


async def execute_mcp_operation(
    client: Client,
    agent: AgentConfig,
    capabilities: MCPCapabilities,
    function_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute an authorized MCP tool, resource, or prompt.

    Args:
        client (Client): Connected MCP client.
        agent (AgentConfig): Selected custom AI agent.
        capabilities (MCPCapabilities): Discovered MCP capabilities.
        function_name (str): Groq function name.
        arguments (dict[str, Any]): Function arguments.

    Returns:
        str: Text returned by the MCP operation.

    Raises:
        ValueError: If the operation or arguments are invalid.
        RuntimeError: If the MCP server reports a tool failure.
    """
    if not isinstance(arguments, dict):
        raise ValueError(
            "MCP arguments must be a JSON object."
        )

    # 1. Execute a native MCP tool.
    if function_name.startswith(MCP_TOOL_PREFIX):
        tool_name = function_name[len(MCP_TOOL_PREFIX):]

        validate_mcp_tool_access(
            agent=agent,
            tool_name=tool_name,
            capabilities=capabilities,
        )

        tool_info = next(
            tool
            for tool in capabilities.tools
            if tool.name == tool_name
        )

        # Validate arguments against the MCP tool schema.
        try:
            validate(
                instance=arguments,
                schema=tool_info.input_schema or {
                    "type": "object",
                    "properties": {},
                },
            )
        except ValidationError as exc:
            raise ValueError(
                f"Invalid arguments for {tool_name}: "
                f"{exc.message}"
            ) from exc

        result = await client.call_tool(
            tool_name,
            arguments,
        )

        # The installed MCP client uses is_error,
        # not isError.
        if result.is_error:
            error_details = extract_mcp_error(
                result.content
            )

            raise RuntimeError(
                f"MCP tool execution failed: {tool_name}. "
                f"Details: {error_details}"
            )

        return extract_text_content(
            result.content
        )

    # 2. Read an MCP resource.
    if function_name == RESOURCE_FUNCTION:
        uri = arguments.get("uri")

        if (
            not isinstance(uri, str)
            or set(arguments) != {"uri"}
        ):
            raise ValueError(
                "Resource operation requires only a URI."
            )

        available_uris = {
            str(resource.uri)
            for resource in capabilities.resources
        }

        if uri not in available_uris:
            raise ValueError(
                f"Unknown MCP resource: {uri}"
            )

        result = await client.read_resource(uri)

        return extract_text_content(
            result.contents
        )

    # 3. Retrieve an MCP prompt.
    if function_name == PROMPT_FUNCTION:
        name = arguments.get("name")

        if not isinstance(name, str):
            raise ValueError(
                "Prompt name must be a string."
            )

        available_prompts = {
            prompt.name: prompt
            for prompt in capabilities.prompts
        }

        if name not in available_prompts:
            raise ValueError(
                f"Unknown MCP prompt: {name}"
            )

        prompt = available_prompts[name]

        # MCP discovery stores argument names as strings.
        allowed_arguments = set(
            prompt.arguments or []
        )

        prompt_arguments = {
            key: value
            for key, value in arguments.items()
            if key != "name"
        }

        # Reject arguments not declared by the MCP prompt.
        if set(prompt_arguments) - allowed_arguments:
            raise ValueError(
                "Unsupported MCP prompt arguments."
            )

        # MCP prompt arguments must contain string values.
        if any(
            not isinstance(value, str)
            for value in prompt_arguments.values()
        ):
            raise ValueError(
                "MCP prompt arguments must be strings."
            )

        result = await client.get_prompt(
            name,
            prompt_arguments,
        )

        contents = [
            message.content
            for message in result.messages
        ]

        return extract_text_content(contents)

    raise ValueError(
        f"Unknown MCP operation: {function_name}"
    )
