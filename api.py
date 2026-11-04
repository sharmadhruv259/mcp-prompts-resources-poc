
"""Expose custom Groq agents and MCP capabilities through FastAPI."""

import os
import logging
import sqlite3
from typing import Literal
from fastapi import Depends

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from auth.routes import router as auth_router
from mcp import Client
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from agent import AgentAuthorizationError, run_agent
from models.agent_config import AgentConfig
from server import mcp
from services.agent_registry import AgentRegistry
from services.default_assistant import DefaultAssistant
from services.mcp_discovery import (
    MCPCapabilities,
    discover_mcp_capabilities,
    filter_enabled_capabilities,
)
from services.tool_registry import tool_registry
from auth.dependencies import current_user
from auth.permissions import Role
from models.user import User
from auth.permissions import has_permission
from auth.admin_routes import router as admin_router
from auth.user_management_routes import (
    router as user_management_router,
)
from auth.tool_management_routes import (
    router as tool_management_router,
)

logger = logging.getLogger(__name__)

registry = AgentRegistry(
    db_path=os.getenv("DATABASE_PATH", "data/agents.db")
)

app = FastAPI(
    title="MCP Playground API",
    description=(
        "Create, manage, and execute custom AI agents "
        "using Groq and MCP capabilities."
    ),
    version="0.4.0",
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(user_management_router)
app.include_router(tool_management_router)

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
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)



class AgentUpdateRequest(BaseModel):
    """Represent a version-controlled agent update request.

    Attributes:
        agent (AgentConfig): Replacement agent configuration.
        expected_version (int): Version expected by the client.
    """

    agent: AgentConfig
    expected_version: int = Field(ge=1)


class ChatRequest(BaseModel):
    """Represent a default or custom agent chat request.

    Attributes:
        message (str): User's question.
        agent_id (str | None): Identifier of a saved agent.
        agent (AgentConfig | None): Legacy inline agent configuration.

    Functions:
        validate_message: Validate and normalize the message.
        validate_agent_id: Normalize the saved agent identifier.
        validate_agent_selection: Reject conflicting agent sources.
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
        """Validate mutually exclusive agent selection.

        Args:
            None.

        Returns:
            ChatRequest: Validated chat request.

        Raises:
            ValueError: If both agent selection fields are provided.
        """
        if (
            self.agent_id is not None
            and self.agent is not None
        ):
            raise ValueError(
                "Provide either agent_id or agent, not both."
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
    """Represent an assistant's response.

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


class AgentReviewRequest(BaseModel):
    """Represent an agent approval workflow request.

    Attributes:
        expected_version (int): Agent configuration version being reviewed.
    """

    expected_version: int = Field(ge=1)


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
def create_agent(
    agent: AgentConfig,
    user: User = Depends(current_user),
) -> AgentConfig:
    """Create a draft AI agent owned by the authenticated user.

    Args:
        agent (AgentConfig): Submitted agent configuration.
        user (User): Authenticated agent creator.

    Returns:
        AgentConfig: Saved agent configuration.

    Raises:
        HTTPException: If the agent already exists or storage fails.
    """
    try:
        saved_agent = registry.create_agent(
            agent=agent,
            owner_id=user.id,
        )

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
def list_agents(
    user: User = Depends(current_user),
) -> list[AgentConfig]:
    """List agents accessible to the authenticated user.

    Args:
        user (User): Authenticated user requesting agents.

    Returns:
        list[AgentConfig]: Agent configurations visible to the user.

    Raises:
        sqlite3.Error: If database retrieval fails.
    """
    if user.role == Role.ADMIN:
        return registry.list_agents()

    records = registry.list_agent_records(
        owner_id=user.id
    )

    return [
        record["configuration"]
        for record in records
    ]


