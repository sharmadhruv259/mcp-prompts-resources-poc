
"""Integration tests for PostgreSQL-backed MCP project notes."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

import server as server_module
from database.models import ProjectNoteModel
from tests.postgres_test_db import get_test_session_factory


@pytest.fixture
def note_context(monkeypatch: pytest.MonkeyPatch):
    """Provide isolated PostgreSQL access for project-note tests.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest patching fixture.

    Yields:
        dict: Server module, test session factory, and tracked note keys.

    Raises:
        RuntimeError: If test database configuration is unsafe.
    """
    session_factory = get_test_session_factory()

    # Redirect the server's project-note operations to Neon testing.
    monkeypatch.setattr(
        server_module,
        "SessionLocal",
        session_factory,
    )

    context = {
        "server": server_module,
        "session_factory": session_factory,
        "note_keys": [],
    }

    try:
        yield context
    finally:
        # Remove only notes created by these integration tests.
        with session_factory.begin() as session:
            for note_key in context["note_keys"]:
                session.execute(
                    delete(ProjectNoteModel).where(
                        ProjectNoteModel.note_key == note_key
                    )
                )


def test_create_and_read_project_note(note_context: dict) -> None:
    """Verify a project note can be created and read.

    Args:
        note_context (dict): Isolated PostgreSQL note context.

    Returns:
        None: Creation and reading assertions pass.

    Raises:
        AssertionError: If note persistence behaves unexpectedly.
    """
    server = note_context["server"]

    note_key = f"pg_note_{uuid4().hex[:12]}"
    note_context["note_keys"].append(note_key)

    content = "This is a PostgreSQL integration test note."

    result = server.write_project_note(
        note_key=note_key,
        content=content,
    )

    assert result == (
        f"Project note '{note_key}' saved successfully."
    )

    stored_content = server.read_project_note(note_key)

    assert stored_content == content


def test_update_existing_project_note(note_context: dict) -> None:
    """Verify PostgreSQL upsert updates existing note content.

    Args:
        note_context (dict): Isolated PostgreSQL note context.

    Returns:
        None: Update assertions pass.

    Raises:
        AssertionError: If note updating behaves unexpectedly.
    """
    server = note_context["server"]
    session_factory = note_context["session_factory"]

    note_key = f"pg_note_{uuid4().hex[:12]}"
    note_context["note_keys"].append(note_key)

    original_content = "Original project note content."
    updated_content = "Updated PostgreSQL project note content."

    server.write_project_note(
        note_key=note_key,
        content=original_content,
    )

    assert server.read_project_note(note_key) == original_content

    result = server.write_project_note(
        note_key=note_key,
        content=updated_content,
    )

    assert result == (
        f"Project note '{note_key}' saved successfully."
    )

    assert server.read_project_note(note_key) == updated_content

    # Confirm the update is persisted in PostgreSQL.
    with session_factory() as session:
        stored = session.get(ProjectNoteModel, note_key)

        assert stored is not None
        assert stored.content == updated_content


def test_missing_project_note(note_context: dict) -> None:
    """Verify reading a nonexistent note returns the expected message.

    Args:
        note_context (dict): Isolated PostgreSQL note context.

    Returns:
        None: Missing-note assertion passes.

    Raises:
        AssertionError: If missing-note handling is incorrect.
    """
    server = note_context["server"]

    note_key = f"pg_missing_{uuid4().hex[:12]}"

    result = server.read_project_note(note_key)

    assert result == f"No project note found for '{note_key}'."


def test_project_note_validation(note_context: dict) -> None:
    """Verify empty note keys and content are rejected.

    Args:
        note_context (dict): Isolated PostgreSQL note context.

    Returns:
        None: Validation assertions pass.

    Raises:
        AssertionError: If invalid input is accepted.
    """
    server = note_context["server"]

    with pytest.raises(
        ValueError,
        match="Note key cannot be empty",
    ):
        server.read_project_note("   ")

    with pytest.raises(
        ValueError,
        match="Note key cannot be empty",
    ):
        server.write_project_note(
            note_key="   ",
            content="Some content",
        )

    with pytest.raises(
        ValueError,
        match="Note content cannot be empty",
    ):
        server.write_project_note(
            note_key="temporary_note",
            content="   ",
        )


def test_project_note_whitespace_normalization(
    note_context: dict,
) -> None:
    """Verify note keys and content are trimmed before storage.

    Args:
        note_context (dict): Isolated PostgreSQL note context.

    Returns:
        None: Whitespace normalization assertions pass.

    Raises:
        AssertionError: If whitespace handling is incorrect.
    """
    server = note_context["server"]
    session_factory = note_context["session_factory"]

    note_key = f"pg_note_{uuid4().hex[:12]}"
    note_context["note_keys"].append(note_key)

    result = server.write_project_note(
        note_key=f"  {note_key}  ",
        content="  Trimmed note content.  ",
    )

    assert result == (
        f"Project note '{note_key}' saved successfully."
    )

    assert (
        server.read_project_note(f"  {note_key}  ")
        == "Trimmed note content."
    )

    with session_factory() as session:
        stored = session.scalar(
            select(ProjectNoteModel).where(
                ProjectNoteModel.note_key == note_key
            )
        )

        assert stored is not None
        assert stored.content == "Trimmed note content."
