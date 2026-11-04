
"""Test administrator-managed MCP tool registry operations."""

import pytest

from services.tool_registry import (
    APPROVED_HANDLERS,
    BUILT_IN_HANDLERS,
    ToolRegistry,
)


@pytest.fixture
def registry(tmp_path) -> ToolRegistry:
    """Create an isolated SQLite Tool Registry for testing.

    Args:
        tmp_path (Path): Temporary directory supplied by pytest.

    Returns:
        ToolRegistry: Registry backed by a temporary database.

    Raises:
        sqlite3.Error: If registry initialization fails.
    """
    return ToolRegistry(
        db_path=tmp_path / "test_tools.db"
    )


def test_registry_initializes_default_tools(
    registry: ToolRegistry,
) -> None:
    """Verify that all approved MCP operations are registered.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify the seeded tools.

    Raises:
        AssertionError: If the default tools are incorrect.
    """
    tools = registry.list_tools()

    names = {tool.name for tool in tools}

    assert names == set(APPROVED_HANDLERS)

    for tool in tools:
        assert tool.enabled is True
        assert tool.deleted is False
        assert tool.handler == tool.name
        assert tool.kind == APPROVED_HANDLERS[tool.name]
        assert tool.built_in is True


def test_get_existing_and_unknown_tool(
    registry: ToolRegistry,
) -> None:
    """Verify retrieval of existing and unknown tools.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify lookup behavior.

    Raises:
        AssertionError: If lookup behavior is incorrect.
    """
    tool = registry.get_tool("read_project_note")

    assert tool is not None
    assert tool.name == "read_project_note"
    assert tool.kind == "read"
    assert tool.enabled is True

    unknown = registry.get_tool("unknown_tool")

    assert unknown is None
    assert registry.is_enabled("unknown_tool") is False


def test_disable_and_enable_tool(
    registry: ToolRegistry,
) -> None:
    """Verify that an administrator can toggle tool availability.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify enabled status changes.

    Raises:
        AssertionError: If status changes are incorrect.
    """
    tool_name = "write_project_note"

    assert registry.is_enabled(tool_name) is True

    disabled = registry.set_enabled(
        name=tool_name,
        enabled=False,
    )

    assert disabled is not None
    assert disabled.enabled is False
    assert registry.is_enabled(tool_name) is False

    enabled = registry.set_enabled(
        name=tool_name,
        enabled=True,
    )

    assert enabled is not None
    assert enabled.enabled is True
    assert registry.is_enabled(tool_name) is True


def test_disabled_status_persists_after_restart(
    registry: ToolRegistry,
) -> None:
    """Verify that disabled status persists across registry instances.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify persistent SQLite state.

    Raises:
        AssertionError: If persistence is incorrect.
    """
    tool_name = "write_project_note"

    registry.set_enabled(
        name=tool_name,
        enabled=False,
    )

    restarted_registry = ToolRegistry(
        db_path=registry.db_path
    )

    assert restarted_registry.is_enabled(tool_name) is False

    tool = restarted_registry.get_tool(tool_name)

    assert tool is not None
    assert tool.enabled is False


def test_update_tool_description(
    registry: ToolRegistry,
) -> None:
    """Verify updating a tool description without changing status.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify the updated description.

    Raises:
        AssertionError: If the update is incorrect.
    """
    tool_name = "read_project_note"

    updated = registry.update_tool(
        name=tool_name,
        description="Read stored notes from SQLite.",
    )

    assert updated is not None
    assert updated.description == (
        "Read stored notes from SQLite."
    )
    assert updated.enabled is True

    restarted_registry = ToolRegistry(
        db_path=registry.db_path
    )

    persisted = restarted_registry.get_tool(tool_name)

    assert persisted is not None
    assert persisted.description == (
        "Read stored notes from SQLite."
    )


def test_update_unknown_tool(
    registry: ToolRegistry,
) -> None:
    """Verify that updating an unknown tool returns None.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify missing-tool behavior.

    Raises:
        AssertionError: If an unknown tool is updated.
    """
    result = registry.update_tool(
        name="unknown_tool",
        description="Unknown description.",
    )

    assert result is None

    status_result = registry.set_enabled(
        name="unknown_tool",
        enabled=True,
    )

    assert status_result is None


def test_reject_unapproved_handler(
    registry: ToolRegistry,
) -> None:
    """Verify that unapproved backend handlers cannot be registered.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify handler restrictions.

    Raises:
        AssertionError: If an unapproved handler is accepted.
    """
    with pytest.raises(
        ValueError,
        match="not in the approved backend registry",
    ):
        registry.create_tool(
            name="unsafe_tool",
            description="An unapproved operation.",
            handler="execute_arbitrary_code",
            kind="write",
        )

    assert registry.get_tool("unsafe_tool") is None