@app.get("/api/agents/records")
def list_agent_records(
    user: User = Depends(current_user),
) -> list[dict]:
    """List agent records with approval metadata.

    Args:
        user (User): Authenticated user requesting records.

    Returns:
        list[dict]: Agent records visible to the user.

    Raises:
        HTTPException: If access is denied.
    """
    if has_permission(user.role, "agents:review"):
        return registry.list_agent_records()

    return registry.list_agent_records(owner_id=user.id)



@app.get(
    "/api/agents/{agent_id}",
    response_model=AgentConfig,
)
def get_agent(
    agent_id: str,
    user: User = Depends(current_user),
) -> AgentConfig:
    """Retrieve an agent accessible to the authenticated user.

    Args:
        agent_id (str): Identifier of the requested agent.
        user (User): Authenticated user requesting the agent.

    Returns:
        AgentConfig: Authorized agent configuration.

    Raises:
        HTTPException: If the agent does not exist or access is denied.
    """
    record = registry.get_agent_record(agent_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    if user.role != Role.ADMIN and record["owner_id"] != user.id:
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    return record["configuration"]



@app.put(
    "/api/agents/{agent_id}",
    response_model=AgentConfig,
)
def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    user: User = Depends(current_user),
) -> AgentConfig:
    """Update an owned agent with optimistic version checking.

    Args:
        agent_id (str): Identifier of the agent to update.
        request (AgentUpdateRequest): New configuration and expected version.
        user (User): Authenticated user making the request.

    Returns:
        AgentConfig: Successfully updated agent configuration.

    Raises:
        HTTPException: If the agent is inaccessible, the ID changes,
            the version conflicts, or database persistence fails.
    """
    agent = request.agent

    if agent.id != agent_id:
        raise HTTPException(
            status_code=422,
            detail="Agent ID cannot be changed.",
        )

    try:
        record = registry.get_agent_record(agent_id)

        # Avoid revealing the existence of another user's agent.
        if record is None or record["owner_id"] != user.id:
            raise HTTPException(
                status_code=404,
                detail="Agent not found.",
            )

        if record["version"] != request.expected_version:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Agent configuration has changed. "
                    "Reload the agent and retry with its current version."
                ),
            )

        # Ownership and version are verified again atomically in SQL.
        updated_agent = registry.update_agent(
            agent_id=agent_id,
            agent=agent,
            owner_id=user.id,
            expected_version=request.expected_version,
        )

        if updated_agent is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Agent was modified or is no longer available. "
                    "Reload the agent before retrying."
                ),
            )

        return updated_agent

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to update agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update agent.",
        ) from exc



