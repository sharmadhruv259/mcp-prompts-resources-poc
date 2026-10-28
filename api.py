
"""Expose the MCP Playground agent through FastAPI."""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp import Client
from pydantic import BaseModel, Field, model_validator

from agent import CustomTool, run_agent
from server import mcp


logger = logging.getLogger(__name__)

app = FastAPI(title="MCP Playground API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    """Represent a frontend agent request.

    Attributes:
        message (str): User's question.
        mode (Literal): Automatic or manual tool selection.
        selected_tool (str | None): Selected manual tool.
        custom_tools (list[CustomTool]): MCP-backed custom tools.

    Functions:
        validate_request: Validate chat and tool selection fields.
    """

    message: str = Field(min_length=1, max_length=10000)
    mode: Literal["auto", "manual"] = "auto"
    selected_tool: str | None = None
    custom_tools: list[CustomTool] = Field(
        default_factory=list,
        max_length=30,
    )

    @model_validator(mode="after")
    def validate_request(self) -> "ChatRequest":
        """Validate the chat request and selected tool.

        Args:
            None: Uses the current model fields.

        Returns:
            ChatRequest: Validated chat request.

        Raises:
            ValueError: If message or selection is invalid.
        """
        self.message = self.message.strip()

        if not self.message:
            raise ValueError("Message cannot be empty.")

        if self.mode == "manual":
            if not self.selected_tool:
                raise ValueError(
                    "Select a tool in Manual mode."
                )

            self.selected_tool = (
                self.selected_tool.strip()
            )

            if not self.selected_tool:
                raise ValueError(
                    "Select a tool in Manual mode."
                )

        else:
            # Auto mode does not force a selected function.
            self.selected_tool = None

        custom_names = [
            tool.name for tool in self.custom_tools
        ]

        if len(custom_names) != len(set(custom_names)):
            raise ValueError(
                "Duplicate custom tool names are not allowed."
            )

        return self


class ExecutionEvent(BaseModel):
    """Represent an agent execution event.

    Attributes:
        id (str): Unique execution event identifier.
        tool (str): Function or operation name.
        status (Literal): Execution status.
        description (str): Human-readable execution details.

    Functions:
        None: Validation is performed by Pydantic.
    """

    id: str
    tool: str
    status: Literal["running", "completed", "failed"]
    description: str


class ChatResponse(BaseModel):
    """Represent the agent's answer and execution history.

    Attributes:
        answer (str): Final generated answer.
        events (list[ExecutionEvent]): Execution history.

    Functions:
        None: Validation is performed by Pydantic.
    """

    answer: str
    events: list[ExecutionEvent]


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the backend health status.

    Args:
        None: No parameters are required.

    Returns:
        dict[str, str]: Backend health information.

    Raises:
        None: No expected application exceptions.
    """
    return {"status": "ok"}


@app.post(
    "/api/chat",
    response_model=ChatResponse,
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run a Groq agent request through the MCP client.

    Args:
        request (ChatRequest): Validated frontend request.

    Returns:
        ChatResponse: Generated answer and execution events.

    Raises:
        HTTPException: If tool selection or execution fails.
    """
    try:
        async with Client(mcp) as client:
            answer, events = await run_agent(
                client=client,
                question=request.message,
                mode=request.mode,
                selected_tool=request.selected_tool,
                custom_tools=request.custom_tools,
            )

        return ChatResponse(
            answer=answer,
            events=[
                ExecutionEvent.model_validate(event)
                for event in events
            ],
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "MCP Playground agent execution failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Agent execution failed. "
                "Check the backend terminal for details."
            ),
        ) from exc
