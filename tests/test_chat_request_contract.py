
"""Test the saved-agent-only chat request contract."""

import pytest
from pydantic import ValidationError

from api import ChatRequest


def test_saved_agent_request_is_valid() -> None:
    """Verify that saved-agent requests are accepted.

    Returns:
        None: Assertions verify the request.

    Raises:
        AssertionError: If validation fails.
    """
    request = ChatRequest(
        agent_id="architecture-agent",
        message="Explain the architecture.",
    )

    assert request.agent_id == "architecture-agent"


def test_inline_agent_is_rejected() -> None:
    """Verify that inline agent configurations are rejected.

    Returns:
        None: Assertions verify rejection.

    Raises:
        AssertionError: If legacy requests are accepted.
    """
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({
            "message": "Hello",
            "agent": {
                "id": "temporary-agent",
            },
        })


def test_missing_agent_id_uses_default_assistant() -> None:
    """Verify that omitting agent ID selects the Default Assistant.

    Args:
        None.

    Returns:
        None: Assertions verify the default chat request contract.

    Raises:
        AssertionError: If the request is not validated correctly.
    """
    request = ChatRequest.model_validate(
        {
            "message": "Hello",
        }
    )

    assert request.agent_id is None
    assert request.agent is None
    assert request.message == "Hello"

    
def test_blank_agent_id_is_rejected() -> None:
    """Verify that blank agent IDs are rejected.

    Returns:
        None: Assertions verify rejection.

    Raises:
        AssertionError: If blank IDs are accepted.
    """
    with pytest.raises(ValidationError):
        ChatRequest(
            agent_id="   ",
            message="Hello",
        )
