"""Strict response contracts for protected, global Baal Gateway reads."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

_Address = Annotated[str, StringConstraints(pattern=r"^0x[0-9a-fA-F]{40}$")]
_UintDecimal = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,77})$")]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class BaalFrameworkInfo(_StrictModel):
    key: Literal["moloch_v3_baal"]
    name: str = Field(min_length=1, max_length=120)
    chain: Literal["gnosis"]


class BaalAuthorizationError(_StrictModel):
    """Authentication denial returned by the Gateway policy middleware."""

    error: Literal["Unauthorized"]
    reason: str | None = Field(max_length=100)


class BaalGovernanceConfig(_StrictModel):
    framework: BaalFrameworkInfo
    chain_id: Literal[100]
    config: BaalGovernanceConfigValues


class BaalGovernanceConfigValues(_StrictModel):
    baal_version: str = Field(min_length=1, max_length=64)
    total_shares: _UintDecimal
    total_loot: _UintDecimal
    proposal_count: int = Field(ge=0)
    shares_token: _Address | None
    loot_token: _Address | None
    avatar: _Address | None
    voting_period: int = Field(ge=0)
    grace_period: int = Field(ge=0)
    proposal_offering: int = Field(ge=0)
    quorum_percent: int = Field(ge=0, le=100)
    sponsor_threshold: int = Field(ge=0)
    min_retention_percent: int = Field(ge=0, le=100)


class BaalProposal(_StrictModel):
    proposal_id: _UintDecimal
    lifecycle: Literal[
        "submitted",
        "sponsored",
        "voting",
        "grace",
        "ready",
        "executed",
        "defeated",
        "cancelled",
        "unknown",
    ]
    title: str | None = Field(max_length=200)
    details: str | None = Field(max_length=4000)
    yes_votes: _UintDecimal
    no_votes: _UintDecimal
    voting_starts: int | None = Field(ge=0)
    voting_ends: int | None = Field(ge=0)
    grace_ends: int | None = Field(ge=0)
    expiration: int | None = Field(ge=0)
    passed: bool | None
    action_failed: bool | None


class BaalProposalList(_StrictModel):
    framework: Literal["moloch_v3_baal"]
    chain_id: Literal[100]
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0, le=100)
    limit: int = Field(ge=1, le=100)
    proposals: list[BaalProposal] = Field(max_length=100)

    @model_validator(mode="after")
    def counts_match_page(self) -> "BaalProposalList":
        if self.returned_count != len(self.proposals):
            raise ValueError("returned_count must match the proposal page length")
        if self.returned_count != min(self.total_count, self.limit):
            raise ValueError("returned_count must match the bounded total")
        return self


class BaalProposalDetail(_StrictModel):
    framework: Literal["moloch_v3_baal"]
    chain_id: Literal[100]
    proposal: BaalProposal


class BaalMember(_StrictModel):
    wallet: _Address
    shares: _UintDecimal
    loot: _UintDecimal
    delegate: _Address | None


class BaalMemberDetail(_StrictModel):
    framework: Literal["moloch_v3_baal"]
    chain_id: Literal[100]
    member: BaalMember


class BaalConfigEnvelope(_StrictModel):
    data: BaalGovernanceConfig


class BaalProposalListEnvelope(_StrictModel):
    data: BaalProposalList


class BaalProposalDetailEnvelope(_StrictModel):
    data: BaalProposalDetail


class BaalMemberDetailEnvelope(_StrictModel):
    data: BaalMemberDetail

