"""Strict response models for private Field Collector review projections."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


def _response_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_MobileResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_MobileResponseDateTime = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]
_MobileFormValidationStatus = Literal["unassessed", "active", "retired_review"]
_MobileConsentValidationStatus = Literal["unassessed", "not_required", "granted"]
_MobileEligibilityReason = Literal[
    "transport_pending",
    "review_required",
    "participant_link_revoked",
    "consent_unassessed",
    "eligible",
    "consent_not_effective_at_collection",
    "consent_expired_after_collection",
    "consent_no_longer_active",
    "consent_expired",
    "withdrawn_after_collection",
]


class MobileCollectionReviewSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _MobileResponseUUID
    location_id: _MobileResponseUUID
    form_id: str | None = Field(max_length=200)
    form_version: str | None = Field(max_length=50)
    collection_type: str = Field(max_length=100)
    collected_at: _MobileResponseDateTime
    synced_at: _MobileResponseDateTime | None
    form_validation_status: _MobileFormValidationStatus
    consent_validation_status: _MobileConsentValidationStatus
    form_review_required: bool = Field(strict=True)
    form_revision_id: _MobileResponseUUID | None
    form_name: str | None = Field(max_length=300)
    form_revision_status: Literal["active", "retired", "inactive"] | None
    eligible_for_use: bool = Field(strict=True)
    eligibility_reason: _MobileEligibilityReason
    review_state: Literal["pending_review", "blocked_by_eligibility"]


class MobileCollectionReviewQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: list[MobileCollectionReviewSummaryResponse] = Field(max_length=100)
    location_id: _MobileResponseUUID

    @model_validator(mode="after")
    def validate_location_and_review_scope(self):
        for row in self.data:
            if row.location_id != self.location_id:
                raise ValueError("collection location does not match requested scope")
            if row.review_state != (
                "pending_review" if row.form_review_required else "blocked_by_eligibility"
            ):
                raise ValueError("collection review state does not match review requirement")
            if row.eligible_for_use != (row.eligibility_reason == "eligible"):
                raise ValueError("collection eligibility reason does not match eligibility")
            if row.eligible_for_use:
                raise ValueError("eligible collection is outside the review queue")
        return self
