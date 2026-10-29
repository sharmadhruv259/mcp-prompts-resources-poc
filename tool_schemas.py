
"""Build Groq function schemas dynamically from MCP capabilities."""

from typing import Any

from models.agent_config import AgentConfig
from services.mcp_discovery import MCPCapabilities


MCP_TOOL_PREFIX = "mcp_tool__"
RESOURCE_FUNCTION = "read_mcp_resource"
PROMPT_FUNCTION = "get_mcp_prompt"


def build_agent_tool_schemas(
    capabilities: MCPCapabilities,
    agent: AgentConfig,
) -> list[dict[str, Any]]:
    """Build Groq-compatible function schemas from discovered MCP capabilities.

    Args:
        capabilities (MCPCapabilities): Discovered MCP tools, resources,
            and prompts.
        agent (AgentConfig): Agent configuration containing tool permissions.

    Returns:
        list[dict[str, Any]]: Function schemas available to the Groq agent.

    Raises:
        ValueError: If the agent selects unavailable MCP tools.
    """
    available_tools = {
        tool.name for tool in capabilities.tools
    }

    if agent.tool_access == "selected":
        unknown_tools = set(agent.allowed_tools) - available_tools

        if unknown_tools:
            raise ValueError(
                "Unknown or unavailable MCP tools: "
                + ", ".join(sorted(unknown_tools))
            )

    schemas: list[dict[str, Any]] = []

    # Native MCP tools: reuse their discovered input schemas.
    for tool in capabilities.tools:
        if (
            agent.tool_access == "selected"
            and tool.name not in agent.allowed_tools
        ):
            continue

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": f"{MCP_TOOL_PREFIX}{tool.name}",
                    "description": (
                        tool.description.split("\n\n")[0]
                        or f"Execute MCP tool {tool.name}"
                    ),
                    "parameters": tool.input_schema or {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        )

    # MCP resources: generate the allowed URI values dynamically.
    resource_uris = [
        resource.uri for resource in capabilities.resources
    ]

    if resource_uris:
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": RESOURCE_FUNCTION,
                    "description": (
                        "Read an available MCP resource to retrieve "
                        "project information."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "uri": {
                                "type": "string",
                                "enum": resource_uris,
                                "description": "MCP resource URI.",
                            },
                        },
                        "required": ["uri"],
                    },
                },
            }
        )

    # MCP prompts: discover argument names instead of hardcoding them.
    prompt_names = [
        prompt.name for prompt in capabilities.prompts
    ]

    if prompt_names:
        prompt_argument_names = sorted(
            {
                argument_name
                for prompt in capabilities.prompts
                for argument_name in prompt.arguments
            }
        )

        prompt_properties: dict[str, Any] = {
            "name": {
                "type": "string",
                "enum": prompt_names,
                "description": "Name of the MCP prompt.",
            }
        }

        for argument_name in prompt_argument_names:
            if argument_name == "name":
                raise ValueError(
                    "MCP prompt argument 'name' conflicts "
                    "with the prompt selector."
                )

            prompt_properties[argument_name] = {
                "type": "string",
                "description": (
                    f"Argument '{argument_name}' for an MCP prompt. "
                    "Provide only when supported by the selected prompt."
                ),
            }

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": PROMPT_FUNCTION,
                    "description": (
                        "Retrieve a reusable MCP prompt. "
                        "Select a discovered prompt name and supply "
                        "only its supported arguments."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": prompt_properties,
                        "required": ["name"],
                    },
                },
            }
        )

    return schemas
