"""Shared strict contracts for private AI-summary Gateway projections."""

import re
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

_SOURCE_TABLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def _strict_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("UUID values must be strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("UUID value is invalid") from exc


StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]
AiSummaryDraftType = Literal["operations", "financial", "environmental", "combined"]
AiSummaryLifecycle = Literal["draft", "submitted", "verified", "published", "rejected"]


class StrictAiSummaryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AiSummarySourceReference(StrictAiSummaryModel):
    record_ids: list[StrictUuid] = Field(max_length=50)
    row_count: int = Field(ge=0, le=9_223_372_036_854_775_807)
    truncated: bool
    scope: Literal["location", "network", "location_or_network"] | None = None

    @model_validator(mode="after")
    def validate_counts(self):
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError("Source-reference IDs must be unique")
        if self.row_count < len(self.record_ids):
            raise ValueError("Source-reference row count is smaller than its sample")
        if self.truncated != (self.row_count > len(self.record_ids)):
            raise ValueError("Source-reference truncation flag is inconsistent")
        return self


class AiSummaryDraftRequest(StrictAiSummaryModel):
    summary_type: AiSummaryDraftType
    request_id: StrictUuid


class AiSummaryDraftResponse(StrictAiSummaryModel):
    summary_id: StrictUuid
    location_id: StrictUuid
    summary_type: AiSummaryDraftType
    content: str = Field(min_length=1, max_length=20_000)
    source_tables: list[str] = Field(min_length=1, max_length=20)
    source_references: dict[str, AiSummarySourceReference] = Field(
        max_length=20,
        json_schema_extra={"propertyNames": {"pattern": _SOURCE_TABLE_PATTERN.pattern}},
    )
    model_version: str | None = Field(max_length=100)
    created_at: AwareDatetime | None
    resulting_status: AiSummaryLifecycle
    replayed: bool

    @model_validator(mode="after")
    def validate_source_tables(self):
        if any(_SOURCE_TABLE_PATTERN.fullmatch(table) is None for table in self.source_tables):
            raise ValueError("Source-table names are invalid")
        if len(set(self.source_tables)) != len(self.source_tables):
            raise ValueError("Source-table names must be unique")
        if any(_SOURCE_TABLE_PATTERN.fullmatch(table) is None for table in self.source_references):
            raise ValueError("Source-reference table names are invalid")
        if not set(self.source_references).issubset(self.source_tables):
            raise ValueError("Source references must match declared source tables")
        return self


class AiSummaryReviewDecisionRequest(StrictAiSummaryModel):
    decision: Literal["approve", "reject"]
    request_id: StrictUuid
    reason_code: Literal[
        "approved_after_review",
        "insufficient_evidence",
        "privacy_concern",
        "unsupported_claim",
        "other",
    ]

    @model_validator(mode="after")
    def validate_decision_reason(self):
        if (self.decision == "approve") != (self.reason_code == "approved_after_review"):
            raise ValueError("Review decision and reason code do not match")
        return self


class AiSummaryReviewDecisionResponse(StrictAiSummaryModel):
    review_id: StrictUuid
    summary_id: StrictUuid
    decision: Literal["approve", "reject"]
    resulting_status: Literal["verified", "rejected"]
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_resulting_status(self):
        expected_status = "verified" if self.decision == "approve" else "rejected"
        if self.resulting_status != expected_status:
            raise ValueError("Review decision and resulting lifecycle status do not match")
        return self


class AiSummaryContractError(StrictAiSummaryModel):
    error: str
