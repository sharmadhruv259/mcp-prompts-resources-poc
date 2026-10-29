
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class CacheConfig(BaseModel):
    """Define caching behavior for an agent.

    Attributes:
        enabled (bool): Whether tool-result caching is enabled.
        ttl_seconds (int): Duration for which cached results remain valid.

    Functions:
        None.
    """

    enabled: bool = False
    ttl_seconds: int = Field(default=300, ge=1, le=3600)


class AgentConfig(BaseModel):
    """Define a user-created AI agent and its MCP access.

    Attributes:
        id (str): Unique identifier for the agent.
        name (str): Display name of the agent.
        description (str): Purpose of the agent.
        system_prompt (str): Custom instructions for the agent.
        tool_access (str): Whether all or selected tools are available.
        allowed_tools (list[str]): Tools permitted in selected mode.
        cache (CacheConfig): Tool-result caching configuration.
        metadata (dict[str, Any]): Optional agent metadata.

    Functions:
        validate_tool_access: Validate selected tool configuration.
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)

    tool_access: Literal["all", "selected"] = "all"
    allowed_tools: list[str] = Field(default_factory=list)

    cache: CacheConfig = Field(default_factory=CacheConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tool_access(self) -> "AgentConfig":
        """Validate tool access settings.

        Args:
            None.

        Returns:
            AgentConfig: The validated agent configuration.

        Raises:
            ValueError: If selected mode has no permitted tools.
        """
        if self.tool_access == "selected" and not self.allowed_tools:
            raise ValueError(
                "allowed_tools cannot be empty when "
                "tool_access is 'selected'."
            )

        return self
