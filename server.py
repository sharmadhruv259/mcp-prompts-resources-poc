"""Expose sample project knowledge and reusable prompts through MCP."""

from pathlib import Path

from mcp.server import MCPServer


mcp = MCPServer("Project Knowledge POC")
DATA_DIR = Path(__file__).resolve().parent / "data"


@mcp.resource("project://requirements", mime_type="text/markdown")
def project_requirements() -> str:
    """Read the example project's functional requirements.

    Returns:
        str: Current Markdown requirements document.

    Raises:
        OSError: If the document cannot be read.
    """
    return (DATA_DIR / "requirements.md").read_text(encoding="utf-8")


@mcp.resource("project://architecture", mime_type="text/markdown")
def project_architecture() -> str:
    """Read the example project's technical architecture.

    Returns:
        str: Current Markdown architecture document.

    Raises:
        OSError: If the document cannot be read.
    """
    return (DATA_DIR / "architecture.md").read_text(encoding="utf-8")


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


if __name__ == "__main__":
    mcp.run()  # stdio transport; the client launches this subprocess.
