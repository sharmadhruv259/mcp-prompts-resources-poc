
"""Build Groq function schemas dynamically from authorized MCP capabilities."""

from typing import Any

from models.agent_config import AgentConfig
from services.mcp_discovery import (
    MCPCapabilities,
    filter_enabled_capabilities,
)
from services.tool_registry import tool_registry


MCP_TOOL_PREFIX = "mcp_tool__"
RESOURCE_FUNCTION = "read_mcp_resource"
PROMPT_FUNCTION = "get_mcp_prompt"


def build_agent_tool_schemas(
    capabilities: MCPCapabilities,
    agent: AgentConfig,
) -> list[dict[str, Any]]:
    """Build Groq-compatible schemas for enabled and authorized MCP capabilities.

    Args:
        capabilities (MCPCapabilities): Discovered MCP tools,
            resources, and prompts before Admin filtering.
        agent (AgentConfig): Agent configuration and permissions.

    Returns:
        list[dict[str, Any]]: Groq function schemas for enabled
            capabilities authorized for the agent.

    Raises:
        ValueError: If the agent references unknown MCP tools,
            resources, or prompts, or if an MCP prompt argument
            conflicts with the prompt selector.
        SQLAlchemyError: If the Tool Registry cannot be queried.
    """
    # ---------------------------------------------------------
    # 1. Validate against raw MCP discovery.
    # ---------------------------------------------------------
    # Admin-disabled capabilities still exist in MCP discovery.
    # They must not be treated as unknown capabilities.

    available_tools = {
        tool.name for tool in capabilities.tools
    }

    available_resources = {
        str(resource.uri)
        for resource in capabilities.resources
    }

    available_prompts = {
        prompt.name for prompt in capabilities.prompts
    }

    # Reject genuinely unknown selected tools.
    if agent.tool_access == "selected":
        unknown_tools = (
            set(agent.allowed_tools) - available_tools
        )

        if unknown_tools:
            raise ValueError(
                "Unknown or unavailable MCP tools: "
                + ", ".join(sorted(unknown_tools))
            )

    # Reject genuinely unknown resources.
    unknown_resources = (
        set(agent.allowed_resources) - available_resources
    )

    if unknown_resources:
        raise ValueError(
            "Unknown or unavailable MCP resources: "
            + ", ".join(sorted(unknown_resources))
        )

    # Reject genuinely unknown prompts.
    unknown_prompts = (
        set(agent.allowed_prompts) - available_prompts
    )

    if unknown_prompts:
        raise ValueError(
            "Unknown or unavailable MCP prompts: "
            + ", ".join(sorted(unknown_prompts))
        )

    # ---------------------------------------------------------
    # 2. Apply global Admin enable/disable settings.
    # ---------------------------------------------------------
    # Only enabled tools, resources, and prompts are exposed
    # to Groq. Disabled capabilities are silently excluded.

    capabilities = filter_enabled_capabilities(
        capabilities,
        tool_registry,
    )

    schemas: list[dict[str, Any]] = []

    # ---------------------------------------------------------
    # 3. Native MCP tools.
    # ---------------------------------------------------------
    for tool in capabilities.tools:

        # Preserve per-agent tool restrictions.
        if (
            agent.tool_access == "selected"
            and tool.name not in agent.allowed_tools
        ):
            continue

        description = tool.description or ""

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": f"{MCP_TOOL_PREFIX}{tool.name}",
                    "description": (
                        description.split("\n\n")[0]
                        or f"Execute MCP tool {tool.name}"
                    ),
                    "parameters": tool.input_schema or {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        )

    # ---------------------------------------------------------
    # 4. Authorized MCP resources.
    # ---------------------------------------------------------
    resource_uris = [
        str(resource.uri)
        for resource in capabilities.resources
        if str(resource.uri) in agent.allowed_resources
    ]

    if resource_uris:
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": RESOURCE_FUNCTION,
                    "description": (
                        "Read an authorized MCP resource to "
                        "retrieve project information."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "uri": {
                                "type": "string",
                                "enum": resource_uris,
                                "description": (
                                    "Authorized MCP resource URI."
                                ),
                            }
                        },
                        "required": ["uri"],
                    },
                },
            }
        )

    # ---------------------------------------------------------
    # 5. Authorized MCP prompts.
    # ---------------------------------------------------------
    authorized_prompts = [
        prompt
        for prompt in capabilities.prompts
        if prompt.name in agent.allowed_prompts
    ]

    if authorized_prompts:
        prompt_names = [
            prompt.name for prompt in authorized_prompts
        ]

        prompt_argument_names: set[str] = set()

        for prompt in authorized_prompts:
            for argument in prompt.arguments or []:
                argument_name = (
                    argument
                    if isinstance(argument, str)
                    else argument.name
                )

                if argument_name == "name":
                    raise ValueError(
                        "MCP prompt argument 'name' conflicts "
                        "with the prompt selector."
                    )

                prompt_argument_names.add(argument_name)

        prompt_properties: dict[str, Any] = {
            "name": {
                "type": "string",
                "enum": prompt_names,
                "description": "Authorized MCP prompt name.",
            }
        }

        for argument_name in sorted(prompt_argument_names):
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
                        "Retrieve an authorized MCP prompt. "
                        "Provide only its supported arguments."
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
