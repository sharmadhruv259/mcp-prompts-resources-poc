
"""Migrate MCP Playground records from SQLite backups to PostgreSQL."""

import argparse
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import (
    AgentModel,
    ManagedToolModel,
    ProjectNoteModel,
    UserModel,
)


def read_table(database_path: Path, table: str) -> list[dict]:
    """Read records from a SQLite backup.

    Args:
        database_path (Path): Path to the SQLite backup.
        table (str): Name of the table to read.

    Returns:
        list[dict]: Records represented as dictionaries.

    Raises:
        FileNotFoundError: If the backup does not exist.
        ValueError: If the table is not supported.
        sqlite3.Error: If SQLite cannot read the table.
    """
    allowed_tables = {
        "users",
        "agents",
        "managed_tools",
        "project_notes",
    }

    if table not in allowed_tables:
        raise ValueError(f"Unsupported table: {table}")

    if not database_path.is_file():
        raise FileNotFoundError(database_path)

    with sqlite3.connect(
        f"file:{database_path.resolve()}?mode=ro",
        uri=True,
    ) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f'SELECT * FROM "{table}"'
        ).fetchall()

    return [dict(row) for row in rows]


def parse_timestamp(value: str | None) -> datetime | None:
    """Convert a SQLite timestamp into a timezone-aware datetime.

    Args:
        value (str | None): SQLite timestamp string.

    Returns:
        datetime | None: UTC-aware timestamp or None.

    Raises:
        ValueError: If the timestamp is invalid.
    """
    if value is None:
        return None

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def load_backup_data(backup_dir: Path) -> dict[str, list[dict]]:
    """Load all application records from SQLite backups.

    Args:
        backup_dir (Path): Directory containing SQLite backups.

    Returns:
        dict[str, list[dict]]: Records grouped by table.

    Raises:
        FileNotFoundError: If a backup is missing.
        sqlite3.Error: If a backup cannot be read.
    """
    agents_db = backup_dir / "agents.db"
    notes_db = backup_dir / "project_notes.db"

    return {
        "users": read_table(agents_db, "users"),
        "agents": read_table(agents_db, "agents"),
        "managed_tools": read_table(agents_db, "managed_tools"),
        "project_notes": read_table(notes_db, "project_notes"),
    }


def validate_backup(data: dict[str, list[dict]]) -> None:
    """Validate identifiers and relationships in the SQLite backup.

    Args:
        data (dict[str, list[dict]]): SQLite application records.

    Returns:
        None: Validation completes without a return value.

    Raises:
        ValueError: If duplicate identifiers or broken references exist.
    """
    users = data["users"]
    agents = data["agents"]

    identifiers = [user["id"] for user in users]
    usernames = [user["username"].lower() for user in users]

    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate user IDs in SQLite backup.")

    if len(usernames) != len(set(usernames)):
        raise ValueError("Duplicate usernames in SQLite backup.")

    if any(not identifier for identifier in identifiers):
        raise ValueError("SQLite backup contains an empty user ID.")

    if any(not username for username in usernames):
        raise ValueError("SQLite backup contains an empty username.")

    admin_count = sum(
        user["role"] == "admin"
        for user in users
    )

    if admin_count != 1:
        raise ValueError(
            f"Expected one SQLite Admin, found {admin_count}."
        )

    user_ids = set(identifiers)

    for agent in agents:
        for field in ("owner_id", "approved_by"):
            reference = agent[field]

            if reference is not None and reference not in user_ids:
                raise ValueError(
                    f"Agent {agent['id']} has invalid {field}."
                )

    for table, key in (
        ("agents", "id"),
        ("managed_tools", "name"),
        ("project_notes", "note_key"),
    ):
        values = [row[key] for row in data[table]]

        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate identifiers in {table}.")

        if any(not value for value in values):
            raise ValueError(f"Empty identifier in {table}.")

    print("SQLite backup validation: PASSED")


def count_records(session: Session, model: type) -> int:
    """Count records in a PostgreSQL table.

    Args:
        session (Session): Active SQLAlchemy session.
        model (type): SQLAlchemy model to count.

    Returns:
        int: Number of records.

    Raises:
        Exception: If the database query fails.
    """
    return session.scalar(
        select(func.count()).select_from(model)
    )


def validate_destination(
    session: Session,
    data: dict[str, list[dict]],
) -> UserModel:
    """Ensure PostgreSQL contains only the temporary Admin.

    Args:
        session (Session): Active SQLAlchemy session.
        data (dict[str, list[dict]]): SQLite backup records.

    Returns:
        UserModel: Temporary PostgreSQL Admin.

    Raises:
        ValueError: If PostgreSQL contains unexpected records.
    """
    counts = {
        "users": count_records(session, UserModel),
        "agents": count_records(session, AgentModel),
        "managed_tools": count_records(session, ManagedToolModel),
        "project_notes": count_records(session, ProjectNoteModel),
    }

    expected = {
        "users": 1,
        "agents": 0,
        "managed_tools": 0,
        "project_notes": 0,
    }

    if counts != expected:
        raise ValueError(
            f"PostgreSQL destination is not empty as expected: {counts}"
        )

    temporary_admin = session.scalar(select(UserModel))

    if temporary_admin is None or temporary_admin.role != "admin":
        raise ValueError(
            "Expected one temporary PostgreSQL Admin."
        )

    sqlite_admin = next(
        user for user in data["users"]
        if user["role"] == "admin"
    )

    if (
        temporary_admin.username.casefold()
        != sqlite_admin["username"].casefold()
    ):
        raise ValueError(
            "PostgreSQL Admin username differs from SQLite Admin. "
            "Review accounts before migrating."
        )

    return temporary_admin