def test_reject_handler_kind_mismatch(
    registry: ToolRegistry,
) -> None:
    """Verify that handler classifications cannot be misrepresented.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify classification restrictions.

    Raises:
        AssertionError: If an invalid classification is accepted.
    """
    with pytest.raises(
        ValueError,
        match="classification does not match",
    ):
        registry.create_tool(
            name="incorrect_write_tool",
            description="Incorrect classification.",
            handler="read_project_note",
            kind="write",
        )


def test_reject_custom_registration_of_builtin_handler(
    registry: ToolRegistry,
) -> None:
    """Verify that built-in handlers cannot be registered as custom tools.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify built-in handler protection.

    Raises:
        AssertionError: If a built-in handler is accepted.
    """
    handler = "get_project_overview"

    assert handler in BUILT_IN_HANDLERS

    with pytest.raises(
        ValueError,
        match="Built-in handlers cannot be registered",
    ):
        registry.create_tool(
            name="custom_overview",
            description="Duplicate overview handler.",
            handler=handler,
            kind="read",
        )


def test_reject_reserved_tool_name(
    registry: ToolRegistry,
) -> None:
    """Verify that approved operation names cannot be reused.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify reserved-name protection.

    Raises:
        AssertionError: If a reserved name is accepted.
    """
    with pytest.raises(
        ValueError,
        match="reserved for a built-in operation",
    ):
        registry.create_tool(
            name="get_project_overview",
            description="Duplicate tool name.",
            handler="read_project_note",
            kind="read",
        )


def test_reject_duplicate_registered_handler(
    registry: ToolRegistry,
) -> None:
    """Verify that a registered handler cannot be reused.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify duplicate-handler protection.

    Raises:
        AssertionError: If duplicate registration succeeds.
    """
    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        registry.create_tool(
            name="custom_note_reader",
            description="Custom note reader.",
            handler="read_project_note",
            kind="read",
        )

    assert registry.get_tool("custom_note_reader") is None


def test_builtin_tools_cannot_be_deleted(
    registry: ToolRegistry,
) -> None:
    """Verify that built-in tools cannot be deleted.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify deletion protection.

    Raises:
        AssertionError: If a built-in tool is deleted.
    """
    with pytest.raises(
        ValueError,
        match="Built-in tools cannot be deleted",
    ):
        registry.delete_tool("get_project_overview")

    assert registry.get_tool("get_project_overview") is not None


def test_delete_unknown_tool(
    registry: ToolRegistry,
) -> None:
    """Verify that deleting an unknown tool returns False.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify missing-tool behavior.

    Raises:
        AssertionError: If deletion reports success.
    """
    deleted = registry.delete_tool("unknown_tool")

    assert deleted is False


def test_disabled_tool_remains_listed(
    registry: ToolRegistry,
) -> None:
    """Verify that disabled tools remain visible to administrators.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify Admin listing behavior.

    Raises:
        AssertionError: If a disabled tool disappears from the registry.
    """
    registry.set_enabled(
        name="write_project_note",
        enabled=False,
    )

    tools = registry.list_tools()

    tool_names = {tool.name for tool in tools}

    assert "write_project_note" in tool_names

    disabled_tool = registry.get_tool(
        "write_project_note"
    )

    assert disabled_tool is not None
    assert disabled_tool.enabled is False


def test_deleted_custom_tool_is_hidden(
    registry: ToolRegistry,
) -> None:
    """Verify that soft-deleted custom tools become unavailable.

    Args:
        registry (ToolRegistry): Isolated test registry.

    Returns:
        None: Assertions verify soft-deletion behavior.

    Raises:
        AssertionError: If a deleted tool remains available.
    """
    tool_name = "temporary_custom_tool"

    # The current registry seeds every approved handler.
    # Insert a custom record directly to test the deletion
    # logic independently of create_tool restrictions.
    with registry._connect() as connection:
        connection.execute(
            """
            INSERT INTO managed_tools (
                name,
                description,
                handler,
                kind,
                enabled,
                built_in,
                deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_name,
                "Temporary test tool.",
                "read_project_note",
                "read",
                1,
                0,
                0,
            ),
        )

    assert registry.is_enabled(tool_name) is True

    deleted = registry.delete_tool(tool_name)

    assert deleted is True
    assert registry.get_tool(tool_name) is None
    assert registry.is_enabled(tool_name) is False

    listed_names = {
        tool.name
        for tool in registry.list_tools()
    }

    assert tool_name not in listed_names

    # A second deletion should report no change.
    assert registry.delete_tool(tool_name) is False
