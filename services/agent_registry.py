
"""Persist custom AI agent configurations using SQLite."""

import sqlite3
from pathlib import Path

from models.agent_config import AgentConfig


DEFAULT_DB_PATH = Path("data/agents.db")


class AgentRegistry:
    """Manage persistent custom agent configurations.

    Attributes:
        db_path (Path): SQLite database file location.

    Functions:
        _connect: Open a SQLite connection.
        _initialize: Create the agents table.
        create_agent: Save a new agent.
        get_agent: Retrieve an agent by ID.
        list_agents: Retrieve all saved agents.
        update_agent: Replace an existing agent.
        delete_agent: Delete an existing agent.
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
        """Open a SQLite connection.

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
        """Create the agent storage table if necessary.

        Args:
            None.

        Returns:
            None: Initializes the database schema.

        Raises:
            sqlite3.Error: If schema creation fails.
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

    def create_agent(
        self,
        agent: AgentConfig,
    ) -> AgentConfig:
        """Save a new custom agent.

        Args:
            agent (AgentConfig): Agent configuration to save.

        Returns:
            AgentConfig: Saved agent configuration.

        Raises:
            ValueError: If the agent ID already exists.
            sqlite3.Error: If persistence fails.
        """
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO agents (id, configuration)
                    VALUES (?, ?)
                    """,
                    (
                        agent.id,
                        agent.model_dump_json(),
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Agent already exists: {agent.id}"
            ) from exc

        return agent

    def get_agent(
        self,
        agent_id: str,
    ) -> AgentConfig | None:
        """Retrieve an agent by its identifier.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            AgentConfig | None: Saved agent or None.

        Raises:
            sqlite3.Error: If database retrieval fails.
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

    def list_agents(self) -> list[AgentConfig]:
        """Retrieve all saved agents.

        Args:
            None.

        Returns:
            list[AgentConfig]: Saved agents ordered by ID.

        Raises:
            sqlite3.Error: If database retrieval fails.
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

    def update_agent(
        self,
        agent_id: str,
        agent: AgentConfig,
    ) -> AgentConfig | None:
        """Replace an existing agent configuration.

        Args:
            agent_id (str): Existing agent identifier.
            agent (AgentConfig): Replacement configuration.

        Returns:
            AgentConfig | None: Updated agent or None if absent.

        Raises:
            ValueError: If the replacement changes the agent ID.
            sqlite3.Error: If persistence fails.
        """
        if agent.id != agent_id:
            raise ValueError(
                "Agent ID cannot be changed."
            )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE agents
                SET configuration = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    agent.model_dump_json(),
                    agent_id,
                ),
            )

            if cursor.rowcount == 0:
                return None

        return agent

    def delete_agent(
        self,
        agent_id: str,
    ) -> bool:
        """Delete an agent by its identifier.

        Args:
            agent_id (str): Agent identifier.

        Returns:
            bool: True if deleted, otherwise False.

        Raises:
            sqlite3.Error: If deletion fails.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM agents
                WHERE id = ?
                """,
                (agent_id,),
            )

            return cursor.rowcount > 0