@app.delete(
    "/api/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_agent(
    agent_id: str,
    user: User = Depends(current_user),
) -> Response:
    """Delete an owned agent through the registry.

    Args:
        agent_id (str): Identifier of the agent to delete.
        user (User): Authenticated user requesting deletion.

    Returns:
        Response: Empty HTTP 204 response.

    Raises:
        HTTPException: If the agent is inaccessible or deletion fails.
    """
    try:
        deleted = registry.delete_agent(
            agent_id=agent_id,
            owner_id=user.id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Agent not found.",
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except sqlite3.Error as exc:
        logger.exception("Failed to delete agent: %s", agent_id)
        raise HTTPException(
            status_code=500,
            detail="Unable to delete agent.",
        ) from exc


@app.get(
    "/api/mcp/capabilities",
    response_model=MCPCapabilities,
)
async def get_mcp_capabilities() -> MCPCapabilities:
    """Discover MCP capabilities enabled by an administrator.

    Args:
        None.

    Returns:
        MCPCapabilities: Enabled MCP tools, resources, and prompts.

    Raises:
        HTTPException: If MCP discovery or registry filtering fails.
    """
    try:
        async with Client(mcp) as client:
            capabilities = await discover_mcp_capabilities(
                client
            )

            enabled_capabilities = filter_enabled_capabilities(
                capabilities,
                tool_registry,
            )

            return enabled_capabilities

    except Exception as exc:
        logger.exception(
            "Failed to discover enabled MCP capabilities."
        )

        raise HTTPException(
            status_code=502,
            detail="Unable to discover MCP capabilities.",
        ) from exc

@app.post(
    "/api/chat",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    user: User = Depends(current_user),
) -> ChatResponse:
    """Execute the default assistant or an authorized approved agent.

    Args:
        request (ChatRequest): Message and agent selection.
        user (User): Authenticated user requesting execution.

    Returns:
        ChatResponse: Generated answer and execution events.

    Raises:
        HTTPException: If authentication, agent access,
            approval validation, or execution fails.
    """
    # Inline agent configurations must never bypass approval.
    if request.agent is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Inline agent configurations are not supported. "
                "Provide the ID of a saved, approved agent."
            ),
        )

    # Preserve Default Assistant functionality for authenticated users.
    if request.agent_id is None:
        try:
            assistant = DefaultAssistant()

            answer = await assistant.chat(
                request.message
            )

            return ChatResponse(
                answer=answer,
                events=[],
            )

        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        except Exception as exc:
            logger.exception(
                "Default Assistant execution failed"
            )

            raise HTTPException(
                status_code=502,
                detail="Unable to execute the Default Assistant.",
            ) from exc

    # Load the full record, including ownership and approval status.
    try:
        record = registry.get_agent_record(
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

    # Only the owner or an Admin may access the agent.
    # Return 404 for inaccessible agents to avoid exposing their IDs.
    if record is None or (
        record["owner_id"] != user.id
        and user.role != Role.ADMIN
    ):
        raise HTTPException(
            status_code=404,
            detail="Agent not found.",
        )

    # Approval is mandatory before execution.
    if record["approval_status"] != "approved":
        raise HTTPException(
            status_code=403,
            detail="Agent must be approved before execution.",
        )

    selected_agent = record["configuration"]
    approved_version = record["version"]
    approved_owner_id = record["owner_id"]
    selected_agent_id = request.agent_id

    async def validate_agent_authorization() -> None:
        """Recheck saved-agent authorization against the current registry.

        Args:
            None.

        Returns:
            None: Agent remains approved, accessible, and unchanged.

        Raises:
            AgentAuthorizationError: If the agent was deleted, its
                approval or owner changed, or its version changed.
            sqlite3.Error: If the registry cannot be read.
        """
        current_record = registry.get_agent_record(selected_agent_id)

        if current_record is None:
            raise AgentAuthorizationError(
                "Agent no longer exists."
            )

        if current_record["owner_id"] != approved_owner_id or (
            current_record["owner_id"] != user.id
            and user.role != Role.ADMIN
        ):
            raise AgentAuthorizationError(
                "Agent ownership or access has changed."
            )

        if current_record["approval_status"] != "approved":
            raise AgentAuthorizationError(
                "Agent is no longer approved."
            )

        if current_record["version"] != approved_version:
            raise AgentAuthorizationError(
                "Agent configuration has changed."
            )

    validation_error: str | None = None
    authorization_error: str | None = None
    answer: str | None = None
    events: list[dict[str, str]] = []

    try:
        async with Client(mcp) as client:
            try:
                answer, events = await run_agent(
                    client=client,
                    question=request.message,
                    agent=selected_agent,
                    agent_version=approved_version,
                    validate_authorization=validate_agent_authorization,
                )

            except AgentAuthorizationError as exc:
                # Catch authorization errors inside the MCP context.
                authorization_error = str(exc)

            except ValueError as exc:
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

    if authorization_error is not None:
        logger.warning(
            "Agent authorization changed during execution: "
            "agent_id=%s, version=%s",
            selected_agent.id,
            approved_version,
        )

        raise HTTPException(
            status_code=403,
            detail=authorization_error,
        )

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



@app.post(
    "/api/agents/{agent_id}/submit",
    status_code=status.HTTP_200_OK,
)
def submit_agent_for_review(
    agent_id: str,
    request: AgentReviewRequest,
    user: User = Depends(current_user),
) -> dict:
    """Submit an owned draft agent for approval.

    Args:
        agent_id (str): Identifier of the agent.
        request (AgentReviewRequest): Expected configuration version.
        user (User): Authenticated user submitting the agent.

    Returns:
        dict: Agent ID, approval status, and configuration version.

    Raises:
        HTTPException: If the agent is inaccessible, not a draft,
            has changed version, or database submission fails.
    """
    try:
        submitted = registry.submit_agent(
            agent_id=agent_id,
            owner_id=user.id,
            expected_version=request.expected_version,
        )

        if not submitted:
            record = registry.get_agent_record(agent_id)

            if record is None or record["owner_id"] != user.id:
                raise HTTPException(
                    status_code=404,
                    detail="Agent not found.",
                )

            raise HTTPException(
                status_code=409,
                detail=(
                    "Agent must be in draft status and "
                    "the expected version must match."
                ),
            )

        return {
            "agent_id": agent_id,
            "approval_status": "pending",
            "version": request.expected_version,
        }

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to submit agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to submit agent for review.",
        ) from exc

