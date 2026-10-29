
"""Discover available MCP tools, resources, and prompts."""

from pydantic import BaseModel, Field
from mcp import Client


class MCPToolInfo(BaseModel):
    """Represent a discovered MCP tool.

    Attributes:
        name (str): MCP tool name.
        description (str): Tool description.
        input_schema (dict): Tool argument schema.

    Functions:
        None.
    """

    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)


class MCPResourceInfo(BaseModel):
    """Represent a discovered MCP resource.

    Attributes:
        uri (str): Resource URI.
        name (str): Resource name.
        description (str): Resource description.

    Functions:
        None.
    """

    uri: str
    name: str
    description: str = ""


class MCPPromptInfo(BaseModel):
    """Represent a discovered MCP prompt.

    Attributes:
        name (str): Prompt name.
        description (str): Prompt description.
        arguments (list[str]): Accepted prompt arguments.

    Functions:
        None.
    """

    name: str
    description: str = ""
    arguments: list[str] = Field(default_factory=list)


class MCPCapabilities(BaseModel):
    """Represent available MCP capabilities.

    Attributes:
        tools (list[MCPToolInfo]): Discovered MCP tools.
        resources (list[MCPResourceInfo]): Discovered resources.
        prompts (list[MCPPromptInfo]): Discovered prompts.

    Functions:
        None.
    """

    tools: list[MCPToolInfo] = Field(default_factory=list)
    resources: list[MCPResourceInfo] = Field(default_factory=list)
    prompts: list[MCPPromptInfo] = Field(default_factory=list)


async def discover_mcp_capabilities(
    client: Client,
) -> MCPCapabilities:
    """Discover tools, resources, and prompts from an MCP server.

    Args:
        client (Client): Connected MCP client.

    Returns:
        MCPCapabilities: Discovered MCP capabilities.

    Raises:
        Exception: If MCP capability discovery fails.
    """
    tools_result = await client.list_tools()
    resources_result = await client.list_resources()
    prompts_result = await client.list_prompts()

    tools = [
        MCPToolInfo(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.input_schema or {},
        )
        for tool in tools_result.tools
    ]

    resources = [
        MCPResourceInfo(
            uri=str(resource.uri),
            name=resource.name,
            description=resource.description or "",
        )
        for resource in resources_result.resources
    ]

    prompts = [
        MCPPromptInfo(
            name=prompt.name,
            description=prompt.description or "",
            arguments=[
                argument.name
                for argument in (prompt.arguments or [])
            ],
        )
        for prompt in prompts_result.prompts
    ]

    return MCPCapabilities(
        tools=tools,
        resources=resources,
        prompts=prompts,
    )
