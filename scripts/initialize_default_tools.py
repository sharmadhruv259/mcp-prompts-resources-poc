
"""Initialize default MCP tools in PostgreSQL."""

from services.tool_registry import ToolRegistry


def main() -> None:
    """Initialize missing default MCP tools.

    Args:
        None.

    Returns:
        None: Missing default tools are initialized.

    Raises:
        SQLAlchemyError: If PostgreSQL initialization fails.
    """
    registry = ToolRegistry()
    registry.initialize_defaults()
    print("Default MCP tools initialized successfully.")


if __name__ == "__main__":
    main()
