
"""Integration tests for PostgreSQL-backed MCP tool management."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from database.models import ManagedToolModel
from services import tool_registry as registry_module
from services.tool_registry import ToolRegistry
from tests.postgres_test_db import get_test_session_factory


@pytest.fixture
def test_handler(monkeypatch: pytest.MonkeyPatch) -> str:
    """Register a temporary approved handler for integration testing.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture.

    Returns:
        str: Unique temporary handler name.

    Raises:
        None.
    """
    handler = f"pg_test_handler_{uuid4().hex[:12]}"

    monkeypatch.setitem(
        registry_module.APPROVED_HANDLERS,
        handler,
        "read",
    )

    return handler


@pytest.fixture
def tool_context(test_handler: str):
    """Provide an isolated registry with temporary handler and cleanup.

    Args:
        test_handler (str): Unique approved test handler.

    Returns:
        dict: Registry, session factory, handler, and test tool names.

    Raises:
        RuntimeError: If test database configuration is unsafe.
    """
    session_factory = get_test_session_factory()

    registry = ToolRegistry(
        session_factory=session_factory,
    )

    context = {
        "registry": registry,
        "session_factory": session_factory,
        "handler": test_handler,
        "tool_names": [],
    }

    try:
        yield context

    finally:
        # Remove only records created by this test.
        with session_factory.begin() as session:
            for name in context["tool_names"]:
                session.execute(
                    delete(ManagedToolModel).where(
                        ManagedToolModel.name == name
                    )
                )


def test_tool_creation_and_listing(tool_context: dict) -> None:
    """Verify custom tool creation, retrieval, and listing.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: All creation and listing assertions pass.

    Raises:
        AssertionError: If tool creation behaves unexpectedly.
    """
    registry = tool_context["registry"]
    handler = tool_context["handler"]

    name = f"pg_tool_{uuid4().hex[:12]}"
    tool_context["tool_names"].append(name)

    created = registry.create_tool(
        name=name,
        description="PostgreSQL integration test tool.",
        handler=handler,
        kind="read",
    )

    assert created is not None
    assert created.name == name
    assert created.handler == handler
    assert created.kind == "read"
    assert created.enabled is False
    assert created.built_in is False
    assert created.deleted is False

    retrieved = registry.get_tool(name)

    assert retrieved is not None
    assert retrieved.name == name
    assert retrieved.handler == handler

    tools = registry.list_tools()

    assert any(
        tool.name == name
        for tool in tools
    )


def test_tool_update_and_enable_disable(tool_context: dict) -> None:
    """Verify description updates and tool availability changes.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: All update assertions pass.

    Raises:
        AssertionError: If tool updates behave unexpectedly.
    """
    registry = tool_context["registry"]
    handler = tool_context["handler"]

    name = f"pg_tool_{uuid4().hex[:12]}"
    tool_context["tool_names"].append(name)

    created = registry.create_tool(
        name=name,
        description="Original description.",
        handler=handler,
        kind="read",
    )

    assert created is not None
    assert created.enabled is False
    assert registry.is_enabled(name) is False

    # Enable the custom tool.
    enabled = registry.set_enabled(
        name=name,
        enabled=True,
    )

    assert enabled is not None
    assert enabled.enabled is True
    assert registry.is_enabled(name) is True

    # Update the tool description.
    updated = registry.update_tool(
        name=name,
        description="Updated PostgreSQL description.",
    )

    assert updated is not None
    assert (
        updated.description
        == "Updated PostgreSQL description."
    )

    # Disable the custom tool.
    disabled = registry.set_enabled(
        name=name,
        enabled=False,
    )

    assert disabled is not None
    assert disabled.enabled is False
    assert registry.is_enabled(name) is False


def test_tool_soft_deletion(tool_context: dict) -> None:
    """Verify soft-deleted tools remain stored but become inaccessible.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: Soft-deletion assertions pass.

    Raises:
        AssertionError: If deletion behaves unexpectedly.
    """
    registry = tool_context["registry"]
    session_factory = tool_context["session_factory"]
    handler = tool_context["handler"]

    name = f"pg_tool_{uuid4().hex[:12]}"
    tool_context["tool_names"].append(name)

    created = registry.create_tool(
        name=name,
        description="Temporary tool for deletion testing.",
        handler=handler,
        kind="read",
    )

    assert created is not None

    enabled = registry.set_enabled(
        name=name,
        enabled=True,
    )

    assert enabled is not None
    assert enabled.enabled is True

    # Soft-delete the tool.
    assert registry.delete_tool(name) is True

    # Repeated deletion must return False.
    assert registry.delete_tool(name) is False

    # Deleted tools must be unavailable.
    assert registry.get_tool(name) is None
    assert registry.is_enabled(name) is False

    assert all(
        tool.name != name
        for tool in registry.list_tools()
    )

    # Confirm soft deletion in PostgreSQL.
    with session_factory() as session:
        stored = session.scalar(
            select(ManagedToolModel).where(
                ManagedToolModel.name == name
            )
        )

        assert stored is not None
        assert stored.deleted is True
        assert stored.enabled is False


def test_tool_validation(tool_context: dict) -> None:
    """Verify unsupported and reserved tool registrations are rejected.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: All validation assertions pass.

    Raises:
        AssertionError: If invalid tool registration succeeds.
    """
    registry = tool_context["registry"]

    # Reject unsupported handlers.
    with pytest.raises(
        ValueError,
        match="Handler is not in the approved backend registry",
    ):
        registry.create_tool(
            name=f"pg_invalid_{uuid4().hex[:12]}",
            description="Unsupported handler.",
            handler="unknown_handler",
            kind="read",
        )

    # Reject incorrect handler classifications.
    with pytest.raises(
        ValueError,
        match="Tool classification does not match its handler",
    ):
        registry.create_tool(
            name=f"pg_invalid_{uuid4().hex[:12]}",
            description="Wrong handler classification.",
            handler="write_project_note",
            kind="read",
        )

    # Reject built-in handlers as custom tools.
    with pytest.raises(
        ValueError,
        match="Built-in handlers cannot be registered",
    ):
        registry.create_tool(
            name=f"pg_invalid_{uuid4().hex[:12]}",
            description="Reserved built-in handler.",
            handler="get_project_overview",
            kind="read",
        )

    # Reject reserved operation names.
    with pytest.raises(
        ValueError,
        match="This name is reserved",
    ):
        registry.create_tool(
            name="read_project_note",
            description="Reserved operation name.",
            handler="read_project_note",
            kind="read",
        )


def test_builtin_tool_protection(tool_context: dict) -> None:
    """Verify built-in tools cannot be deleted.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: Built-in deletion protection works.

    Raises:
        AssertionError: If built-in deletion is incorrectly allowed.
    """
    registry = tool_context["registry"]

    with pytest.raises(
        ValueError,
        match="Built-in tools cannot be deleted",
    ):
        registry.delete_tool("get_project_overview")

    built_in = registry.get_tool("get_project_overview")

    assert built_in is not None
    assert built_in.built_in is True


def test_missing_tool_operations(tool_context: dict) -> None:
    """Verify operations on nonexistent tools are handled safely.

    Args:
        tool_context (dict): Isolated PostgreSQL test context.

    Returns:
        None: Missing-tool assertions pass.

    Raises:
        AssertionError: If a missing-tool operation behaves unexpectedly.
    """
    registry = tool_context["registry"]

    missing_name = f"pg_missing_{uuid4().hex[:12]}"

    assert registry.get_tool(missing_name) is None
    assert registry.is_enabled(missing_name) is False

    assert registry.update_tool(
        name=missing_name,
        description="Updated description.",
    ) is None

    assert registry.set_enabled(
        name=missing_name,
        enabled=True,
    ) is None

    assert registry.delete_tool(missing_name) is False
