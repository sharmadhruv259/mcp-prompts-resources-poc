
"""Expose custom Groq agents and MCP capabilities through FastAPI."""

import os
import logging
import sqlite3
from typing import Literal

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from mcp import Client
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from agent import run_agent
from models.agent_config import AgentConfig
from server import mcp
from services.agent_registry import AgentRegistry
from services.mcp_cache import mcp_cache
from services.mcp_discovery import (
    MCPCapabilities,
    discover_mcp_capabilities,
)


logger = logging.getLogger(__name__)

registry = AgentRegistry()

app = FastAPI(
    title="MCP Playground API",
    description=(
        "Create, manage, and execute custom AI agents "
        "using Groq and MCP capabilities."
    ),
    version="0.4.0",
)


# Allowed frontend origins for local and deployed environments.
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
    ],
    allow_headers=["Content-Type"],
)

class ChatRequest(BaseModel):
    """Represent a custom agent chat request.

    Attributes:
        message (str): User's question.
        agent_id (str | None): Identifier of a saved agent.
        agent (AgentConfig | None): Legacy inline agent configuration.

    Functions:
        validate_message: Validate and normalize the message.
        validate_agent_id: Normalize the saved agent identifier.
        validate_agent_selection: Require exactly one agent source.
    """

    message: str = Field(
        min_length=1,
        max_length=20000,
    )

    agent_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    agent: AgentConfig | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Validate and normalize the user message.

        Args:
            value (str): User-provided message.

        Returns:
            str: Trimmed nonempty message.

        Raises:
            ValueError: If the message is empty.
        """
        value = value.strip()

        if not value:
            raise ValueError(
                "Message cannot be empty."
            )

        return value

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize the optional saved agent identifier.

        Args:
            value (str | None): Agent identifier.

        Returns:
            str | None: Trimmed identifier or None.

        Raises:
            ValueError: If the identifier is blank.
        """
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError(
                "Agent ID cannot be empty."
            )

        return value

    @model_validator(mode="after")
    def validate_agent_selection(self) -> "ChatRequest":
        """Require exactly one agent selection method.

        Args:
            None: Uses the current request fields.

        Returns:
            ChatRequest: Validated request.

        Raises:
            ValueError: If both or neither agent source is provided.
        """
        if (self.agent_id is None) == (self.agent is None):
            raise ValueError(
                "Provide exactly one of agent_id or agent."
            )

        return self


class ExecutionEvent(BaseModel):
    """Represent an MCP operation execution event.

    Attributes:
        id (str): Unique execution event identifier.
        tool (str): Executed MCP operation.
        status (Literal): Execution status.
        description (str): Human-readable execution details.

    Functions:
        None.
    """

    id: str

    tool: str

    status: Literal[
        "running",
        "completed",
        "failed",
    ]

    description: str


