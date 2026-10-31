"""Strict response models for private Field Collector review projections."""

import json
from datetime import datetime
from typing import Annotated, Any, Literal
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


class MobileCollectionReviewEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    source: str = Field(min_length=1, max_length=1000)
    basis: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_non_blank_evidence(self):
        if not self.source.strip() or not self.basis.strip():
            raise ValueError("review evidence text must not be blank")
        return self


class MobileCollectionReviewEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _MobileResponseUUID
    actor_operator_id: _MobileResponseUUID
    decision: Literal["reviewed", "needs_follow_up", "ineligibility_acknowledged"]
    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[MobileCollectionReviewEvidenceResponse] = Field(min_length=1, max_length=20)
    created_at: _MobileResponseDateTime

    @model_validator(mode="after")
    def validate_non_blank_reason(self):
        if not self.reason.strip():
            raise ValueError("review reason must not be blank")
        return self


class MobileCollectionReviewDetailResponseData(MobileCollectionReviewSummaryResponse):
    """Strict bounded collection detail; form payload keys remain form-defined."""

    consent_policy_status: Literal["unclassified", "required", "not_required"] | None
    photo_count: int = Field(strict=True, ge=0)
    payload: dict[str, Any]
    review_events: list[MobileCollectionReviewEventResponse] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_review_scope(self):
        if self.review_state != (
            "pending_review" if self.form_review_required else "blocked_by_eligibility"
        ):
            raise ValueError("collection review state does not match review requirement")
        if self.eligible_for_use != (self.eligibility_reason == "eligible"):
            raise ValueError("collection eligibility reason does not match eligibility")
        if self.eligible_for_use:
            raise ValueError("eligible collection is outside the review queue")
        try:
            payload_size = len(
                json.dumps(self.payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("collection payload must be JSON serializable") from exc
        if payload_size > 524288:
            raise ValueError("collection payload exceeds the 512 KiB response limit")
        return self


class MobileCollectionReviewDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: MobileCollectionReviewDetailResponseData


class MobileCollectionDispositionCollectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    sync_status: Literal["synced"]
    form_id: str | None = Field(max_length=200)
    form_version: str | None = Field(max_length=50)
    has_participant_link: bool = Field(strict=True)
    has_collection_consent_reference: bool = Field(strict=True)
    has_sync_consent_reference: bool = Field(strict=True)
    payload_bytes: int = Field(ge=0, strict=True)
    payload_field_count: int = Field(ge=0, strict=True)
    photo_reference_count: int = Field(ge=0, strict=True)
    has_coordinates: bool = Field(strict=True)


class MobileCollectionDispositionMediaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    object_count: int = Field(ge=0, strict=True)
    total_bytes: int = Field(ge=0, strict=True)
    by_status: dict[Literal["uploaded", "attached", "expired"], int]

    @model_validator(mode="after")
    def validate_counts(self):
        if any(count < 0 for count in self.by_status.values()):
            raise ValueError("private media counts must not be negative")
        if sum(self.by_status.values()) != self.object_count:
            raise ValueError("private media status counts do not match total")
        return self


class MobileCollectionDispositionActivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    total: int = Field(ge=0, strict=True)
    by_status: dict[Literal["draft", "submitted", "verified", "published", "rejected"], int]

    @model_validator(mode="after")
    def validate_counts(self):
        if any(count < 0 for count in self.by_status.values()):
            raise ValueError("canonical activity counts must not be negative")
        if sum(self.by_status.values()) != self.total:
            raise ValueError("canonical activity status counts do not match total")
        return self


class MobileCollectionDispositionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    collection_id: _MobileResponseUUID
    location_id: _MobileResponseUUID
    eligible_for_use: bool = Field(strict=True)
    eligibility_reason: _MobileEligibilityReason
    inventory_scope: Literal["known_direct_lineage_only"]
    collection: MobileCollectionDispositionCollectionResponse
    private_media: MobileCollectionDispositionMediaResponse
    canonical_activity: MobileCollectionDispositionActivityResponse
    workflow_event_count: int = Field(ge=0, strict=True)
    review_event_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_inventory_scope(self):
        if self.eligible_for_use != (self.eligibility_reason == "eligible"):
            raise ValueError("collection eligibility reason does not match eligibility")
        if self.eligible_for_use:
            raise ValueError("eligible collection is outside the disposition inventory")
        return self


class MobileCollectionDispositionInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: MobileCollectionDispositionInventoryData
