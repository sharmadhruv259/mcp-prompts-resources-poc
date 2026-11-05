
"""Persist administrator-managed MCP tool configurations in PostgreSQL."""

import os
from pathlib import Path

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.connection import SessionLocal
from database.models import ManagedToolModel
from models.tool_config import ToolKind, ToolRecord


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

DEFAULT_DB_PATH = Path("data/agents.db")

DEFAULT_TOOLS = [
    {
        "name": "get_project_overview",
        "description": "Read the project overview.",
        "handler": "get_project_overview",
        "kind": "read",
        "enabled": True,
        "built_in": True,
        "deleted": False,
    },
    {
        "name": "read_mcp_resource",
        "description": "Read an authorized MCP resource.",
        "handler": "read_mcp_resource",
        "kind": "read",
        "enabled": True,
        "built_in": True,
        "deleted": False,
    },
    {
        "name": "get_mcp_prompt",
        "description": "Retrieve an authorized MCP prompt.",
        "handler": "get_mcp_prompt",
        "kind": "read",
        "enabled": True,
        "built_in": True,
        "deleted": False,
    },
    {
        "name": "read_project_note",
        "description": "Read a stored project note.",
        "handler": "read_project_note",
        "kind": "read",
        "enabled": True,
        "built_in": True,
        "deleted": False,
    },
    {
        "name": "write_project_note",
        "description": "Create or update a project note.",
        "handler": "write_project_note",
        "kind": "write",
        "enabled": True,
        "built_in": True,
        "deleted": False,
    },
]