class ChatResponse(BaseModel):
    """Represent a custom agent's response.

    Attributes:
        answer (str): Final generated answer.
        events (list[ExecutionEvent]): MCP execution history.

    Functions:
        None.
    """

    answer: str

    events: list[ExecutionEvent] = Field(
        default_factory=list,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Return backend process health.

    Args:
        None.

    Returns:
        dict[str, str]: Backend health status.

    Raises:
        None.
    """
    return {
        "status": "ok",
    }


@app.post(
    "/api/agents",
    response_model=AgentConfig,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(agent: AgentConfig) -> AgentConfig:
    """Create and persist a custom AI agent.

    Args:
        agent (AgentConfig): New agent configuration.

    Returns:
        AgentConfig: Saved agent configuration.

    Raises:
        HTTPException: If the agent exists or persistence fails.
    """
    try:
        saved_agent = registry.create_agent(agent)

        # Clear stale cache entries if this agent ID
        # was previously used and then deleted.
        mcp_cache.invalidate_agent(saved_agent.id)

        return saved_agent

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to create agent: %s",
            agent.id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to save agent.",
        ) from exc


@app.get(
    "/api/agents",
    response_model=list[AgentConfig],
)
def list_agents() -> list[AgentConfig]:
    """Retrieve all saved custom agents.

    Args:
        None.

    Returns:
        list[AgentConfig]: Saved agent configurations.

    Raises:
        HTTPException: If database retrieval fails.
    """
    try:
        return registry.list_agents()

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to list agents"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve agents.",
        ) from exc


@app.get(
    "/api/agents/{agent_id}",
    response_model=AgentConfig,
)
def get_agent(agent_id: str) -> AgentConfig:
    """Retrieve a saved custom agent by ID.

    Args:
        agent_id (str): Agent identifier.

    Returns:
        AgentConfig: Saved agent configuration.

    Raises:
        HTTPException: If the agent is missing or retrieval fails.
    """
    try:
        agent = registry.get_agent(agent_id)

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to retrieve agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve agent.",
        ) from exc

    if agent is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )

    return agent


@app.put(
    "/api/agents/{agent_id}",
    response_model=AgentConfig,
)
def update_agent(
    agent_id: str,
    agent: AgentConfig,
) -> AgentConfig:
    """Update an existing custom agent.

    Args:
        agent_id (str): Existing agent identifier.
        agent (AgentConfig): Replacement configuration.

    Returns:
        AgentConfig: Updated agent configuration.

    Raises:
        HTTPException: If the ID differs, agent is missing,
            or persistence fails.
    """
    if agent.id != agent_id:
        raise HTTPException(
            status_code=400,
            detail="Agent ID cannot be changed.",
        )

    try:
        updated = registry.update_agent(
            agent_id,
            agent,
        )

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to update agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update agent.",
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )

    # Invalidate cached resources and prompts because
    # the agent configuration may have changed.
    mcp_cache.invalidate_agent(agent_id)

    return updated


@app.delete(
    "/api/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_agent(agent_id: str) -> Response:
    """Delete a saved custom agent.

    Args:
        agent_id (str): Agent identifier.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        HTTPException: If the agent is missing or deletion fails.
    """
    try:
        deleted = registry.delete_agent(
            agent_id
        )

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to delete agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to delete agent.",
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Agent not found: {agent_id}",
        )

    # Remove cached MCP results for the deleted agent.
    mcp_cache.invalidate_agent(agent_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@app.get(
    "/api/mcp/capabilities",
    response_model=MCPCapabilities,
)
async def get_mcp_capabilities() -> MCPCapabilities:
    """Discover available MCP capabilities.

    Args:
        None.

    Returns:
        MCPCapabilities: Available tools, resources, and prompts.

    Raises:
        HTTPException: If MCP discovery fails.
    """
    try:
        async with Client(mcp) as client:
            capabilities = await discover_mcp_capabilities(
                client
            )

        return capabilities

    except Exception as exc:
        logger.exception(
            "MCP capability discovery failed"
        )

        raise HTTPException(
            status_code=502,
            detail="Unable to discover MCP capabilities.",
        ) from exc


# Custom agent execution
@app.post(
    "/api/chat",
    response_model=ChatResponse,
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Execute a saved or legacy inline custom agent.

    Args:
        request (ChatRequest): Message and agent selection.

    Returns:
        ChatResponse: Generated answer and execution events.

    Raises:
        HTTPException: If the agent is missing, invalid,
            or execution fails.
    """
    # Load saved agent from SQLite when agent_id is provided.
    if request.agent_id is not None:
        try:
            selected_agent = registry.get_agent(
                request.agent_id
            )

        except sqlite3.Error as exc:
            logger.exception(
                "Failed to load agent: %s",
                request.agent_id,
            )

            raise HTTPException(
                status_code=500,
                detail="Unable to load the selected agent.",
            ) from exc

        if selected_agent is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {request.agent_id}",
            )

    else:
        # Temporary backward compatibility with existing clients.
        selected_agent = request.agent

    if selected_agent is None:
        raise HTTPException(
            status_code=422,
            detail="An agent must be selected.",
        )

    validation_error: str | None = None
    answer: str | None = None
    events: list[dict[str, str]] = []

    try:
        async with Client(mcp) as client:
            try:
                answer, events = await run_agent(
                    client=client,
                    question=request.message,
                    agent=selected_agent,
                )

            except ValueError as exc:
                # Handle validation errors after exiting
                # the MCP context manager.
                validation_error = str(exc)

    except Exception as exc:
        logger.exception(
            "Custom agent execution failed: agent_id=%s",
            selected_agent.id,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to execute the custom agent. "
                "Check the backend logs."
            ),
        ) from exc

    if validation_error is not None:
        raise HTTPException(
            status_code=400,
            detail=validation_error,
        )

    if answer is None:
        logger.error(
            "Agent returned no answer: agent_id=%s",
            selected_agent.id,
        )

        raise HTTPException(
            status_code=502,
            detail="Agent returned no answer.",
        )

    return ChatResponse(
        answer=answer,
        events=[
            ExecutionEvent.model_validate(event)
            for event in events
        ],
    )