@app.post(
    "/api/agents/{agent_id}/approve",
    status_code=status.HTTP_200_OK,
)
def approve_agent_for_review(
    agent_id: str,
    request: AgentReviewRequest,
    user: User = Depends(current_user),
) -> dict:
    """Approve a pending agent using an authorized reviewer.

    Args:
        agent_id (str): Identifier of the agent to approve.
        request (AgentReviewRequest): Expected configuration version.
        user (User): Authenticated reviewer.

    Returns:
        dict: Approved agent ID, status, version, and reviewer ID.

    Raises:
        HTTPException: If permission is denied, the agent is
            inaccessible, the version differs, or approval fails.
    """
    if not has_permission(user.role, "agents:review"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to review agents.",
        )

    try:
        record = registry.get_agent_record(agent_id)

        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Agent not found.",
            )

        if record["owner_id"] == user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot approve your own agent.",
            )

        approved = registry.approve_agent(
            agent_id=agent_id,
            reviewer_id=user.id,
            expected_version=request.expected_version,
        )

        if not approved:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Agent must be pending and "
                    "the expected version must match."
                ),
            )

        return {
            "agent_id": agent_id,
            "approval_status": "approved",
            "version": request.expected_version,
            "approved_by": user.id,
        }

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to approve agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to approve agent.",
        ) from exc

@app.post(
    "/api/agents/{agent_id}/reject",
    status_code=status.HTTP_200_OK,
)
def reject_agent_for_review(
    agent_id: str,
    request: AgentReviewRequest,
    user: User = Depends(current_user),
) -> dict:
    """Reject a pending agent using an authorized reviewer.

    Args:
        agent_id (str): Identifier of the agent to reject.
        request (AgentReviewRequest): Expected configuration version.
        user (User): Authenticated reviewer.

    Returns:
        dict: Rejected agent ID, status, version, and reviewer ID.

    Raises:
        HTTPException: If permission is denied, the agent is
            inaccessible, its version differs, or rejection fails.
    """
    if not has_permission(user.role, "agents:review"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to review agents.",
        )

    try:
        record = registry.get_agent_record(agent_id)

        if record is None:
            raise HTTPException(
                status_code=404,
                detail="Agent not found.",
            )

        if record["owner_id"] == user.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot reject your own agent.",
            )

        rejected = registry.reject_agent(
            agent_id=agent_id,
            reviewer_id=user.id,
            expected_version=request.expected_version,
        )

        if not rejected:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Agent must be pending and "
                    "the expected version must match."
                ),
            )

        return {
            "agent_id": agent_id,
            "approval_status": "rejected",
             "version": request.expected_version,
             "reviewed_by": user.id,
    }

    except sqlite3.Error as exc:
        logger.exception(
            "Failed to reject agent: %s",
            agent_id,
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to reject agent.",
        ) from exc
