
"""Define API models for managed MCP tools."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ToolKind = Literal["read", "write"]


class ToolRecord(BaseModel):
    """Represent a registered MCP tool configuration.

    Attributes:
        name (str): Public MCP tool name.
        description (str): Tool description.
        handler (str): Approved backend handler name.
        kind (ToolKind): Read or write classification.
        enabled (bool): Whether the tool is enabled.
        built_in (bool): Whether the tool is system-managed.
        deleted (bool): Whether the record is soft-deleted.

    Functions:
        None.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    handler: str
    kind: ToolKind
    enabled: bool
    built_in: bool
    deleted: bool = False


class CreateToolRequest(BaseModel):
    """Represent a request to register an approved handler.

    Attributes:
        name (str): Tool name to register.
        description (str): Description exposed to administrators.
        handler (str): Existing approved backend handler.
        kind (ToolKind): Read or write classification.

    Functions:
        None.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    description: str = Field(
        min_length=1,
        max_length=2000,
    )
    handler: str = Field(min_length=1, max_length=100)
    kind: ToolKind


class UpdateToolRequest(BaseModel):
    """Represent editable tool configuration fields.

    Attributes:
        description (str | None): Replacement description.
        enabled (bool | None): Replacement enabled status.

    Functions:
        None.
    """

    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )
    enabled: bool | None = None


class ToolStatusRequest(BaseModel):
    """Represent an enable or disable request.

    Attributes:
        enabled (bool): Requested tool availability.

    Functions:
        None.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool
