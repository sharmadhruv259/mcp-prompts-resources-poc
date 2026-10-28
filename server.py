from mcp.server import MCPServer

from prompts import register_prompts
from constants.paths import (
    ARCHITECTURE_PATH,
    ARCHITECTURE_URI,
    REQUIREMENTS_PATH,
    REQUIREMENTS_URI,
)

mcp = MCPServer("Project Knowledge POC")


@mcp.resource(REQUIREMENTS_URI, mime_type="text/markdown")
def project_requirements() -> str:
    """Read the example project's functional requirements.

    Returns:
        str: Current Markdown requirements document.

    Raises:
        OSError: If the document cannot be read.
    """
    return REQUIREMENTS_PATH.read_text(encoding="utf-8")


@mcp.resource(ARCHITECTURE_URI, mime_type="text/markdown")
def project_architecture() -> str:
    """Read the example project's technical architecture.

    Returns:
        str: Current Markdown architecture document.

    Raises:
        OSError: If the document cannot be read.
    """
    return ARCHITECTURE_PATH.read_text(encoding="utf-8")
register_prompts(mcp)


if __name__ == "__main__":
    mcp.run()  # stdio transport; the client launches this subprocess.
