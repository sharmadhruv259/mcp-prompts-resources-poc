
"""Persist administrator-managed MCP tool configurations."""

import os
import sqlite3
from pathlib import Path

from models.tool_config import ToolRecord, ToolKind


# Only backend-approved handlers may be registered.
APPROVED_HANDLERS: dict[str, ToolKind] = {
    "get_project_overview": "read",
    "read_project_note": "read",
    "write_project_note": "write",
    "read_mcp_resource": "read",
    "get_mcp_prompt": "read",
}

BUILT_IN_HANDLERS = {
    "get_project_overview",
    "read_mcp_resource",
    "get_mcp_prompt",
}


class ToolRegistry:
    """Manage persistent MCP tool configurations.

    Attributes:
        db_path (Path): SQLite database location.

    Functions:
        _initialize: Create and seed the tool registry.
        list_tools: Return registered tools.
        get_tool: Retrieve a tool by name.
        create_tool: Register an approved handler.
        update_tool: Update editable fields.
        set_enabled: Change tool availability.
        delete_tool: Soft-delete a custom tool.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the persistent registry.

        Args:
            db_path (str | Path): SQLite database path.

        Returns:
            None: Initializes registry storage.

        Raises:
            sqlite3.Error: If initialization fails.
            OSError: If the parent directory cannot be created.
        """
        self.db_path = Path(db_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with dictionary-like rows.

        Args:
            None.

        Returns:
            sqlite3.Connection: Configured database connection.

        Raises:
            sqlite3.Error: If the connection fails.
        """
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        """Create the registry and seed system tools.

        Args:
            None.

        Returns:
            None: Registry schema and defaults are initialized.

        Raises:
            sqlite3.Error: If database initialization fails.
        """
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS managed_tools (
                    name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    handler TEXT NOT NULL,
                    kind TEXT NOT NULL
                        CHECK(kind IN ('read', 'write')),
                    enabled INTEGER NOT NULL DEFAULT 1
                        CHECK(enabled IN (0, 1)),
                    built_in INTEGER NOT NULL DEFAULT 0
                        CHECK(built_in IN (0, 1)),
                    deleted INTEGER NOT NULL DEFAULT 0
                        CHECK(deleted IN (0, 1))
                )
                """
            )

            defaults = [
                (
                    "get_project_overview",
                    "Read the project overview.",
                    "get_project_overview",
                    "read",
                    1,
                    1,
                ),
                (
                    "read_mcp_resource",
                    "Read an authorized MCP resource.",
                    "read_mcp_resource",
                    "read",
                    1,
                    1,
                ),
                (
                    "get_mcp_prompt",
                    "Retrieve an authorized MCP prompt.",
                    "get_mcp_prompt",
                    "read",
                    1,
                    1,
                ),
                (
                    "read_project_note",
                    "Read a stored project note.",
                    "read_project_note",
                    "read",
                    1,
                    1,
                ),
                (
                    "write_project_note",
                    "Create or update a project note.",
                    "write_project_note",
                    "write",
                    1,
                    1,
                ),
            ]

            connection.executemany(
                """
                INSERT OR IGNORE INTO managed_tools (
                    name,
                    description,
                    handler,
                    kind,
                    enabled,
                    built_in
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                defaults,
            )

    @staticmethod
    def _to_record(row: sqlite3.Row) -> ToolRecord:
        """Convert a database row into a tool model.

        Args:
            row (sqlite3.Row): Stored tool row.

        Returns:
            ToolRecord: Validated tool configuration.

        Raises:
            ValueError: If stored data is invalid.
        """
        return ToolRecord(
            name=row["name"],
            description=row["description"],
            handler=row["handler"],
            kind=row["kind"],
            enabled=bool(row["enabled"]),
            built_in=bool(row["built_in"]),
            deleted=bool(row["deleted"]),
        )

    def list_tools(self) -> list[ToolRecord]:
        """List all non-deleted tool configurations.

        Args:
            None.

        Returns:
            list[ToolRecord]: Registered tools.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM managed_tools
                WHERE deleted = 0
                ORDER BY name
                """
            ).fetchall()

        return [self._to_record(row) for row in rows]

    def get_tool(self, name: str) -> ToolRecord | None:
        """Retrieve an active registry record by name.

        Args:
            name (str): Tool name.

        Returns:
            ToolRecord | None: Tool or None if unavailable.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM managed_tools
                WHERE name = ? AND deleted = 0
                """,
                (name,),
            ).fetchone()

        return self._to_record(row) if row else None

    def create_tool(
        self,
        name: str,
        description: str,
        handler: str,
        kind: ToolKind,
    ) -> ToolRecord:
        """Create a configuration for an approved handler.

        Args:
            name (str): New tool name.
            description (str): Tool description.
            handler (str): Approved backend handler.
            kind (ToolKind): Handler classification.

        Returns:
            ToolRecord: Newly registered disabled tool.

        Raises:
            ValueError: If the handler is unsupported or duplicated.
            sqlite3.Error: If persistence fails.
        """
        if handler not in APPROVED_HANDLERS:
            raise ValueError(
                "Handler is not in the approved backend registry."
            )

        if APPROVED_HANDLERS[handler] != kind:
            raise ValueError(
                "Tool classification does not match its handler."
            )

        if handler in BUILT_IN_HANDLERS:
            raise ValueError(
                "Built-in handlers cannot be registered as custom tools."
            )

        if name in APPROVED_HANDLERS:
            raise ValueError(
                "This name is reserved for a built-in operation."
            )

        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT name FROM managed_tools
                WHERE name = ? OR handler = ?
                """,
                (name, handler),
            ).fetchone()

            if existing:
                raise ValueError(
                    "Tool name or handler is already registered."
                )

            connection.execute(
                """
                INSERT INTO managed_tools (
                    name, description, handler, kind,
                    enabled, built_in, deleted
                )
                VALUES (?, ?, ?, ?, 0, 0, 0)
                """,
                (name, description, handler, kind),
            )

        return self.get_tool(name)

    
    def is_enabled(self, name: str) -> bool:
        """Check whether an MCP operation is currently enabled.

        Args:
            name (str): Registered operation name.

        Returns:
            bool: True if the operation exists, is enabled,
                and has not been deleted.

        Raises:
            sqlite3.Error: If the database query fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT enabled
                FROM managed_tools
                WHERE name = ?
                  AND deleted = 0
                """,
                (name,),
            ).fetchone()

        return row is not None and bool(row["enabled"])


    def update_tool(
        self,
        name: str,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> ToolRecord | None:
        """Update a registered tool's editable fields.

        Args:
            name (str): Existing tool name.
            description (str | None): Optional description.
            enabled (bool | None): Optional enabled status.

        Returns:
            ToolRecord | None: Updated tool or None.

        Raises:
            sqlite3.Error: If persistence fails.
        """
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE managed_tools
                SET
                    description = COALESCE(?, description),
                    enabled = COALESCE(?, enabled)
                WHERE name = ? AND deleted = 0
                """,
                (
                    description,
                    int(enabled) if enabled is not None else None,
                    name,
                ),
            )

        return self.get_tool(name)

    def set_enabled(
        self,
        name: str,
        enabled: bool,
    ) -> ToolRecord | None:
        """Enable or disable a registered tool.

        Args:
            name (str): Registered tool name.
            enabled (bool): Desired availability.

        Returns:
            ToolRecord | None: Updated tool or None.

        Raises:
            sqlite3.Error: If persistence fails.
        """
        return self.update_tool(
            name=name,
            enabled=enabled,
        )

    def delete_tool(self, name: str) -> bool:
        """Soft-delete a custom tool configuration.

        Args:
            name (str): Tool to delete.

        Returns:
            bool: True if a custom tool was deleted.

        Raises:
            ValueError: If the tool is built-in.
            sqlite3.Error: If persistence fails.
        """
        tool = self.get_tool(name)

        if tool is None:
            return False

        if tool.built_in:
            raise ValueError(
                "Built-in tools cannot be deleted. Disable them instead."
            )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE managed_tools
                SET deleted = 1, enabled = 0
                WHERE name = ?
                    AND built_in = 0
                    AND deleted = 0
                """,
                (name,),
            )

        return cursor.rowcount > 0


tool_registry = ToolRegistry(
    db_path=os.getenv("DATABASE_PATH", "data/agents.db")
)