def import_records(
    session: Session,
    data: dict[str, list[dict]],
    temporary_admin: UserModel,
) -> None:
    """Import all SQLite records into the PostgreSQL transaction.

    Args:
        session (Session): Active PostgreSQL transaction session.
        data (dict[str, list[dict]]): Validated SQLite records.
        temporary_admin (UserModel): Admin account to reconcile.

    Returns:
        None: Records are added to the active transaction.

    Raises:
        Exception: If an insert or database constraint fails.
    """
    session.delete(temporary_admin)
    session.flush()

    for user in data["users"]:
        session.add(
            UserModel(
                id=user["id"],
                username=user["username"],
                password_hash=user["password_hash"],
                role=user["role"],
                is_active=bool(user["is_active"]),
                created_at=parse_timestamp(user["created_at"]),
            )
        )

    session.flush()

    for agent in data["agents"]:
        session.add(
            AgentModel(
                id=agent["id"],
                configuration=agent["configuration"],
                created_at=parse_timestamp(agent["created_at"]),
                updated_at=parse_timestamp(agent["updated_at"]),
                owner_id=agent["owner_id"],
                approval_status=agent["approval_status"],
                approved_by=agent["approved_by"],
                approved_at=parse_timestamp(agent["approved_at"]),
                version=int(agent["version"]),
            )
        )

    for tool in data["managed_tools"]:
        session.add(
            ManagedToolModel(
                name=tool["name"],
                description=tool["description"],
                handler=tool["handler"],
                kind=tool["kind"],
                enabled=bool(tool["enabled"]),
                built_in=bool(tool["built_in"]),
                deleted=bool(tool["deleted"]),
            )
        )

    for note in data["project_notes"]:
        session.add(
            ProjectNoteModel(
                note_key=note["note_key"],
                content=note["content"],
                updated_at=parse_timestamp(note["updated_at"]),
            )
        )

    session.flush()


def verify_import(
    session: Session,
    data: dict[str, list[dict]],
) -> None:
    """Verify PostgreSQL record counts and key relationships.

    Args:
        session (Session): Active PostgreSQL transaction session.
        data (dict[str, list[dict]]): Original SQLite records.

    Returns:
        None: Verification completes without a return value.

    Raises:
        ValueError: If counts or references do not match.
    """
    models = {
        "users": UserModel,
        "agents": AgentModel,
        "managed_tools": ManagedToolModel,
        "project_notes": ProjectNoteModel,
    }

    for table, model in models.items():
        expected = len(data[table])
        actual = count_records(session, model)

        if actual != expected:
            raise ValueError(
                f"{table}: expected {expected}, found {actual}"
            )

    postgres_users = {
        user.id
        for user in session.scalars(select(UserModel))
    }

    for agent in session.scalars(select(AgentModel)):
        if agent.owner_id and agent.owner_id not in postgres_users:
            raise ValueError("Invalid PostgreSQL agent owner.")

        if agent.approved_by and agent.approved_by not in postgres_users:
            raise ValueError("Invalid PostgreSQL agent reviewer.")

    expected_statuses = Counter(
        agent["approval_status"]
        for agent in data["agents"]
    )

    actual_statuses = Counter(
        agent.approval_status
        for agent in session.scalars(select(AgentModel))
    )

    if actual_statuses != expected_statuses:
        raise ValueError("Agent approval statuses do not match.")

    print("PostgreSQL import verification: PASSED")


def migrate(backup_dir: Path, apply: bool = False) -> None:
    """Validate and optionally migrate SQLite backups to PostgreSQL.

    Args:
        backup_dir (Path): Directory containing SQLite backups.
        apply (bool): Whether to commit the migration.

    Returns:
        None: Migration finishes without a return value.

    Raises:
        ValueError: If validation or verification fails.
        Exception: If a database operation fails.
    """
    data = load_backup_data(backup_dir)
    validate_backup(data)

    print("\nSQLite records:")
    for table, rows in data.items():
        print(f"  {table}: {len(rows)}")

    with SessionLocal.begin() as session:
        temporary_admin = validate_destination(session, data)

        print("\nPostgreSQL destination validation: PASSED")

        if not apply:
            print("\nDRY RUN ONLY — no PostgreSQL changes made.")
            return

        import_records(session, data, temporary_admin)
        verify_import(session, data)

    print("\nMigration committed successfully.")


def main() -> None:
    """Run the SQLite-to-PostgreSQL migration CLI.

    Args:
        None.

    Returns:
        None.

    Raises:
        ValueError: If migration validation fails.
        Exception: If database operations fail.
    """
    parser = argparse.ArgumentParser(
        description="Migrate MCP Playground SQLite backups to PostgreSQL."
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("backups"),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit migration after validation.",
    )

    args = parser.parse_args()

    migrate(
        backup_dir=args.backup_dir,
        apply=args.apply,
    )


if __name__ == "__main__":
    main()
