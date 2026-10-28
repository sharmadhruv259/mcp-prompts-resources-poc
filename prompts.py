
"""Define and register reusable MCP project prompts."""

from mcp.server import MCPServer


def register_prompts(mcp: MCPServer) -> None:
    """Register project prompts with the MCP server.

    Args:
        mcp (MCPServer): MCP server instance to register prompts on.

    Returns:
        None: Registers the prompt definitions.

    Raises:
        None.
    """

    @mcp.prompt()
    def summarize_project(audience: str = "manager") -> str:
        """Create reusable project summarization instructions.

        Args:
            audience (str): Intended audience for the summary.

        Returns:
            str: Instructions for summarizing supplied project knowledge.

        Raises:
            ValueError: If the audience is empty.
        """
        if not audience.strip():
            raise ValueError("Audience cannot be empty")

        return (
            f"Summarize the project for a {audience}. "
            "Cover purpose, main features and key constraints. "
            "Use only the supplied project resource. "
            "If information is missing, say so. Keep the answer concise."
        )

    @mcp.prompt()
    def explain_technical(audience: str = "developer") -> str:
        """Create reusable technical explanation instructions.

        Args:
            audience (str): Intended audience for the explanation.

        Returns:
            str: Instructions for explaining supplied technical information.

        Raises:
            ValueError: If the audience is empty.
        """
        if not audience.strip():
            raise ValueError("Audience cannot be empty")

        return (
            f"Explain this project's technical details for a {audience}. "
            "Identify components and how they interact. "
            "Use only the supplied project resource; do not invent architecture. "
            "State when information is missing."
        )
