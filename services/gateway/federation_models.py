"""Public response contracts for the federation directory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FederationNodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_name: str
    node_url: str
    trust_level: str
    shared_capabilities: Any
    last_sync_at: str | None
    status: str
    created_at: str


class FederationNodesPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[FederationNodeResponse]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0, le=10_000)
    has_more: bool
    next_offset: int | None
    continuation_capped: bool