class ToolRegistry:
    """Manage persistent MCP tool configurations in PostgreSQL.

    Attributes:
        db_path (Path): Legacy SQLite path retained for compatibility.
        session_factory (sessionmaker): PostgreSQL session factory.

    Functions:
        initialize_defaults: Seed missing default tools explicitly.
        _to_record: Convert a database model into a ToolRecord.
        list_tools: Return registered, non-deleted tools.
        get_tool: Retrieve a non-deleted tool by name.
        create_tool: Register an approved custom handler.
        is_enabled: Check whether a tool is enabled.
        update_tool: Update editable tool fields.
        set_enabled: Change tool availability.
        delete_tool: Soft-delete a custom tool.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        session_factory: sessionmaker = SessionLocal,
    ) -> None:
        """Initialize the PostgreSQL tool registry without database writes.

        Args:
            db_path (str | Path): Legacy SQLite path, no longer used.
            session_factory (sessionmaker): SQLAlchemy session factory.

        Returns:
            None: Initializes the registry instance.

        Raises:
            TypeError: If an invalid database path is supplied.
        """
        self.db_path = Path(db_path)
        self.session_factory = session_factory

    def initialize_defaults(self) -> None:
        """Insert missing default tools without modifying existing records.

        Args:
            None.

        Returns:
            None: Missing default tools are inserted.

        Raises:
            SQLAlchemyError: If database initialization fails.
        """
        with self.session_factory.begin() as session:
            statement = (
                insert(ManagedToolModel)
                .values(DEFAULT_TOOLS)
                .on_conflict_do_nothing(
                    index_elements=[ManagedToolModel.name]
                )
            )
            session.execute(statement)

    @staticmethod
    def _to_record(model: ManagedToolModel) -> ToolRecord:
        """Convert a stored PostgreSQL model into a validated tool record.

        Args:
            model (ManagedToolModel): Stored tool configuration.

        Returns:
            ToolRecord: Validated MCP tool configuration.

        Raises:
            ValueError: If stored data is invalid.
        """
        return ToolRecord(
            name=model.name,
            description=model.description,
            handler=model.handler,
            kind=model.kind,
            enabled=model.enabled,
            built_in=model.built_in,
            deleted=model.deleted,
        )

    def list_tools(self) -> list[ToolRecord]:
        """List all non-deleted tool configurations.

        Args:
            None.

        Returns:
            list[ToolRecord]: Registered tools ordered by name.

        Raises:
            SQLAlchemyError: If database retrieval fails.
        """
        with self.session_factory() as session:
            models = session.scalars(
                select(ManagedToolModel)
                .where(ManagedToolModel.deleted.is_(False))
                .order_by(ManagedToolModel.name.asc())
            ).all()

            return [
                self._to_record(model)
                for model in models
            ]

    def get_tool(self, name: str) -> ToolRecord | None:
        """Retrieve a non-deleted tool by name.

        Args:
            name (str): Registered tool name.

        Returns:
            ToolRecord | None: Tool record or None if unavailable.

        Raises:
            SQLAlchemyError: If database retrieval fails.
        """
        with self.session_factory() as session:
            model = session.scalar(
                select(ManagedToolModel).where(
                    ManagedToolModel.name == name,
                    ManagedToolModel.deleted.is_(False),
                )
            )

            return self._to_record(model) if model else None

    def create_tool(
        self,
        name: str,
        description: str,
        handler: str,
        kind: ToolKind,
    ) -> ToolRecord:
        """Create a disabled custom tool using an approved handler.

        Args:
            name (str): New tool name.
            description (str): Tool description.
            handler (str): Approved backend handler.
            kind (ToolKind): Handler classification.

        Returns:
            ToolRecord: Newly registered disabled tool.

        Raises:
            ValueError: If the handler is unsupported, reserved,
                incorrectly classified, or already registered.
            SQLAlchemyError: If database persistence fails.
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

        try:
            with self.session_factory.begin() as session:
                existing = session.scalar(
                    select(ManagedToolModel.name)
                    .where(
                        or_(
                            ManagedToolModel.name == name,
                            ManagedToolModel.handler == handler,
                        )
                    )
                    .limit(1)
                )

                if existing is not None:
                    raise ValueError(
                        "Tool name or handler is already registered."
                    )

                session.add(
                    ManagedToolModel(
                        name=name,
                        description=description,
                        handler=handler,
                        kind=kind,
                        enabled=False,
                        built_in=False,
                        deleted=False,
                    )
                )

        except IntegrityError as exc:
            raise ValueError(
                "Tool name or handler is already registered."
            ) from exc

        return self.get_tool(name)

    def is_enabled(self, name: str) -> bool:
        """Check whether an MCP operation is currently enabled.

        Args:
            name (str): Registered operation name.

        Returns:
            bool: True if the tool exists, is enabled, and is not deleted.

        Raises:
            SQLAlchemyError: If database retrieval fails.
        """
        with self.session_factory() as session:
            enabled = session.scalar(
                select(ManagedToolModel.enabled).where(
                    ManagedToolModel.name == name,
                    ManagedToolModel.deleted.is_(False),
                )
            )

            return enabled is True

    def update_tool(
        self,
        name: str,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> ToolRecord | None:
        """Update a registered tool's editable fields.

        Args:
            name (str): Existing tool name.
            description (str | None): Optional new description.
            enabled (bool | None): Optional enabled status.

        Returns:
            ToolRecord | None: Updated tool or None if unavailable.

        Raises:
            SQLAlchemyError: If database persistence fails.
        """
        values = {}

        if description is not None:
            values["description"] = description

        if enabled is not None:
            values["enabled"] = enabled

        if not values:
            return self.get_tool(name)

        with self.session_factory.begin() as session:
            result = session.execute(
                update(ManagedToolModel)
                .where(
                    ManagedToolModel.name == name,
                    ManagedToolModel.deleted.is_(False),
                )
                .values(**values)
            )

            changed = result.rowcount == 1

        if not changed:
            return None

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
            ToolRecord | None: Updated tool or None if unavailable.

        Raises:
            SQLAlchemyError: If database persistence fails.
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
            bool: True if a custom tool was deleted, otherwise False.

        Raises:
            ValueError: If the tool is built-in.
            SQLAlchemyError: If database persistence fails.
        """
        with self.session_factory.begin() as session:
            model = session.scalar(
                select(ManagedToolModel)
                .where(
                    ManagedToolModel.name == name,
                    ManagedToolModel.deleted.is_(False),
                )
                .with_for_update()
            )

            if model is None:
                return False

            if model.built_in:
                raise ValueError(
                    "Built-in tools cannot be deleted. "
                    "Disable them instead."
                )

            model.deleted = True
            model.enabled = False

        return True


# Creating the registry does not access or modify PostgreSQL.
tool_registry = ToolRegistry()
