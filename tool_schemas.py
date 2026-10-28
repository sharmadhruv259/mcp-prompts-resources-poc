
"""Build Groq function-calling schemas from MCP discovery results."""

from typing import Any


def build_tool_schemas(
    resource_uris: list[str],
    prompt_names: list[str],
) -> list[dict[str, Any]]:
    """Build Groq tool schemas from MCP discovery results.

    Args:
        resource_uris (list[str]): Available resource URIs.
        prompt_names (list[str]): Available MCP prompt names.

    Returns:
        list[dict[str, Any]]: Tool schemas for Groq.

    Raises:
        ValueError: If resources or prompts are unavailable.
    """
    if not resource_uris or not prompt_names:
        raise ValueError(
            "MCP server must expose at least one resource and prompt."
        )

    return [
        {
            "type": "function",
            "function": {
                "name": "read_mcp_resource",
                "description": (
                    "Read project documentation from the MCP server. "
                    "Choose the resource relevant to the user's question. "
                    "Read multiple resources if needed."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "enum": resource_uris,
                            "description": "Resource URI to read.",
                        }
                    },
                    "required": ["uri"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_mcp_prompt",
                "description": (
                    "Retrieve reusable task instructions from the "
                    "MCP server. Select a prompt based on the user's "
                    "requested task."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "enum": prompt_names,
                            "description": "MCP prompt name.",
                        },
                        "audience": {
                            "type": "string",
                            "description": (
                                "Intended audience, such as manager "
                                "or developer."
                            ),
                        },
                    },
                    "required": ["name", "audience"],
                },
            },
        },
    ]
