
"""Persist custom AI agents with ownership and approval metadata."""

import sqlite3
from pathlib import Path
from typing import Literal

from models.agent_config import AgentConfig
from services.mcp_cache import mcp_cache


DEFAULT_DB_PATH = Path("data/agents.db")

AgentStatus = Literal[
    "draft",
    "pending",
    "approved",
    "rejected",
]


class AgentRegistry:
    """Manage agent configurations and approval metadata.

    Attributes:
        db_path (Path): SQLite database file location.

    Functions:
        _connect: Open a SQLite connection.
        _initialize: Create and migrate the agents table.
        create_agent: Save a new agent as a draft.
        get_agent: Retrieve an agent configuration.
        get_agent_record: Retrieve configuration and access metadata.
        list_agents: Retrieve saved configurations.
        list_agent_records: Retrieve agents with ownership metadata.
        update_agent: Update an owned agent with version checking.
        delete_agent: Delete an agent.
        submit_agent: Submit an owned draft for review.
        approve_agent: Approve a pending agent.
        reject_agent: Reject a pending agent.
    """

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
    ) -> None:
        """Initialize the agent registry.

        Args:
            db_path (str | Path): SQLite database path.

        Returns:
            None: Initializes the registry.

        Raises:
            OSError: If the database directory cannot be created.
            sqlite3.Error: If database initialization fails.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a configured SQLite connection.

        Args:
            None.

        Returns:
            sqlite3.Connection: Connection with named rows.

        Raises:
            sqlite3.Error: If the connection fails.
        """
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        """Create or migrate agent storage without deleting records.

        Args:
            None.

        Returns:
            None: Initializes the database schema.

        Raises:
            sqlite3.Error: If schema migration fails.
        """
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY,
                    configuration TEXT NOT NULL,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(agents)"
                ).fetchall()
            }

            if "owner_id" not in columns:
                connection.execute(
                    """
                    ALTER TABLE agents
                    ADD COLUMN owner_id TEXT
                    """
                )

            if "approval_status" not in columns:
                connection.execute(
                    """
                    ALTER TABLE agents
                    ADD COLUMN approval_status TEXT NOT NULL
                    DEFAULT 'draft'
                    CHECK (
                        approval_status IN (
                            'draft',
                            'pending',
                            'approved',
                            'rejected'
                        )
                    )
                    """
                )

            if "approved_by" not in columns:
                connection.execute(
                    """
                    ALTER TABLE agents
                    ADD COLUMN approved_by TEXT
                    """
                )

            if "approved_at" not in columns:
                connection.execute(
                    """
                    ALTER TABLE agents
                    ADD COLUMN approved_at TEXT
                    """
                )

            if "version" not in columns:
                connection.execute(
                    """
                    ALTER TABLE agents
                    ADD COLUMN version INTEGER NOT NULL DEFAULT 1
                    """
                )

            # Legacy agents remain unapproved.
            # Historical records are never automatically approved.

    def create_agent(
        self,
        agent: AgentConfig,
        owner_id: str | None = None,
    ) -> AgentConfig:
        """Save a new agent in draft status.

        Args:
            agent (AgentConfig): Agent configuration to save.
            owner_id (str | None): Authenticated creator's ID.

        Returns:
            AgentConfig: Saved agent configuration.

        Raises:
            ValueError: If the agent already exists.
            sqlite3.Error: If persistence fails.
        """
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO agents (
                        id,
                        configuration,
                        owner_id,
                        approval_status
                    )
                    VALUES (?, ?, ?, 'draft')
                    """,
                    (
                        agent.id,
                        agent.model_dump_json(),
                        owner_id,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Agent already exists: {agent.id}"
            ) from exc

        mcp_cache.invalidate_agent(agent.id)
        return agent

    def get_agent(
        self,
        agent_id: str,
    ) -> AgentConfig | None:
        """Retrieve an agent configuration by ID.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            AgentConfig | None: Saved agent or None.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT configuration
                FROM agents
                WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()

        if row is None:
            return None

        return AgentConfig.model_validate_json(
            row["configuration"]
        )

    def get_agent_record(
        self,
        agent_id: str,
    ) -> dict | None:
        """Retrieve an agent with ownership and approval metadata.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            dict | None: Agent record or None if absent.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    configuration,
                    owner_id,
                    approval_status,
                    approved_by,
                    approved_at,
                    version,
                    created_at,
                    updated_at
                FROM agents
                WHERE id = ?
                """,
                (agent_id,),
            ).fetchone()

        if row is None:
            return None

        record = dict(row)

        record["configuration"] = (
            AgentConfig.model_validate_json(
                row["configuration"]
            )
        )

        return record

    def list_agents(self) -> list[AgentConfig]:
        """Retrieve all saved agent configurations.

        Args:
            None.

        Returns:
            list[AgentConfig]: Agents ordered by ID.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT configuration
                FROM agents
                ORDER BY id ASC
                """
            ).fetchall()

        return [
            AgentConfig.model_validate_json(
                row["configuration"]
            )
            for row in rows
        ]

    def list_agent_records(
        self,
        owner_id: str | None = None,
    ) -> list[dict]:
        """List agents with approval metadata.

        Args:
            owner_id (str | None): Optional owner filter.

        Returns:
            list[dict]: Agent records ordered by ID.

        Raises:
            sqlite3.Error: If retrieval fails.
        """
        with self._connect() as connection:
            if owner_id is None:
                rows = connection.execute(
                    """
                    SELECT id
                    FROM agents
                    ORDER BY id ASC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id
                    FROM agents
                    WHERE owner_id = ?
                    ORDER BY id ASC
                    """,
                    (owner_id,),
                ).fetchall()

        return [
            record
            for row in rows
            if (
                record := self.get_agent_record(
                    row["id"]
                )
            ) is not None
        ]

    def update_agent(
        self,
        agent_id: str,
        agent: AgentConfig,
        owner_id: str,
        expected_version: int,
    ) -> AgentConfig | None:
        """Update an owned agent and invalidate previous approval.

        Args:
            agent_id (str): Existing agent identifier.
            agent (AgentConfig): Replacement configuration.
            owner_id (str): Authenticated owner's identifier.
            expected_version (int): Expected current version.

        Returns:
            AgentConfig | None: Updated agent if successful,
                otherwise None.

        Raises:
            ValueError: If the agent ID or version is invalid.
            sqlite3.Error: If persistence fails.
        """
        if agent.id != agent_id:
            raise ValueError(
                "Agent ID cannot be changed."
            )

        if expected_version < 1:
            raise ValueError(
                "Expected version must be at least 1."
            )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents
                SET
                    configuration = ?,
                    approval_status = 'draft',
                    approved_by = NULL,
                    approved_at = NULL,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND owner_id = ?
                  AND version = ?
                """,
                (
                    agent.model_dump_json(),
                    agent_id,
                    owner_id,
                    expected_version,
                ),
            )

            if cursor.rowcount != 1:
                return None

        mcp_cache.invalidate_agent(agent_id)
        return agent

    def delete_agent(
        self,
        agent_id: str,
        owner_id: str | None = None,
    ) -> bool:
        """Delete an agent and invalidate its cached results after commit.

        Args:
            agent_id (str): Identifier of the agent to delete.
            owner_id (str | None): Required owner for scoped deletion.
                None preserves unrestricted internal registry deletion.

        Returns:
            bool: True if the agent was deleted, otherwise False.

        Raises:
            sqlite3.Error: If database deletion fails.
        """
        with self._connect() as connection:
            if owner_id is None:
                cursor = connection.execute(
                    "DELETE FROM agents WHERE id = ?",
                    (agent_id,),
                )
            else:
                cursor = connection.execute(
                    "DELETE FROM agents WHERE id = ? AND owner_id = ?",
                    (agent_id, owner_id),
                )

            deleted = cursor.rowcount > 0

        if deleted:
            mcp_cache.invalidate_agent(agent_id)

        return deleted

    def submit_agent(
        self,
        agent_id: str,
        owner_id: str,
        expected_version: int,
    ) -> bool:
        """Submit an owned draft agent for approval.

        Args:
            agent_id (str): Identifier of the agent.
            owner_id (str): Authenticated owner's identifier.
            expected_version (int): Version being submitted.

        Returns:
            bool: Whether submission succeeded.

        Raises:
            sqlite3.Error: If the database update fails.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents
                SET
                    approval_status = 'pending',
                    approved_by = NULL,
                    approved_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND owner_id = ?
                  AND approval_status = 'draft'
                  AND version = ?
                """,
                (
                    agent_id,
                    owner_id,
                    expected_version,
                ),
            )

            changed = cursor.rowcount == 1

        if changed:
            mcp_cache.invalidate_agent(agent_id)

        return changed

    def approve_agent(
        self,
        agent_id: str,
        reviewer_id: str,
        expected_version: int,
    ) -> bool:
        """Approve a pending agent using an authorized reviewer.

        Args:
            agent_id (str): Identifier of the agent.
            reviewer_id (str): Authorized reviewer's identifier.
            expected_version (int): Version being reviewed.

        Returns:
            bool: Whether approval succeeded.

        Raises:
            sqlite3.Error: If the database update fails.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents
                SET
                    approval_status = 'approved',
                    approved_by = ?,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND approval_status = 'pending'
                  AND version = ?
                  AND owner_id IS NOT NULL
                  AND owner_id != ?
                """,
                (
                    reviewer_id,
                    agent_id,
                    expected_version,
                    reviewer_id,
                ),
            )

            changed = cursor.rowcount == 1

        if changed:
            mcp_cache.invalidate_agent(agent_id)

        return changed

    def reject_agent(
        self,
        agent_id: str,
        reviewer_id: str,
        expected_version: int,
    ) -> bool:
        """Reject a pending agent using an authorized reviewer.

        Args:
            agent_id (str): Identifier of the agent.
            reviewer_id (str): Authorized reviewer's identifier.
            expected_version (int): Version being reviewed.

        Returns:
            bool: Whether rejection succeeded.

        Raises:
            sqlite3.Error: If the database update fails.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents
                SET
                    approval_status = 'rejected',
                    approved_by = NULL,
                    approved_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                  AND approval_status = 'pending'
                  AND version = ?
                  AND owner_id IS NOT NULL
                  AND owner_id != ?
                """,
                (
                    agent_id,
                    expected_version,
                    reviewer_id,
                ),
            )

            changed = cursor.rowcount == 1

        if changed:
            mcp_cache.invalidate_agent(agent_id)

        return changed
