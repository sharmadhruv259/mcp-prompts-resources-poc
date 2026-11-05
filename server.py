
"""Register MCP resources, tools, and reusable prompts."""

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from database.connection import SessionLocal
from database.models import ProjectNoteModel
from mcp.server import MCPServer
from prompts import register_prompts
from constants.paths import (
    ARCHITECTURE_PATH,
    ARCHITECTURE_URI,
    REQUIREMENTS_PATH,
    REQUIREMENTS_URI,
)


mcp = MCPServer("Project Knowledge POC")


def initialize_notes_database() -> None:
    """Verify that the PostgreSQL project notes table is accessible.

    Args:
        None.

    Returns:
        None: Confirms that project note storage is accessible.

    Raises:
        SQLAlchemyError: If PostgreSQL storage is unavailable.
    """
    with SessionLocal() as session:
        session.query(ProjectNoteModel).limit(1).all()


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
    """Read a project note from PostgreSQL.

    Args:
        note_key (str): Unique identifier of the note.

    Returns:
        str: Stored note content or a not-found message.

    Raises:
        ValueError: If the note key is empty.
        SQLAlchemyError: If the database query fails.
    """
    note_key = note_key.strip()

    if not note_key:
        raise ValueError("Note key cannot be empty.")

    with SessionLocal() as session:
        note = session.get(ProjectNoteModel, note_key)

        if note is None:
            return f"No project note found for '{note_key}'."

        return note.content


@mcp.tool()
def write_project_note(
    note_key: str,
    content: str,
) -> str:
    """Create or update a project note in PostgreSQL.

    Args:
        note_key (str): Unique identifier of the note.
        content (str): Text to store in the note.

    Returns:
        str: Confirmation that the note was saved.

    Raises:
        ValueError: If the note key or content is empty.
        SQLAlchemyError: If the database operation fails.
    """
    note_key = note_key.strip()
    content = content.strip()

    if not note_key:
        raise ValueError("Note key cannot be empty.")

    if not content:
        raise ValueError("Note content cannot be empty.")

    statement = (
    insert(ProjectNoteModel)
    .values(
        note_key=note_key,
        content=content,
        updated_at=func.now(),
    )
    .on_conflict_do_update(
        index_elements=[ProjectNoteModel.note_key],
        set_={
            "content": content,
            "updated_at": func.now(),
        },
    )
)


    with SessionLocal.begin() as session:
        session.execute(statement)

    return f"Project note '{note_key}' saved successfully."


# Register reusable MCP prompts.
register_prompts(mcp)


if __name__ == "__main__":
    mcp.run()
