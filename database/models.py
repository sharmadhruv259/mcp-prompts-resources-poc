
"""Define PostgreSQL ORM models for the MCP Playground."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Provide the declarative base for database models."""


class UserModel(Base):
    """Store authenticated application accounts."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True
    )
    username: Mapped[str] = mapped_column(
        String(150), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'manager', 'admin')",
            name="ck_users_role",
        ),
    )


class AgentModel(Base):
    """Store custom agents and their approval metadata."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )
    configuration: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    owner_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "approval_status IN "
            "('draft', 'pending', 'approved', 'rejected')",
            name="ck_agents_approval_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_agents_version",
        ),
    )


class ManagedToolModel(Base):
    """Store administrator-managed MCP tool settings."""

    __tablename__ = "managed_tools"

    name: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    handler: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    built_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('read', 'write')",
            name="ck_managed_tools_kind",
        ),
    )


class ProjectNoteModel(Base):
    """Store persistent project notes in PostgreSQL.

    Attributes:
        note_key (str): Unique identifier for the note.
        content (str): Stored note content.
        updated_at (datetime): Last modification timestamp.

    Functions:
        None.
    """

    __tablename__ = "project_notes"

    note_key: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
