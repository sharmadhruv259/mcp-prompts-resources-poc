
"""Register MCP resources, tools, and reusable prompts."""

import sqlite3
from pathlib import Path

from mcp.server import MCPServer

from prompts import register_prompts
from constants.paths import (
    ARCHITECTURE_PATH,
    ARCHITECTURE_URI,
    REQUIREMENTS_PATH,
    REQUIREMENTS_URI,
)


mcp = MCPServer("Project Knowledge POC")

NOTES_DB_PATH = Path("data/project_notes.db")


def initialize_notes_database() -> None:
    """Create the SQLite table for project notes.

    Args:
        None.

    Returns:
        None: Initializes the database schema.

    Raises:
        sqlite3.Error: If database initialization fails.
        OSError: If the database directory cannot be created.
    """
    NOTES_DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sqlite3.connect(NOTES_DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_notes (
                note_key TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@mcp.resource(REQUIREMENTS_URI, mime_type="text/markdown")
def project_requirements() -> str:
    """Read the example project's functional requirements.

    Args:
        None.

    Returns:
        str: Current Markdown requirements document.

    Raises:
        OSError: If the document cannot be read.
    """
    return REQUIREMENTS_PATH.read_text(
        encoding="utf-8"
    )


@mcp.resource(ARCHITECTURE_URI, mime_type="text/markdown")
def project_architecture() -> str:
    """Read the example project's technical architecture.

    Args:
        None.

    Returns:
        str: Current Markdown architecture document.

    Raises:
        OSError: If the document cannot be read.
    """
    return ARCHITECTURE_PATH.read_text(
        encoding="utf-8"
    )


@mcp.tool()
def get_project_overview() -> str:
    """Return an overview of the project from its documents.

    Args:
        None.

    Returns:
        str: Project requirements and architecture context.

    Raises:
        OSError: If a project document cannot be read.
    """
    requirements = REQUIREMENTS_PATH.read_text(
        encoding="utf-8"
    )

    architecture = ARCHITECTURE_PATH.read_text(
        encoding="utf-8"
    )

    return (
        "PROJECT REQUIREMENTS\n"
        f"{requirements}\n\n"
        "PROJECT ARCHITECTURE\n"
        f"{architecture}"
    )


@mcp.tool()
def read_project_note(note_key: str) -> str:
    """Read a project note from the SQLite database.

    Args:
        note_key (str): Unique identifier of the note.

    Returns:
        str: Stored note content or a not-found message.

    Raises:
        ValueError: If the note key is empty.
        sqlite3.Error: If the database query fails.
    """
    note_key = note_key.strip()

    if not note_key:
        raise ValueError("Note key cannot be empty.")

    initialize_notes_database()

    with sqlite3.connect(NOTES_DB_PATH) as connection:
        row = connection.execute(
            """
            SELECT content
            FROM project_notes
            WHERE note_key = ?
            """,
            (note_key,),
        ).fetchone()

    if row is None:
        return f"No project note found for '{note_key}'."

    return row[0]


@mcp.tool()
def write_project_note(
    note_key: str,
    content: str,
) -> str:
    """Create or update a project note in SQLite.

    Args:
        note_key (str): Unique identifier of the note.
        content (str): Text to store in the note.

    Returns:
        str: Confirmation that the note was saved.

    Raises:
        ValueError: If the note key or content is empty.
        sqlite3.Error: If the database operation fails.
    """
    note_key = note_key.strip()
    content = content.strip()

    if not note_key:
        raise ValueError("Note key cannot be empty.")

    if not content:
        raise ValueError("Note content cannot be empty.")

    initialize_notes_database()

    with sqlite3.connect(NOTES_DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO project_notes (
                note_key,
                content
            )
            VALUES (?, ?)
            ON CONFLICT(note_key)
            DO UPDATE SET
                content = excluded.content,
                updated_at = CURRENT_TIMESTAMP
            """,
            (note_key, content),
        )

    return f"Project note '{note_key}' saved successfully."


# Register reusable MCP prompts.
register_prompts(mcp)


if __name__ == "__main__":
    mcp.run()
