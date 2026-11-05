
"""Execute authorized and Admin-enabled MCP operations for custom AI agents."""

from typing import Any

from jsonschema import ValidationError, validate
from mcp import Client
from mcp.types import TextContent, TextResourceContents

from models.agent_config import AgentConfig
from services.mcp_discovery import MCPCapabilities
from services.tool_registry import tool_registry
from tool_schemas import (
    MCP_TOOL_PREFIX,
    PROMPT_FUNCTION,
    RESOURCE_FUNCTION,
)


MAX_RESULT_CHARS = 40000
MAX_ERROR_CHARS = 1000


def require_enabled_operation(operation_name: str) -> None:
    """Reject an MCP operation disabled by an administrator.

    Args:
        operation_name (str): Registered MCP operation name.

    Returns:
        None: The operation is enabled.

    Raises:
        ValueError: If the operation is disabled, deleted,
            or not registered.
        SQLAlchemyError: If the Tool Registry cannot be queried.
    """
    if not tool_registry.is_enabled(operation_name):
        raise ValueError(
            "MCP operation is disabled or unavailable: "
            f"{operation_name}"
        )


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


def validate_mcp_resource_access(
    agent: AgentConfig,
    uri: str,
    capabilities: MCPCapabilities,
) -> None:
    """Validate an agent's permission to read an MCP resource.

    Args:
        agent (AgentConfig): Selected agent configuration.
        uri (str): Requested MCP resource URI.
        capabilities (MCPCapabilities): Discovered capabilities.

    Returns:
        None: Resource exists and access is permitted.

    Raises:
        ValueError: If the resource is unknown or unauthorized.
    """
    available_uris = {
        str(resource.uri)
        for resource in capabilities.resources
    }

    if uri not in available_uris:
        raise ValueError(
            f"Unknown MCP resource: {uri}"
        )

    if uri not in agent.allowed_resources:
        raise ValueError(
            "Agent is not allowed to read this MCP resource."
        )


def validate_mcp_prompt_access(
    agent: AgentConfig,
    name: str,
    capabilities: MCPCapabilities,
) -> None:
    """Validate an agent's permission to retrieve an MCP prompt.

    Args:
        agent (AgentConfig): Selected agent configuration.
        name (str): Requested MCP prompt name.
        capabilities (MCPCapabilities): Discovered capabilities.

    Returns:
        None: Prompt exists and access is permitted.

    Raises:
        ValueError: If the prompt is unknown or unauthorized.
    """
    available_names = {
        prompt.name
        for prompt in capabilities.prompts
    }

    if name not in available_names:
        raise ValueError(
            f"Unknown MCP prompt: {name}"
        )

    if name not in agent.allowed_prompts:
        raise ValueError(
            "Agent is not allowed to retrieve this MCP prompt."
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
    """Execute an authorized and Admin-enabled MCP operation.

    Args:
        client (Client): Connected MCP client.
        agent (AgentConfig): Selected custom AI agent.
        capabilities (MCPCapabilities): Discovered MCP capabilities.
        function_name (str): Groq function name.
        arguments (dict[str, Any]): Function arguments.

    Returns:
        str: Text returned by the MCP operation.

    Raises:
        ValueError: If the operation is disabled, unauthorized,
            unknown, or has invalid arguments.
        RuntimeError: If the MCP server reports a tool failure.
        SQLAlchemyError: If the Tool Registry cannot be queried.
    """
    if not isinstance(arguments, dict):
        raise ValueError(
            "MCP arguments must be a JSON object."
        )

    # ---------------------------------------------------------
    # 1. Execute a native MCP tool.
    # ---------------------------------------------------------
    if function_name.startswith(MCP_TOOL_PREFIX):
        tool_name = function_name[len(MCP_TOOL_PREFIX):]

        # First verify the agent's access permissions.
        validate_mcp_tool_access(
            agent=agent,
            tool_name=tool_name,
            capabilities=capabilities,
        )

        # Then enforce the global Admin setting.
        require_enabled_operation(tool_name)

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

        # Recheck immediately before execution.
        require_enabled_operation(tool_name)

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

    # ---------------------------------------------------------
    # 2. Read an MCP resource.
    # ---------------------------------------------------------
    if function_name == RESOURCE_FUNCTION:
        # Check Admin enablement.
        require_enabled_operation(RESOURCE_FUNCTION)

        uri = arguments.get("uri")

        if (
            not isinstance(uri, str)
            or set(arguments) != {"uri"}
        ):
            raise ValueError(
                "Resource operation requires only a URI."
            )

        validate_mcp_resource_access(
            agent=agent,
            uri=uri,
            capabilities=capabilities,
        )

        # Recheck immediately before execution.
        require_enabled_operation(RESOURCE_FUNCTION)

        result = await client.read_resource(uri)

        return extract_text_content(
            result.contents
        )

    # ---------------------------------------------------------
    # 3. Retrieve an MCP prompt.
    # ---------------------------------------------------------
    if function_name == PROMPT_FUNCTION:
        # Check Admin enablement.
        require_enabled_operation(PROMPT_FUNCTION)

        name = arguments.get("name")

        if not isinstance(name, str):
            raise ValueError(
                "Prompt name must be a string."
            )

        available_prompts = {
            prompt.name: prompt
            for prompt in capabilities.prompts
        }

        validate_mcp_prompt_access(
            agent=agent,
            name=name,
            capabilities=capabilities,
        )

        prompt = available_prompts[name]

        # Extract supported and required MCP prompt arguments.
        allowed_arguments: set[str] = set()
        required_arguments: set[str] = set()

        for argument in prompt.arguments or []:
            if isinstance(argument, str):
                argument_name = argument
                is_required = False
            else:
                argument_name = argument.name
                is_required = bool(
                    getattr(argument, "required", False)
                )

            if argument_name == "name":
                raise ValueError(
                    "MCP prompt argument 'name' conflicts "
                    "with the prompt selector."
                )

            allowed_arguments.add(argument_name)

            if is_required:
                required_arguments.add(argument_name)

        prompt_arguments = {
            key: value
            for key, value in arguments.items()
            if key != "name"
        }

        # Reject arguments not declared by the MCP prompt.
        unknown_arguments = (
            set(prompt_arguments) - allowed_arguments
        )

        if unknown_arguments:
            raise ValueError(
                "Unsupported MCP prompt arguments: "
                + ", ".join(sorted(unknown_arguments))
            )

        # Reject missing required prompt arguments.
        missing_arguments = (
            required_arguments - set(prompt_arguments)
        )

        if missing_arguments:
            raise ValueError(
                "Missing required MCP prompt arguments: "
                + ", ".join(sorted(missing_arguments))
            )

        # All supplied prompt argument values must be strings.
        if any(
            not isinstance(value, str)
            for value in prompt_arguments.values()
        ):
            raise ValueError(
                "MCP prompt arguments must be strings."
            )

        # Recheck immediately before execution.
        require_enabled_operation(PROMPT_FUNCTION)

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
