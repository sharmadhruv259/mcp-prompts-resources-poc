
"""Persist custom AI agents with PostgreSQL ownership and approval metadata."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from database.connection import SessionLocal
from database.models import AgentModel
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
    """Manage agent configurations and approval metadata in PostgreSQL.

    Attributes:
        db_path (Path): Legacy path retained for caller compatibility.
        session_factory (sessionmaker): PostgreSQL session factory.

    Functions:
        _to_record: Convert a database model to an agent record.
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
        session_factory: sessionmaker = SessionLocal,
    ) -> None:
        """Initialize the PostgreSQL agent registry.

        Args:
            db_path (str | Path): Legacy SQLite path, no longer used
                for persistence.
            session_factory (sessionmaker): SQLAlchemy session factory.

        Returns:
            None: Initializes the registry.

        Raises:
            None: No database connection is opened during initialization.
        """
        self.db_path = Path(db_path)
        self.session_factory = session_factory

    @staticmethod
    def _to_record(model: AgentModel) -> dict:
        """Convert a stored agent into its public record representation.

        Args:
            model (AgentModel): Stored PostgreSQL agent.

        Returns:
            dict: Agent configuration and approval metadata.

        Raises:
            ValueError: If the stored configuration is invalid.
        """
        return {
            "id": model.id,
            "configuration": AgentConfig.model_validate_json(
                model.configuration
            ),
            "owner_id": model.owner_id,
            "approval_status": model.approval_status,
            "approved_by": model.approved_by,
            "approved_at": (
                str(model.approved_at)
                if model.approved_at is not None
                else None
            ),
            "version": model.version,
            "created_at": str(model.created_at),
            "updated_at": str(model.updated_at),
        }

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
            ValueError: If the agent already exists or an owner
                reference is invalid.
            SQLAlchemyError: If database persistence fails.
        """
        try:
            with self.session_factory.begin() as session:
                session.add(
                    AgentModel(
                        id=agent.id,
                        configuration=agent.model_dump_json(),
                        owner_id=owner_id,
                        approval_status="draft",
                        version=1,
                    )
                )
        except IntegrityError as exc:
            raise ValueError(
                f"Could not create agent {agent.id}: "
                "duplicate ID or invalid owner."
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
            ValueError: If the stored configuration is invalid.
            SQLAlchemyError: If retrieval fails.
        """
        with self.session_factory() as session:
            model = session.get(AgentModel, agent_id)

            if model is None:
                return None

            return AgentConfig.model_validate_json(
                model.configuration
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
            ValueError: If the stored configuration is invalid.
            SQLAlchemyError: If retrieval fails.
        """
        with self.session_factory() as session:
            model = session.get(AgentModel, agent_id)

            if model is None:
                return None

            return self._to_record(model)

    def list_agents(self) -> list[AgentConfig]:
        """Retrieve all saved agent configurations.

        Args:
            None.

        Returns:
            list[AgentConfig]: Agents ordered by ID.

        Raises:
            ValueError: If a stored configuration is invalid.
            SQLAlchemyError: If retrieval fails.
        """
        with self.session_factory() as session:
            models = session.scalars(
                select(AgentModel).order_by(AgentModel.id.asc())
            ).all()

            return [
                AgentConfig.model_validate_json(model.configuration)
                for model in models
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
            ValueError: If a stored configuration is invalid.
            SQLAlchemyError: If retrieval fails.
        """
        statement = select(AgentModel)

        if owner_id is not None:
            statement = statement.where(
                AgentModel.owner_id == owner_id
            )

        statement = statement.order_by(AgentModel.id.asc())

        with self.session_factory() as session:
            models = session.scalars(statement).all()

            return [
                self._to_record(model)
                for model in models
            ]

    def update_agent(
        self,
        agent_id: str,
        agent: AgentConfig,
        owner_id: str,
        expected_version: int,
    ) -> AgentConfig | None:
        """Update an owned agent and invalidate its previous approval.

        Args:
            agent_id (str): Existing agent identifier.
            agent (AgentConfig): Replacement configuration.
            owner_id (str): Authenticated owner's identifier.
            expected_version (int): Expected current version.

        Returns:
            AgentConfig | None: Updated agent or None if no row matched.

        Raises:
            ValueError: If the agent ID or version is invalid.
            SQLAlchemyError: If persistence fails.
        """
        if agent.id != agent_id:
            raise ValueError("Agent ID cannot be changed.")

        if expected_version < 1:
            raise ValueError(
                "Expected version must be at least 1."
            )

        with self.session_factory.begin() as session:
            result = session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == agent_id,
                    AgentModel.owner_id == owner_id,
                    AgentModel.version == expected_version,
                )
                .values(
                    configuration=agent.model_dump_json(),
                    approval_status="draft",
                    approved_by=None,
                    approved_at=None,
                    version=AgentModel.version + 1,
                    updated_at=func.now(),
                )
            )

            changed = result.rowcount == 1

        if not changed:
            return None

        mcp_cache.invalidate_agent(agent_id)
        return agent

    def delete_agent(
        self,
        agent_id: str,
        owner_id: str | None = None,
    ) -> bool:
        """Delete an agent and invalidate its cache after commit.

        Args:
            agent_id (str): Identifier of the agent to delete.
            owner_id (str | None): Optional ownership restriction.
                None permits unrestricted internal deletion.

        Returns:
            bool: True if the agent was deleted, otherwise False.

        Raises:
            SQLAlchemyError: If deletion fails.
        """
        statement = delete(AgentModel).where(
            AgentModel.id == agent_id
        )

        if owner_id is not None:
            statement = statement.where(
                AgentModel.owner_id == owner_id
            )

        with self.session_factory.begin() as session:
            result = session.execute(statement)
            deleted = result.rowcount > 0

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
            SQLAlchemyError: If the database update fails.
        """
        with self.session_factory.begin() as session:
            result = session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == agent_id,
                    AgentModel.owner_id == owner_id,
                    AgentModel.approval_status == "draft",
                    AgentModel.version == expected_version,
                )
                .values(
                    approval_status="pending",
                    approved_by=None,
                    approved_at=None,
                    updated_at=func.now(),
                )
            )

            changed = result.rowcount == 1

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
            SQLAlchemyError: If the database update fails.
        """
        with self.session_factory.begin() as session:
            result = session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == agent_id,
                    AgentModel.approval_status == "pending",
                    AgentModel.version == expected_version,
                    AgentModel.owner_id.is_not(None),
                    AgentModel.owner_id != reviewer_id,
                )
                .values(
                    approval_status="approved",
                    approved_by=reviewer_id,
                    approved_at=func.now(),
                    updated_at=func.now(),
                )
            )

            changed = result.rowcount == 1

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
            SQLAlchemyError: If the database update fails.
        """
        with self.session_factory.begin() as session:
            result = session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == agent_id,
                    AgentModel.approval_status == "pending",
                    AgentModel.version == expected_version,
                    AgentModel.owner_id.is_not(None),
                    AgentModel.owner_id != reviewer_id,
                )
                .values(
                    approval_status="rejected",
                    approved_by=None,
                    approved_at=None,
                    updated_at=func.now(),
                )
            )

            changed = result.rowcount == 1

        if changed:
            mcp_cache.invalidate_agent(agent_id)

        return changed
