"""OIDC route registration for location-scoped governance reads and actions."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


def _response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


_GovernanceResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]

_GOVERNANCE_TENSION_TYPE = Literal[
    "unmet_interest",
    "unclear_accountability",
    "authority_gap",
    "authority_conflict",
    "commitment_risk",
    "representation_gap",
    "consent_gap",
    "evidence_gap",
    "harm_risk",
    "policy_gap",
    "cross_circle_dependency",
    "role_overload",
]
_GOVERNANCE_TENSION_STATUS = Literal[
    "draft", "submitted", "triaged", "in_progress", "resolved", "deferred", "rejected", "closed"
]


class GovernanceTensionCreateRequest(BaseModel):
    """Strict operator request for a location-scoped tension draft."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    title: str = Field(min_length=1, max_length=255, strict=True)
    description: str = Field(min_length=1, max_length=10000, strict=True)
    tension_type: _GOVERNANCE_TENSION_TYPE
    severity: int = Field(ge=1, le=5, strict=True)
    urgency: int = Field(ge=1, le=5, strict=True)

    @model_validator(mode="after")
    def validate_text(self):
        if not self.title.strip() or not self.description.strip():
            raise ValueError("title and description must not be blank")
        if "\x00" in self.title or "\x00" in self.description:
            raise ValueError("tension text cannot contain null characters")
        return self


class _GovernanceTensionMutationResult(BaseModel):
    """Exact nine-field migration-437 result, including its private correlation key."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    tension_id: _GovernanceResponseUUID
    tension_key: str = Field(min_length=1, max_length=120, strict=True)
    title: str = Field(min_length=1, max_length=255, strict=True)
    description: str = Field(min_length=1, max_length=10000, strict=True)
    tension_type: _GOVERNANCE_TENSION_TYPE
    severity: int = Field(ge=1, le=5, strict=True)
    urgency: int = Field(ge=1, le=5, strict=True)
    status: _GOVERNANCE_TENSION_STATUS
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("tension creation timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tension creation timestamp must include a timezone")
        return value

    @field_validator("tension_key")
    @classmethod
    def validate_private_key_shape(cls, value: str) -> str:
        parts = value.split(":")
        if len(parts) != 3 or parts[0] != "gateway":
            raise ValueError("tension correlation key is invalid")
        try:
            operator_id, request_id = UUID(parts[1]), UUID(parts[2])
        except ValueError as exc:
            raise ValueError("tension correlation key is invalid") from exc
        if parts[1] != str(operator_id) or parts[2] != str(request_id):
            raise ValueError("tension correlation key is invalid")
        return value


class _GovernanceTensionResponseBase(BaseModel):
    """Public tension fields shared by create and submit receipts."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    tension_id: _GovernanceResponseUUID
    title: str = Field(min_length=1, max_length=255, strict=True)
    description: str = Field(min_length=1, max_length=10000, strict=True)
    tension_type: _GOVERNANCE_TENSION_TYPE
    severity: int = Field(ge=1, le=5, strict=True)
    urgency: int = Field(ge=1, le=5, strict=True)
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("tension creation timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tension creation timestamp must include a timezone")
        return value


class GovernanceTensionMutationResponse(_GovernanceTensionResponseBase):
    """Public creation receipt; the private operator/request key is excluded."""

    status: _GOVERNANCE_TENSION_STATUS


class GovernanceTensionSubmittedResponse(_GovernanceTensionResponseBase):
    """Public submission receipt with the only valid resulting lifecycle state."""

    status: Literal["submitted"]


class GovernanceTensionActionError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


def _request_schema(model, *, optional_non_null_fields=()):
    """Build a request schema without advertising None for omitted-only fields."""
    schema = model.model_json_schema()
    for field_name in optional_non_null_fields:
        schema.get("properties", {}).get(field_name, {}).pop("default", None)
    return schema


_ROLE_STATUS = Literal[
    "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
]
_ASSIGNMENT_STATUS = Literal["proposed", "active", "suspended", "ended", "rejected"]
_ASSIGNMENT_TYPE = Literal["primary", "delegate", "representative", "interim"]
_CIRCLE_STATUS = Literal["draft", "submitted", "active", "suspended", "rejected", "retired"]
_GOVERNANCE_SCOPE = Literal[
    "network",
    "organization",
    "location",
    "farm",
    "cooperative",
    "value_stream",
    "initiative",
    "decision",
]


class GovernanceRoleDetailRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    purpose: str
    status: _ROLE_STATUS
    effective_from: AwareDatetime | None
    effective_until: AwareDatetime | None
    review_due_at: AwareDatetime | None
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    circle_status: _CIRCLE_STATUS


class GovernanceRoleAccountabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    accountability: str
    priority: int = Field(ge=1, le=5, strict=True)
    required: bool = Field(strict=True)


class GovernanceRoleAuthorityDomainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    domain_type: str = Field(max_length=40)
    domain_key: str = Field(max_length=160)
    scope_type: _GOVERNANCE_SCOPE
    authority_level: Literal["observe", "recommend", "decide", "execute"]
    requires_human_approval: bool = Field(strict=True)


class GovernanceRoleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    role: GovernanceRoleDetailRoleResponse
    accountabilities: list[GovernanceRoleAccountabilityResponse] = Field(max_length=100)
    accountabilities_truncated: bool = Field(strict=True)
    authority_domains: list[GovernanceRoleAuthorityDomainResponse] = Field(max_length=100)
    authority_domains_truncated: bool = Field(strict=True)


class GovernanceCircleDetailItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    circle_key: str = Field(max_length=120, strict=True)
    name: str = Field(max_length=255, strict=True)
    purpose: str = Field(strict=True)
    description: str | None = Field(strict=True)
    parent_circle_id: _GovernanceResponseUUID | None
    status: _CIRCLE_STATUS


class GovernanceCircleDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    circle: GovernanceCircleDetailItemResponse


class GovernanceAssignmentProposalItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    assignment_id: _GovernanceResponseUUID
    role_id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120, strict=True)
    role_name: str = Field(max_length=255, strict=True)
    assignment_type: _ASSIGNMENT_TYPE
    status: _ASSIGNMENT_STATUS
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _parse_serialized_timestamp(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment proposal timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment proposal timestamp must include a timezone")
        return value


class GovernanceAssignmentProposalCursorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    created_at: AwareDatetime
    assignment_id: _GovernanceResponseUUID

    @field_validator("created_at", mode="before")
    @classmethod
    def _parse_serialized_cursor_timestamp(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment proposal cursor timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment proposal cursor timestamp must include a timezone")
        return value


class GovernanceAssignmentProposalPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceAssignmentProposalItemResponse] = Field(max_length=100)
    next_cursor: GovernanceAssignmentProposalCursorResponse | None

    def validate_request(
        self,
        *,
        location_id: str,
        limit: int,
        cursor_created_at: str | None,
        cursor_assignment_id: str | None,
    ):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance assignment proposal page does not match request scope or bounds")

        identities = [item.assignment_id for item in self.items]
        if len(identities) != len(set(identities)):
            raise ValueError("Governance assignment proposal page contains duplicate assignments")
        if any(
            (previous.created_at, previous.assignment_id.int)
            <= (current.created_at, current.assignment_id.int)
            for previous, current in zip(self.items, self.items[1:])
        ):
            raise ValueError("Governance assignment proposal page is not in descending order")

        if (cursor_created_at is None) != (cursor_assignment_id is None):
            raise ValueError("Governance assignment proposal input cursor is incomplete")
        if cursor_created_at is not None:
            parsed_cursor = datetime.fromisoformat(cursor_created_at.replace("Z", "+00:00"))
            cursor_key = (parsed_cursor, UUID(cursor_assignment_id).int)
            if any((item.created_at, item.assignment_id.int) >= cursor_key for item in self.items):
                raise ValueError("Governance assignment proposal page repeats its input cursor")

        if self.next_cursor is not None:
            if not self.items or len(self.items) != limit:
                raise ValueError("Governance assignment proposal continuation does not match its page")
            last = self.items[-1]
            if (
                self.next_cursor.created_at != last.created_at
                or self.next_cursor.assignment_id != last.assignment_id
            ):
                raise ValueError("Governance assignment proposal continuation does not match its last item")
        return self


class GovernanceAssignmentReviewItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    assignment_id: _GovernanceResponseUUID
    request_id: _GovernanceResponseUUID
    role_id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120, strict=True)
    role_name: str = Field(max_length=255, strict=True)
    nominee_party_id: _GovernanceResponseUUID
    nominee_name: str = Field(max_length=255, strict=True)
    nominee_status: str = Field(max_length=30, strict=True)
    submitted_by_party_id: _GovernanceResponseUUID
    submitted_by_name: str = Field(max_length=255, strict=True)
    assignment_type: _ASSIGNMENT_TYPE
    mandate: str | None = Field(strict=True)
    role_status: _ROLE_STATUS
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment review timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment review timestamp must include a timezone")
        return value


class GovernanceAssignmentReviewCursorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    created_at: AwareDatetime
    assignment_id: _GovernanceResponseUUID

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment review cursor timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment review cursor timestamp must include a timezone")
        return value


class GovernanceAssignmentReviewPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceAssignmentReviewItemResponse] = Field(max_length=100)
    next_cursor: GovernanceAssignmentReviewCursorResponse | None

    def validate_request(
        self,
        *,
        location_id: str,
        limit: int,
        cursor_created_at: str | None,
        cursor_assignment_id: str | None,
    ):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance assignment review page does not match request scope or bounds")
        assignments = [item.assignment_id for item in self.items]
        if len(assignments) != len(set(assignments)):
            raise ValueError("Governance assignment review page contains duplicate assignments")
        if any(
            (previous.created_at, previous.assignment_id.int)
            <= (current.created_at, current.assignment_id.int)
            for previous, current in zip(self.items, self.items[1:])
        ):
            raise ValueError("Governance assignment review page is not in descending order")

        if (cursor_created_at is None) != (cursor_assignment_id is None):
            raise ValueError("Governance assignment review input cursor is incomplete")
        if cursor_created_at is not None:
            parsed_cursor = datetime.fromisoformat(cursor_created_at.replace("Z", "+00:00"))
            cursor_key = (parsed_cursor, UUID(cursor_assignment_id).int)
            if any((item.created_at, item.assignment_id.int) >= cursor_key for item in self.items):
                raise ValueError("Governance assignment review page repeats its input cursor")

        if self.next_cursor is not None:
            if not self.items or len(self.items) != limit:
                raise ValueError("Governance assignment review continuation does not match its page")
            last = self.items[-1]
            if (
                self.next_cursor.created_at != last.created_at
                or self.next_cursor.assignment_id != last.assignment_id
            ):
                raise ValueError("Governance assignment review continuation does not match its last item")
        return self


class GovernanceAssignmentDecisionRequest(BaseModel):
    """Strict idempotent decision request for an independent role reviewer."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    decision_request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("reason")
    @classmethod
    def reason_must_be_nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("reason must contain 1 to 4000 valid characters")
        return value


class _GovernanceAssignmentDecisionResult(BaseModel):
    """Exact six-field migration-440 result, including its private reviewer."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    decision_id: _GovernanceResponseUUID
    assignment_id: _GovernanceResponseUUID
    decision: Literal["approve", "reject"]
    assignment_status: Literal["active", "rejected"]
    reviewer_party_id: _GovernanceResponseUUID
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment decision timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment decision timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def decision_matches_assignment_status(self):
        expected = "active" if self.decision == "approve" else "rejected"
        if self.assignment_status != expected:
            raise ValueError("assignment decision and resulting status do not match")
        return self


class _GovernanceAssignmentDecisionResponseBase(BaseModel):
    """Public decision receipt fields, excluding reviewer identity."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    decision_id: _GovernanceResponseUUID
    assignment_id: _GovernanceResponseUUID
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("assignment decision timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assignment decision timestamp must include a timezone")
        return value


class GovernanceAssignmentApprovedResponse(_GovernanceAssignmentDecisionResponseBase):
    decision: Literal["approve"]
    assignment_status: Literal["active"]


class GovernanceAssignmentRejectedResponse(_GovernanceAssignmentDecisionResponseBase):
    decision: Literal["reject"]
    assignment_status: Literal["rejected"]


class GovernanceAssignmentReviewError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


class GovernanceRoleListItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    role_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    purpose: str
    status: _ROLE_STATUS
    effective_from: AwareDatetime | None
    effective_until: AwareDatetime | None
    review_due_at: AwareDatetime | None
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    circle_status: _CIRCLE_STATUS
    active_accountability_count: int = Field(ge=0, strict=True)
    current_assignment_count: int = Field(ge=0, strict=True)
    applicable_authority_domain_count: int = Field(ge=0, strict=True)


class GovernanceRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceRoleListItemResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None


class GovernanceSummaryCircleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    circle_key: str = Field(max_length=120)
    name: str = Field(max_length=255)
    status: _CIRCLE_STATUS
    review_due_at: AwareDatetime | None
    active_role_count: int = Field(ge=0, strict=True)
    overdue_role_review_count: int = Field(ge=0, strict=True)
    active_assignment_count: int = Field(ge=0, strict=True)
    proposed_assignment_count: int = Field(ge=0, strict=True)
    active_authority_domain_count: int = Field(ge=0, strict=True)


class GovernanceSummaryTensionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    total: int = Field(ge=0, strict=True)
    unresolved: int = Field(ge=0, strict=True)
    high_severity_unresolved: int = Field(ge=0, strict=True)
    overdue_reviews: int = Field(ge=0, strict=True)


class GovernanceSummaryTacticalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    sessions: int = Field(ge=0, strict=True)
    open_items: int = Field(ge=0, strict=True)
    overdue_items: int = Field(ge=0, strict=True)
    disposed_items: int = Field(ge=0, strict=True)


class GovernanceSummaryResponse(BaseModel):
    """Location-scoped counts and circle metadata from the governance summary query."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    circles: list[GovernanceSummaryCircleResponse]
    tensions: GovernanceSummaryTensionsResponse
    tactical: GovernanceSummaryTacticalResponse


class GovernanceTacticalItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    requested_next_action: str = Field(min_length=1, max_length=4000)
    priority: int = Field(ge=1, le=5, strict=True)
    due_at: AwareDatetime | None
    status: Literal["open", "in_progress"]
    created_at: AwareDatetime
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ]
    session_title: str = Field(max_length=255)
    scheduled_at: AwareDatetime | None
    session_status: Literal["planned", "active", "completed"]
    owner_role_key: str | None = Field(max_length=120)

    @field_validator("requested_next_action")
    @classmethod
    def _requested_action_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("requested_next_action must not be blank")
        return value


class GovernanceTacticalItemPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceTacticalItemResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None

    def validate_request(self, *, location_id: str, limit: int, cursor: str | None):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance tactical page does not match request bounds")
        if self.next_cursor is not None:
            if (
                not self.items
                or len(self.items) != limit
                or self.next_cursor != self.items[-1].id
            ):
                raise ValueError("Governance tactical cursor does not match the page")
        if cursor is not None:
            input_cursor = UUID(cursor)
            if input_cursor in {item.id for item in self.items} or self.next_cursor == input_cursor:
                raise ValueError("Governance tactical page repeats its input cursor")
        return self


class GovernanceTacticalSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _GovernanceResponseUUID
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ]
    title: str = Field(max_length=255)
    scheduled_at: AwareDatetime | None
    status: Literal["planned", "active", "completed", "cancelled"]
    created_at: AwareDatetime
    circle_key: str = Field(max_length=120)
    circle_name: str = Field(max_length=255)
    item_count: int = Field(ge=0, strict=True)
    open_item_count: int = Field(ge=0, strict=True)
    disposed_item_count: int = Field(ge=0, strict=True)
    overdue_item_count: int = Field(ge=0, strict=True)


class GovernanceTacticalSessionPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _GovernanceResponseUUID
    items: list[GovernanceTacticalSessionResponse] = Field(max_length=100)
    next_cursor: _GovernanceResponseUUID | None

    def validate_request(self, *, location_id: str, limit: int, cursor: str | None):
        if self.location_id != UUID(location_id) or len(self.items) > limit:
            raise ValueError("Governance tactical session page does not match request bounds")
        if self.next_cursor is not None:
            if (
                not self.items
                or len(self.items) != limit
                or self.next_cursor != self.items[-1].id
            ):
                raise ValueError("Governance tactical session cursor does not match the page")
        if cursor is not None:
            input_cursor = UUID(cursor)
            if input_cursor in {item.id for item in self.items} or self.next_cursor == input_cursor:
                raise ValueError("Governance tactical session page repeats its input cursor")
        return self


class GovernanceTacticalItemCreateRequest(BaseModel):
    """Strict, location-scoped request for an open tactical item."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    session_id: _GovernanceResponseUUID
    requested_next_action: str = Field(min_length=1, max_length=4000, strict=True)
    tension_id: _GovernanceResponseUUID | None = None
    work_item_id: _GovernanceResponseUUID | None = None
    decision_id: _GovernanceResponseUUID | None = None
    owner_role_id: _GovernanceResponseUUID | None = None
    owner_party_id: _GovernanceResponseUUID | None = None
    priority: int = Field(default=3, ge=1, le=5, strict=True)
    due_at: str | None = Field(
        default=None,
        strict=True,
        json_schema_extra={"format": "date-time"},
    )

    @field_validator("due_at")
    @classmethod
    def _due_at_must_be_timezone_aware(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("due_at must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("due_at must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _validate_create_bounds(self):
        if not self.reason.strip() or not self.requested_next_action.strip():
            raise ValueError("reason and requested_next_action must not be blank")
        if any(
            "\x00" in value
            for value in (self.reason, self.requested_next_action)
            if value is not None
        ):
            raise ValueError("Tactical item text cannot contain null characters")
        return self


class _GovernanceTacticalItemCreateActionResult(BaseModel):
    """Exact six-field result from migration 445, including its private actor."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    operation: Literal["create_item"]
    session_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID
    actor_party_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class GovernanceTacticalItemCreatedResponse(BaseModel):
    """Public migration-445 creation receipt without the private actor ID."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    operation: Literal["create_item"]
    session_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class GovernanceTacticalItemCreateError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


class GovernanceTacticalItemUpdateRequest(BaseModel):
    """Strict partial content edit for an open tactical item."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    requested_next_action: str = Field(default=None, min_length=1, max_length=4000, strict=True)
    tension_id: _GovernanceResponseUUID | None = None
    work_item_id: _GovernanceResponseUUID | None = None
    decision_id: _GovernanceResponseUUID | None = None
    owner_role_id: _GovernanceResponseUUID | None = None
    owner_party_id: _GovernanceResponseUUID | None = None
    priority: int = Field(default=None, ge=1, le=5, strict=True)
    due_at: str | None = Field(
        default=None,
        strict=True,
        json_schema_extra={"format": "date-time"},
    )

    @field_validator("due_at")
    @classmethod
    def _due_at_must_be_timezone_aware(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("due_at must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("due_at must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _validate_update_fields(self):
        mutable_fields = self.model_fields_set - {"request_id", "reason"}
        if not mutable_fields:
            raise ValueError("At least one tactical-item field is required")
        if "requested_next_action" in self.model_fields_set and self.requested_next_action is None:
            raise ValueError("requested_next_action must be text")
        if "priority" in self.model_fields_set and self.priority is None:
            raise ValueError("priority must be an integer between 1 and 5")
        if self.requested_next_action is not None and not self.requested_next_action.strip():
            raise ValueError("requested_next_action must not be blank")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if any(
            "\x00" in value
            for value in (self.reason, self.requested_next_action)
            if value is not None
        ):
            raise ValueError("Tactical item text cannot contain null characters")
        return self


class GovernanceTacticalSessionUpdateRequest(BaseModel):
    """Strict partial content edit for a planned tactical session."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ] = Field(default=None)
    title: str = Field(default=None, min_length=1, max_length=255, strict=True)
    scheduled_at: str | None = Field(
        default=None,
        strict=True,
        json_schema_extra={"format": "date-time"},
    )
    facilitator_role_id: _GovernanceResponseUUID | None = None
    recorder_role_id: _GovernanceResponseUUID | None = None
    agenda_scope: str | None = Field(default=None, max_length=10_000, strict=True)

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_must_be_timezone_aware(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_at must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("scheduled_at must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _validate_update_fields(self):
        mutable_fields = self.model_fields_set - {"request_id", "reason"}
        if not mutable_fields:
            raise ValueError("At least one tactical-session field is required")
        if "session_type" in self.model_fields_set and self.session_type is None:
            raise ValueError("session_type is required")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title is required")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        if self.title is not None and not self.title.strip():
            raise ValueError("title must not be blank")
        if any(
            "\x00" in value
            for value in (self.reason, self.title, self.agenda_scope)
            if value is not None
        ):
            raise ValueError("Tactical session text cannot contain null characters")
        return self


class _GovernanceTacticalContentUpdateActionResult(BaseModel):
    """Exact migration-445 result for item/session edits, including its private actor."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    operation: Literal["update_item", "update_session"]
    session_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID | None
    actor_party_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class GovernanceTacticalItemUpdatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    operation: Literal["update_item"]
    session_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class GovernanceTacticalSessionUpdatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    operation: Literal["update_session"]
    session_id: _GovernanceResponseUUID
    item_id: None
    created_at: AwareDatetime


class GovernanceTacticalContentMutationError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


class GovernanceTacticalSimpleActionRequest(BaseModel):
    """Strict start/cancel request envelope."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)

    @field_validator("reason")
    @classmethod
    def _reason_must_be_nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("reason must contain 1 to 2000 valid characters")
        return value


class GovernanceTacticalDisposeRequest(BaseModel):
    """Strict disposal request with an enumerated disposition and summary."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    disposition_type: Literal[
        "next_action",
        "delegate",
        "create_work_item",
        "create_proposal",
        "escalate",
        "defer",
        "no_action",
    ]
    disposition_summary: str = Field(min_length=1, max_length=4000, strict=True)

    @field_validator("reason", "disposition_summary")
    @classmethod
    def _action_text_must_be_nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("Tactical action text must be nonblank and valid")
        return value


class _GovernanceTacticalActionResult(BaseModel):
    """Exact seven-field migration-441 result, including its private actor."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID
    action: Literal["start", "dispose", "cancel"]
    prior_status: Literal["open", "in_progress"]
    resulting_status: Literal["in_progress", "disposed", "cancelled"]
    actor_party_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class _GovernanceTacticalActionResponseBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    item_id: _GovernanceResponseUUID
    created_at: AwareDatetime


class GovernanceTacticalItemStartedResponse(_GovernanceTacticalActionResponseBase):
    """Public start receipt omitting the acting-party identity."""

    action: Literal["start"]
    prior_status: Literal["open"]
    resulting_status: Literal["in_progress"]


class GovernanceTacticalItemDisposedResponse(_GovernanceTacticalActionResponseBase):
    """Public disposal receipt omitting the acting-party identity."""

    action: Literal["dispose"]
    prior_status: Literal["in_progress"]
    resulting_status: Literal["disposed"]


class GovernanceTacticalItemCancelledResponse(_GovernanceTacticalActionResponseBase):
    """Public cancellation receipt omitting the acting-party identity."""

    action: Literal["cancel"]
    prior_status: Literal["open", "in_progress"]
    resulting_status: Literal["cancelled"]


class GovernanceTacticalActionError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


class GovernanceTacticalSessionCreateRequest(BaseModel):
    """Strict location-scoped request for creating a planned session."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)
    circle_id: _GovernanceResponseUUID
    session_type: Literal[
        "weekly_review",
        "stakeholder_health",
        "relationship_review",
        "risk_triage",
        "governance_followup",
    ]
    title: str = Field(min_length=1, max_length=255, strict=True)
    scheduled_at: str | None = Field(
        default=None,
        strict=True,
        json_schema_extra={"format": "date-time"},
    )
    facilitator_role_id: _GovernanceResponseUUID | None = None
    recorder_role_id: _GovernanceResponseUUID | None = None
    agenda_scope: str | None = Field(default=None, max_length=10_000, strict=True)

    @field_validator("scheduled_at")
    @classmethod
    def _scheduled_at_must_be_timezone_aware(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_at must be a valid ISO timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("scheduled_at must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _validate_create_bounds(self):
        if not self.reason.strip() or len(self.reason.strip()) > 2000:
            raise ValueError("reason must contain 1 to 2000 characters")
        if not self.title.strip() or len(self.title.strip()) > 255:
            raise ValueError("title must contain 1 to 255 characters")
        if any(
            "\x00" in value
            for value in (self.reason, self.title, self.agenda_scope)
            if value is not None
        ):
            raise ValueError("Tactical session text cannot contain null characters")
        return self


class _GovernanceTacticalSessionCreateActionResult(BaseModel):
    """Exact five-field result from migration 444, including its private actor."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    session_id: _GovernanceResponseUUID
    actor_party_id: _GovernanceResponseUUID
    status: Literal["planned"]
    created_at: AwareDatetime


class GovernanceTacticalSessionCreatedResponse(BaseModel):
    """Public creation receipt omitting the migration's private actor identity."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    session_id: _GovernanceResponseUUID
    status: Literal["planned"]
    created_at: AwareDatetime


class GovernanceTacticalSessionCreateError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


class GovernanceDefinitionLifecycleRequest(BaseModel):
    """Strict request envelope for an audited circle or role transition."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _GovernanceResponseUUID
    reason: str = Field(min_length=1, max_length=2000, strict=True)

    @field_validator("reason")
    @classmethod
    def _reason_must_be_nonblank(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("reason must contain 1 to 2000 valid characters")
        return value


class _GovernanceDefinitionLifecycleActionResult(BaseModel):
    """Exact eight-field migration-442 result, including the private actor ID."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    entity_type: Literal["circle", "role"]
    entity_id: _GovernanceResponseUUID
    action: Literal["submit", "approve", "reject", "activate", "suspend", "retire"]
    prior_status: Literal[
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    ]
    resulting_status: Literal[
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    ]
    actor_party_id: _GovernanceResponseUUID
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("governance lifecycle timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("governance lifecycle timestamp must include a timezone")
        return value


class _GovernanceDefinitionLifecycleResponseBase(BaseModel):
    """Public seven-field lifecycle receipt without the acting-party identity."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    event_id: _GovernanceResponseUUID
    entity_type: Literal["circle", "role"]
    entity_id: _GovernanceResponseUUID
    action: Literal["submit", "approve", "reject", "activate", "suspend", "retire"]
    prior_status: Literal[
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    ]
    resulting_status: Literal[
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    ]
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def _parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("governance lifecycle timestamp is invalid") from exc
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("governance lifecycle timestamp must include a timezone")
        return value


class GovernanceCircleSubmittedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["circle"]
    action: Literal["submit"]
    prior_status: Literal["draft"]
    resulting_status: Literal["submitted"]


class GovernanceCircleRejectedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["circle"]
    action: Literal["reject"]
    prior_status: Literal["draft", "submitted"]
    resulting_status: Literal["rejected"]


class GovernanceCircleActivatedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["circle"]
    action: Literal["activate"]
    prior_status: Literal["submitted"]
    resulting_status: Literal["active"]


class GovernanceCircleSuspendedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["circle"]
    action: Literal["suspend"]
    prior_status: Literal["active"]
    resulting_status: Literal["suspended"]


class GovernanceCircleRetiredResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["circle"]
    action: Literal["retire"]
    prior_status: Literal["active", "suspended"]
    resulting_status: Literal["retired"]


class GovernanceRoleSubmittedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["submit"]
    prior_status: Literal["draft"]
    resulting_status: Literal["submitted"]


class GovernanceRoleApprovedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["approve"]
    prior_status: Literal["submitted"]
    resulting_status: Literal["approved"]


class GovernanceRoleRejectedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["reject"]
    prior_status: Literal["draft", "submitted"]
    resulting_status: Literal["rejected"]


class GovernanceRoleActivatedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["activate"]
    prior_status: Literal["approved"]
    resulting_status: Literal["active"]


class GovernanceRoleSuspendedResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["suspend"]
    prior_status: Literal["active"]
    resulting_status: Literal["suspended"]


class GovernanceRoleRetiredResponse(_GovernanceDefinitionLifecycleResponseBase):
    entity_type: Literal["role"]
    action: Literal["retire"]
    prior_status: Literal["active", "suspended"]
    resulting_status: Literal["retired"]


class GovernanceDefinitionLifecycleError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: str


def register_governance_role_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.governance_assignment_proposal_reads import (
        GovernanceAssignmentProposalReadInvalid,
        list_own_governance_assignment_proposals,
    )
    from services.gateway.governance_assignment_proposals import (
        GovernanceAssignmentConflict,
        GovernanceAssignmentInvalid,
        propose_governance_role_assignment,
    )
    from services.gateway.governance_assignment_review import (
        GovernanceAssignmentReviewConflict,
        GovernanceAssignmentReviewInvalid,
        decide_governance_assignment,
        list_governance_assignment_reviews,
    )
    from services.gateway.governance_definition_actions import (
        GovernanceDefinitionActionConflict,
        GovernanceDefinitionActionInvalid,
        transition_governance_definition,
    )
    from services.gateway.governance_definition_mutations import (
        GovernanceDefinitionMutationConflict,
        GovernanceDefinitionMutationInvalid,
        mutate_governance_definition,
    )
    from services.gateway.governance_operations import (
        GovernanceOperationsInvalid,
        get_location_governance_circle_detail,
        get_location_governance_role_detail,
        list_location_governance_roles,
        list_location_governance_tactical_items,
        list_location_governance_tactical_sessions,
    )
    from services.gateway.governance_roles import get_location_governance_summary
    from services.gateway.governance_tactical_actions import (
        GovernanceTacticalActionConflict,
        GovernanceTacticalActionInvalid,
        transition_governance_tactical_item,
    )
    from services.gateway.governance_tactical_mutations import (
        GovernanceTacticalMutationConflict,
        GovernanceTacticalMutationInvalid,
        mutate_governance_tactical_content,
    )
    from services.gateway.governance_tactical_session_mutations import (
        GovernanceTacticalSessionInvalid,
        create_governance_tactical_session,
    )
    from services.gateway.governance_tension_actions import (
        GovernanceTensionConflict,
        GovernanceTensionInvalid,
        report_governance_tension,
        submit_governance_tension,
    )
    from services.gateway.governance_tension_review import (
        GovernanceTensionReviewDetailResponse,
        GovernanceTensionReviewInvalid,
        GovernanceTensionReviewNotFound,
        GovernanceTensionReviewQueueResponse,
        get_location_governance_tension,
        list_location_governance_tensions,
    )

    tension_action_error_responses = {
        status: {
            "model": GovernanceTensionActionError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The governance-tension request is invalid.",
            403: "The operator lacks an active exact-location action grant.",
            404: "Operator OIDC is disabled or the tension is unavailable.",
            409: "The requested tension action conflicts with current state.",
            500: "The governance-tension result failed its response contract.",
            503: "The governance-tension action is unavailable.",
        }.items()
    }

    def error_response(exc, *, headers):
        if isinstance(exc, TenantContextDenied):
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        if isinstance(exc, GovernanceTensionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceTensionReviewNotFound):
            return JSONResponse(status_code=404, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceDefinitionActionInvalid):
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, GovernanceDefinitionActionConflict):
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        if isinstance(exc, psycopg2.Error):
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance tension request is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance tension request conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tension action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        raise exc

    @router.get(
        "/operator/api/governance/{location_id}/summary",
        response_model=GovernanceSummaryResponse,
    )
    async def location_governance_summary(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            summary = await run_in_threadpool(
                get_location_governance_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        try:
            response = GovernanceSummaryResponse.model_validate(summary)
            if response.location_id != UUID(location_id):
                raise ValueError("Governance summary location does not match request")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance summary unavailable"},
                headers=headers,
            )

        return JSONResponse(jsonable_encoder(response.model_dump(mode="python")), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/roles",
        response_model=GovernanceRoleListResponse,
    )
    async def location_governance_roles(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_roles,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role registry unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role registry unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceRoleListResponse.model_validate(result)
            if response.location_id != UUID(location_id) or len(response.items) > limit:
                raise ValueError("Governance role page does not match request bounds")
            if response.next_cursor is not None and (
                not response.items or response.next_cursor != response.items[-1].id
            ):
                raise ValueError("Governance role cursor does not match the page")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role page response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance role registry unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/roles/{role_id}",
        response_model=GovernanceRoleDetailResponse,
    )
    async def location_governance_role_detail(
        request: Request,
        location_id: str,
        role_id: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_role_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Governance role not found"},
                headers=headers,
            )
        try:
            response = GovernanceRoleDetailResponse.model_validate(result)
            if response.location_id != UUID(location_id) or response.role.id != UUID(role_id):
                raise ValueError("Governance role detail does not match request scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance role detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance role detail unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/circles/{circle_id}",
        response_model=GovernanceCircleDetailResponse,
    )
    async def location_governance_circle_detail(
        request: Request,
        location_id: str,
        circle_id: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_circle_detail,
                request.state.operator_session.operator.operator_id,
                location_id,
                circle_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance circle detail unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance circle detail unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Governance circle not found"},
                headers=headers,
            )
        try:
            response = GovernanceCircleDetailResponse.model_validate(result)
            if (
                response.location_id != UUID(location_id)
                or response.circle.id != UUID(circle_id)
            ):
                raise ValueError("Governance circle detail does not match request scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance circle detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance circle detail unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/assignment-proposals",
        response_model=GovernanceAssignmentProposalPageResponse,
    )
    async def own_governance_assignment_proposals(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor_created_at: str | None = None,
        cursor_assignment_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_own_governance_assignment_proposals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentProposalReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role read grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role proposal cursor is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role proposal readback unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role proposal readback unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = GovernanceAssignmentProposalPageResponse.model_validate(result)
            page.validate_request(
                location_id=location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role proposal response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance role proposal readback unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(page.model_dump(mode="json")), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/assignment-review-queue",
        response_model=GovernanceAssignmentReviewPageResponse,
        responses={
            status: {"model": GovernanceAssignmentReviewError, "description": description}
            for status, description in {
                400: "The review cursor is invalid.",
                403: "The operator lacks a current location review grant and person binding.",
                404: "Operator OIDC is disabled.",
                500: "The review projection failed its response contract.",
                503: "The review service is unavailable.",
            }.items()
        },
    )
    async def governance_assignment_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor_created_at: str | None = None,
        cursor_assignment_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_governance_assignment_reviews,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role review grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance assignment review cursor is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance assignment review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = GovernanceAssignmentReviewPageResponse.model_validate(result)
            page.validate_request(
                location_id=location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_assignment_id=cursor_assignment_id,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment review response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance assignment review queue unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(page.model_dump(mode="json")), headers=headers)

    assignment_decision_error_responses = {
        status: {
            "model": GovernanceAssignmentReviewError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The assignment decision request is invalid.",
            403: "The operator lacks the active exact-location decision grant or independent person binding.",
            404: "Operator OIDC is disabled or the assignment is unavailable.",
            409: "The assignment has already changed or the decision conflicts with current state.",
            500: "The assignment decision result failed its response contract.",
            503: "The assignment decision is unavailable.",
        }.items()
    }

    async def decide_assignment_route(
        request: Request,
        location_id: str,
        role_id: str,
        assignment_id: str,
        decision: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Assignment decision must be valid JSON"},
                headers=headers,
            )
        try:
            decision_request = GovernanceAssignmentDecisionRequest.model_validate(payload)
            operator_id = str(UUID(request.state.operator_session.operator.operator_id))
            requested_location_id = str(UUID(location_id))
            requested_role_id = str(UUID(role_id))
            requested_assignment_id = str(UUID(assignment_id))
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance assignment decision request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_governance_assignment,
                operator_id,
                requested_location_id,
                requested_role_id,
                requested_assignment_id,
                decision,
                decision_request.model_dump(mode="json"),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceAssignmentReviewConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active governance role decision grant and independent person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance assignment decision is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance assignment has already changed or been decided"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance assignment decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            action_result = _GovernanceAssignmentDecisionResult.model_validate(result)
            if action_result.assignment_id != UUID(assignment_id) or action_result.decision != decision:
                raise ValueError("Assignment decision result does not match the request path")
            response_model = (
                GovernanceAssignmentApprovedResponse
                if decision == "approve"
                else GovernanceAssignmentRejectedResponse
            )
            response = response_model.model_validate(
                action_result.model_dump(mode="python", exclude={"reviewer_party_id"})
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance assignment decision response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance assignment decision unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")), headers=headers
        )

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments/{assignment_id}/approve",
        response_model=GovernanceAssignmentApprovedResponse,
        responses={
            200: {
                "model": GovernanceAssignmentApprovedResponse,
                "description": "The assignment was approved or an idempotent retry returned its original approval receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **assignment_decision_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceAssignmentDecisionRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def approve_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str, assignment_id: str
    ):
        return await decide_assignment_route(
            request, location_id, role_id, assignment_id, "approve"
        )

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments/{assignment_id}/reject",
        response_model=GovernanceAssignmentRejectedResponse,
        responses={
            200: {
                "model": GovernanceAssignmentRejectedResponse,
                "description": "The assignment was rejected or an idempotent retry returned its original rejection receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **assignment_decision_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceAssignmentDecisionRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def reject_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str, assignment_id: str
    ):
        return await decide_assignment_route(
            request, location_id, role_id, assignment_id, "reject"
        )

    @router.post(
        "/operator/api/governance/{location_id}/roles/{role_id}/assignments",
        status_code=201,
    )
    async def propose_governance_role_assignment_route(
        request: Request, location_id: str, role_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Role nomination must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                propose_governance_role_assignment,
                request.state.operator_session.operator.operator_id,
                location_id,
                role_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceAssignmentInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceAssignmentConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance role creation grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance role nomination is invalid"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance role nomination conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_roles").warning(
                "Governance role nomination unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance role nomination unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    async def governance_definition_action_route(
        request: Request,
        location_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance lifecycle content must be valid JSON"},
                headers=headers,
            )
        try:
            action_request = GovernanceDefinitionLifecycleRequest.model_validate(payload)
            requested_location_id = str(UUID(location_id))
            requested_entity_id = str(UUID(entity_id))
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance definition action request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_governance_definition,
                request.state.operator_session.operator.operator_id,
                requested_location_id,
                entity_type,
                requested_entity_id,
                action,
                action_request.model_dump(mode="json"),
            )
        except (
            TenantContextDenied,
            GovernanceDefinitionActionInvalid,
            GovernanceDefinitionActionConflict,
            psycopg2.Error,
        ) as exc:
            if isinstance(exc, (GovernanceDefinitionActionInvalid, GovernanceDefinitionActionConflict)):
                status_code = 400 if isinstance(exc, GovernanceDefinitionActionInvalid) else 409
                return JSONResponse(status_code=status_code, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, TenantContextDenied):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Tenant-qualified operator access is required"},
                    headers=headers,
                )
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance action grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance definition action is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance definition action conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_definitions").warning(
                "Governance definition action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance definition action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        try:
            action_result = _GovernanceDefinitionLifecycleActionResult.model_validate(result)
            if (
                action_result.entity_type != entity_type
                or action_result.entity_id != UUID(entity_id)
                or action_result.action != action
            ):
                raise ValueError("Governance definition result does not match its route")
            response_model = definition_action_response_models[(entity_type, action)]
            response = response_model.model_validate(
                action_result.model_dump(mode="python", exclude={"actor_party_id"})
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_definitions").warning(
                "Governance definition action response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance definition action unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")), headers=headers
        )

    def circle_action_endpoint(action):
        async def endpoint(request: Request, location_id: str, circle_id: str):
            return await governance_definition_action_route(
                request, location_id, "circle", circle_id, action
            )

        return endpoint

    def role_action_endpoint(action):
        async def endpoint(request: Request, location_id: str, role_id: str):
            return await governance_definition_action_route(
                request, location_id, "role", role_id, action
            )

        return endpoint

    async def governance_definition_mutation_route(
        request: Request,
        location_id: str,
        entity_type: str,
        action: str,
        entity_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance definition content must be valid JSON"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                mutate_governance_definition,
                request.state.operator_session.operator.operator_id,
                location_id,
                entity_type,
                action,
                entity_id,
                payload,
            )
        except (
            TenantContextDenied,
            GovernanceDefinitionMutationInvalid,
            GovernanceDefinitionMutationConflict,
            psycopg2.Error,
        ) as exc:
            if isinstance(exc, GovernanceDefinitionMutationInvalid):
                return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, GovernanceDefinitionMutationConflict):
                return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
            if isinstance(exc, TenantContextDenied):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Tenant-qualified operator access is required"},
                    headers=headers,
                )
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current governance mutation grant and person binding are required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Governance definition content is invalid"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Governance definition was not found in this location"},
                    headers=headers,
                )
            if code in {"23505", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Governance definition is unavailable or changed state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_definitions").warning(
                "Governance definition mutation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance definition mutation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=201 if action == "create" else 200,
            headers=headers,
        )

    def create_definition_endpoint(entity_type):
        async def endpoint(request: Request, location_id: str):
            return await governance_definition_mutation_route(
                request, location_id, entity_type, "create"
            )

        return endpoint

    def update_definition_endpoint(entity_type):
        async def endpoint(request: Request, location_id: str, definition_id: str):
            return await governance_definition_mutation_route(
                request, location_id, entity_type, "update", definition_id
            )

        return endpoint

    for entity_type, route_name in (("circle", "circle"), ("role", "role")):
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/{route_name}s",
            create_definition_endpoint(entity_type),
            methods=["POST"],
            name=f"create_governance_{route_name}",
        )
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/{route_name}s/{{definition_id}}",
            update_definition_endpoint(entity_type),
            methods=["PATCH"],
            name=f"update_governance_{route_name}",
        )

    definition_action_response_models = {
        ("circle", "submit"): GovernanceCircleSubmittedResponse,
        ("circle", "reject"): GovernanceCircleRejectedResponse,
        ("circle", "activate"): GovernanceCircleActivatedResponse,
        ("circle", "suspend"): GovernanceCircleSuspendedResponse,
        ("circle", "retire"): GovernanceCircleRetiredResponse,
        ("role", "submit"): GovernanceRoleSubmittedResponse,
        ("role", "approve"): GovernanceRoleApprovedResponse,
        ("role", "reject"): GovernanceRoleRejectedResponse,
        ("role", "activate"): GovernanceRoleActivatedResponse,
        ("role", "suspend"): GovernanceRoleSuspendedResponse,
        ("role", "retire"): GovernanceRoleRetiredResponse,
    }
    definition_action_error_responses = {
        status: {
            "model": GovernanceDefinitionLifecycleError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The governance definition action request is invalid.",
            403: "The operator lacks an active exact-location action grant.",
            404: "Operator OIDC is disabled or the definition is unavailable.",
            409: "The definition lifecycle conflicts with current state.",
            500: "The lifecycle result failed its response contract.",
            503: "The governance definition action is unavailable.",
        }.items()
    }

    for circle_action in ("submit", "reject", "activate", "suspend", "retire"):
        response_model = definition_action_response_models[("circle", circle_action)]
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/circles/{{circle_id}}/{circle_action}",
            circle_action_endpoint(circle_action),
            methods=["POST"],
            name=f"transition_governance_circle_{circle_action}",
            response_model=response_model,
            responses={
                200: {
                    "model": response_model,
                    "description": (
                        "The circle transition was recorded or an idempotent retry "
                        "returned its original receipt. The actor ID is omitted."
                    ),
                    "headers": {
                        "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                        "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                    },
                },
                **definition_action_error_responses,
            },
            openapi_extra={
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": GovernanceDefinitionLifecycleRequest.model_json_schema()
                        }
                    },
                }
            },
        )

    for role_action in ("submit", "approve", "reject", "activate", "suspend", "retire"):
        response_model = definition_action_response_models[("role", role_action)]
        router.add_api_route(
            f"/operator/api/governance/{{location_id}}/roles/{{role_id}}/{role_action}",
            role_action_endpoint(role_action),
            methods=["POST"],
            name=f"transition_governance_role_{role_action}",
            response_model=response_model,
            responses={
                200: {
                    "model": response_model,
                    "description": (
                        "The role transition was recorded or an idempotent retry "
                        "returned its original receipt. The actor ID is omitted."
                    ),
                    "headers": {
                        "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                        "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                    },
                },
                **definition_action_error_responses,
            },
            openapi_extra={
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": GovernanceDefinitionLifecycleRequest.model_json_schema()
                        }
                    },
                }
            },
        )

    @router.get(
        "/operator/api/governance/{location_id}/tactical-items",
        response_model=GovernanceTacticalItemPageResponse,
    )
    async def location_governance_tactical_items(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tactical_items,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceTacticalItemPageResponse.model_validate(result)
            response.validate_request(location_id=location_id, limit=limit, cursor=cursor)
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical page response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical queue unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/governance/{location_id}/tactical-sessions",
        response_model=GovernanceTacticalSessionPageResponse,
    )
    async def location_governance_tactical_sessions(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tactical_sessions,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor=cursor,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceOperationsInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical sessions unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical sessions unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            response = GovernanceTacticalSessionPageResponse.model_validate(result)
            response.validate_request(location_id=location_id, limit=limit, cursor=cursor)
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_operations").warning(
                "Governance tactical session page response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical sessions unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(response.model_dump(mode="python")), headers=headers)

    tactical_create_error_responses = {
        status: {
            "model": GovernanceTacticalSessionCreateError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The tactical-session request is invalid.",
            403: "The operator lacks an active exact-location create grant.",
            404: "Operator OIDC is disabled or the selected circle/role is unavailable.",
            409: "Tactical-session creation conflicts with existing state.",
            500: "The tactical-session result failed its response contract.",
            503: "Tactical-session creation is unavailable.",
        }.items()
    }

    @router.post(
        "/operator/api/governance/{location_id}/tactical-sessions",
        status_code=201,
        response_model=GovernanceTacticalSessionCreatedResponse,
        responses={
            201: {
                "model": GovernanceTacticalSessionCreatedResponse,
                "description": (
                    "A planned tactical session was created or an idempotent retry "
                    "returned the original creation receipt."
                ),
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_create_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTacticalSessionCreateRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def create_governance_tactical_session_route(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical session content must be valid JSON"},
                headers=headers,
            )
        try:
            create_request = GovernanceTacticalSessionCreateRequest.model_validate(payload)
            requested_location_id = UUID(location_id)
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical session request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_governance_tactical_session,
                request.state.operator_session.operator.operator_id,
                str(requested_location_id),
                create_request.model_dump(mode="json", exclude_unset=True),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalSessionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical session creation grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "The active circle or role was not found in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical session request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical session creation conflicts with current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical session creation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical session creation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            action_result = _GovernanceTacticalSessionCreateActionResult.model_validate(result)
            response = GovernanceTacticalSessionCreatedResponse(
                event_id=action_result.event_id,
                session_id=action_result.session_id,
                status=action_result.status,
                created_at=action_result.created_at,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical session create response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical session creation unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")),
            status_code=201,
            headers=headers,
        )

    async def mutate_tactical_content_route(
        request: Request,
        location_id: str,
        operation: str,
        target_id: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical content must be valid JSON"},
                headers=headers,
            )
        route_request = None
        if operation in {"create_item", "update_item", "update_session"}:
            request_model = {
                "create_item": GovernanceTacticalItemCreateRequest,
                "update_item": GovernanceTacticalItemUpdateRequest,
                "update_session": GovernanceTacticalSessionUpdateRequest,
            }[operation]
            try:
                route_request = request_model.model_validate(payload)
                location_id = str(UUID(location_id))
                if operation != "create_item":
                    target_id = str(UUID(target_id))
            except (ValidationError, TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": (
                            "Tactical item request is invalid"
                            if operation in {"create_item", "update_item"}
                            else "Tactical session request is invalid"
                        )
                    },
                    headers=headers,
                )
            payload = route_request.model_dump(mode="json", exclude_unset=True)
        try:
            result = await run_in_threadpool(
                mutate_governance_tactical_content,
                request.state.operator_session.operator.operator_id,
                location_id,
                operation,
                target_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalMutationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceTacticalMutationConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical content grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "The linked session, role, person, or record is unavailable in this location"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical content request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical content conflicts with its current state"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical content mutation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical content mutation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        status_code = 201 if operation == "create_item" else 200
        if operation == "create_item":
            try:
                action_result = _GovernanceTacticalItemCreateActionResult.model_validate(result)
                if action_result.session_id != route_request.session_id:
                    raise ValueError("Tactical item result session does not match request")
                response = GovernanceTacticalItemCreatedResponse(
                    event_id=action_result.event_id,
                    operation=action_result.operation,
                    session_id=action_result.session_id,
                    item_id=action_result.item_id,
                    created_at=action_result.created_at,
                )
            except (ValidationError, TypeError, ValueError) as exc:
                from services.common.logging import get_logger

                get_logger("gateway.governance_tactical").warning(
                    "Governance tactical item create response rejected (%s)",
                    type(exc).__name__,
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": "Governance tactical item creation unavailable"},
                    headers=headers,
                )
            return JSONResponse(
                jsonable_encoder(response.model_dump(mode="python")),
                status_code=status_code,
                headers=headers,
            )
        if operation in {"update_item", "update_session"}:
            try:
                action_result = _GovernanceTacticalContentUpdateActionResult.model_validate(result)
                if operation == "update_item":
                    if action_result.operation != "update_item" or action_result.item_id != UUID(target_id):
                        raise ValueError("Tactical item result does not match the request path")
                    response = GovernanceTacticalItemUpdatedResponse(
                        event_id=action_result.event_id,
                        operation=action_result.operation,
                        session_id=action_result.session_id,
                        item_id=action_result.item_id,
                        created_at=action_result.created_at,
                    )
                else:
                    if (
                        action_result.operation != "update_session"
                        or action_result.session_id != UUID(target_id)
                        or action_result.item_id is not None
                    ):
                        raise ValueError("Tactical session result does not match the request path")
                    response = GovernanceTacticalSessionUpdatedResponse(
                        event_id=action_result.event_id,
                        operation=action_result.operation,
                        session_id=action_result.session_id,
                        item_id=action_result.item_id,
                        created_at=action_result.created_at,
                    )
            except (ValidationError, TypeError, ValueError) as exc:
                from services.common.logging import get_logger

                get_logger("gateway.governance_tactical").warning(
                    "Governance tactical content update response rejected (%s)",
                    type(exc).__name__,
                )
                return JSONResponse(
                    status_code=500,
                    content={"error": "Governance tactical content update unavailable"},
                    headers=headers,
                )
            return JSONResponse(
                jsonable_encoder(response.model_dump(mode="python")),
                status_code=status_code,
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), status_code=status_code, headers=headers)

    tactical_item_create_error_responses = {
        status: {
            "model": GovernanceTacticalItemCreateError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The tactical-item request is invalid.",
            403: "The operator lacks an active exact-location create grant.",
            404: "Operator OIDC is disabled or the referenced session/item is unavailable.",
            409: "Tactical-item creation conflicts with existing state.",
            500: "The tactical-item result failed its response contract.",
            503: "Tactical-item creation is unavailable.",
        }.items()
    }
    tactical_content_update_error_responses = {
        status: {
            "model": GovernanceTacticalContentMutationError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The tactical content update request is invalid.",
            403: "The operator lacks an active exact-location update grant.",
            404: "Operator OIDC is disabled or the requested tactical record is unavailable.",
            409: "The tactical record cannot be updated in its current state.",
            500: "The tactical content result failed its response contract.",
            503: "The tactical content update is unavailable.",
        }.items()
    }

    @router.post(
        "/operator/api/governance/{location_id}/tactical-items",
        status_code=201,
        response_model=GovernanceTacticalItemCreatedResponse,
        responses={
            201: {
                "model": GovernanceTacticalItemCreatedResponse,
                "description": (
                    "An open tactical item was created or an idempotent retry returned "
                    "the original creation receipt."
                ),
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_item_create_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTacticalItemCreateRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def create_governance_tactical_item(request: Request, location_id: str):
        return await mutate_tactical_content_route(request, location_id, "create_item")

    @router.patch(
        "/operator/api/governance/{location_id}/tactical-items/{item_id}",
        response_model=GovernanceTacticalItemUpdatedResponse,
        responses={
            200: {
                "model": GovernanceTacticalItemUpdatedResponse,
                "description": "The item content was updated or an idempotent retry returned its receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_content_update_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": _request_schema(
                            GovernanceTacticalItemUpdateRequest,
                            optional_non_null_fields=("requested_next_action", "priority"),
                        )
                    }
                },
            }
        },
    )
    async def update_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await mutate_tactical_content_route(request, location_id, "update_item", item_id)

    @router.patch(
        "/operator/api/governance/{location_id}/tactical-sessions/{session_id}",
        response_model=GovernanceTacticalSessionUpdatedResponse,
        responses={
            200: {
                "model": GovernanceTacticalSessionUpdatedResponse,
                "description": "The session content was updated or an idempotent retry returned its receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_content_update_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": _request_schema(
                            GovernanceTacticalSessionUpdateRequest,
                            optional_non_null_fields=("session_type", "title"),
                        )
                    }
                },
            }
        },
    )
    async def update_governance_tactical_session(request: Request, location_id: str, session_id: str):
        return await mutate_tactical_content_route(request, location_id, "update_session", session_id)

    async def transition_tactical_route(request: Request, location_id: str, item_id: str, action: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical action must be valid JSON"},
                headers=headers,
            )
        try:
            request_model = (
                GovernanceTacticalDisposeRequest
                if action == "dispose"
                else GovernanceTacticalSimpleActionRequest
            )
            action_request = request_model.model_validate(payload)
            location_id = str(UUID(location_id))
            item_id = str(UUID(item_id))
            payload = action_request.model_dump(mode="json", exclude_unset=True)
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Tactical action request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_governance_tactical_item,
                request.state.operator_session.operator.operator_id,
                location_id,
                item_id,
                action,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers=headers,
            )
        except GovernanceTacticalActionInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except GovernanceTacticalActionConflict as exc:
            return JSONResponse(status_code=409, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "An active tactical action grant and person binding are required"},
                    headers=headers,
                )
            if code == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Tactical item not found"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Tactical action request is invalid"},
                    headers=headers,
                )
            if code in {"23505", "23514", "40001", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Tactical item state has changed or this action conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical action unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Governance tactical action unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            action_result = _GovernanceTacticalActionResult.model_validate(result)
            if action_result.action != action or action_result.item_id != UUID(item_id):
                raise ValueError("Tactical action result does not match the request path")
            response_model = {
                "start": GovernanceTacticalItemStartedResponse,
                "dispose": GovernanceTacticalItemDisposedResponse,
                "cancel": GovernanceTacticalItemCancelledResponse,
            }[action]
            response = response_model(
                event_id=action_result.event_id,
                item_id=action_result.item_id,
                action=action_result.action,
                prior_status=action_result.prior_status,
                resulting_status=action_result.resulting_status,
                created_at=action_result.created_at,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tactical").warning(
                "Governance tactical action response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tactical action unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")),
            headers=headers,
        )

    tactical_action_error_responses = {
        status: {
            "model": GovernanceTacticalActionError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The tactical-action request is invalid.",
            403: "The operator lacks the action's active exact-location grant.",
            404: "Operator OIDC is disabled or the tactical item is unavailable.",
            409: "The tactical-item state conflicts with the requested transition.",
            500: "The tactical-action result failed its response contract.",
            503: "The tactical action is unavailable.",
        }.items()
    }

    @router.post(
        "/operator/api/governance/{location_id}/tactical-items/{item_id}/start",
        response_model=GovernanceTacticalItemStartedResponse,
        responses={
            200: {
                "model": GovernanceTacticalItemStartedResponse,
                "description": "The item was started or an idempotent retry returned its original transition receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_action_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTacticalSimpleActionRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def start_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "start")

    @router.post(
        "/operator/api/governance/{location_id}/tactical-items/{item_id}/dispose",
        response_model=GovernanceTacticalItemDisposedResponse,
        responses={
            200: {
                "model": GovernanceTacticalItemDisposedResponse,
                "description": "The item was disposed or an idempotent retry returned its original transition receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_action_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTacticalDisposeRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def dispose_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "dispose")

    @router.post(
        "/operator/api/governance/{location_id}/tactical-items/{item_id}/cancel",
        response_model=GovernanceTacticalItemCancelledResponse,
        responses={
            200: {
                "model": GovernanceTacticalItemCancelledResponse,
                "description": "The item was cancelled or an idempotent retry returned its original transition receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tactical_action_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTacticalSimpleActionRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def cancel_governance_tactical_item(request: Request, location_id: str, item_id: str):
        return await transition_tactical_route(request, location_id, item_id, "cancel")

    @router.get(
        "/operator/api/governance/{location_id}/tensions",
        response_model=GovernanceTensionReviewQueueResponse,
    )
    async def location_governance_tensions(
        request: Request,
        location_id: str,
        status: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_governance_tensions,
                request.state.operator_session.operator.operator_id,
                location_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        try:
            page = GovernanceTensionReviewQueueResponse.model_validate(result)
            from uuid import UUID

            if (
                page.location_id != UUID(location_id)
                or len(page.items) > limit
                or (page.next_cursor is not None and len(page.items) != limit)
            ):
                raise ValueError("governance tension page does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension queue response rejected (%s)",
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/governance/{location_id}/tensions/{tension_id}",
        response_model=GovernanceTensionReviewDetailResponse,
    )
    async def location_governance_tension_detail(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (
            TenantContextDenied,
            GovernanceTensionReviewInvalid,
            GovernanceTensionReviewNotFound,
            psycopg2.Error,
        ) as exc:
            return error_response(exc, headers=headers)
        try:
            from uuid import UUID

            detail = GovernanceTensionReviewDetailResponse.model_validate(result)
            if (
                detail.location_id != UUID(location_id)
                or detail.tension.id != UUID(tension_id)
            ):
                raise ValueError("governance tension detail does not match request scope")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(detail.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/governance/{location_id}/tensions",
        status_code=201,
        response_model=GovernanceTensionMutationResponse,
        responses={
            201: {
                "model": GovernanceTensionMutationResponse,
                "description": (
                    "A tension draft was created or an idempotent retry returned its "
                    "original creation receipt. The private operator/request key is omitted."
                ),
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tension_action_error_responses,
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": GovernanceTensionCreateRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def create_governance_tension(request: Request, location_id: str):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance tension content must be valid JSON"},
                headers=headers,
            )
        try:
            create_request = GovernanceTensionCreateRequest.model_validate(payload)
            requested_location_id = UUID(location_id)
            operator_id = str(UUID(request.state.operator_session.operator.operator_id))
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Governance tension request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                report_governance_tension,
                operator_id,
                str(requested_location_id),
                create_request.model_dump(mode="json"),
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        try:
            action_result = _GovernanceTensionMutationResult.model_validate(result)
            if action_result.tension_key != (
                f"gateway:{operator_id}:{create_request.request_id}"
            ):
                raise ValueError("Governance tension result does not match the create request")
            if (
                action_result.title != create_request.title.strip()
                or action_result.description != create_request.description.strip()
                or action_result.tension_type != create_request.tension_type
                or action_result.severity != create_request.severity
                or action_result.urgency != create_request.urgency
            ):
                raise ValueError("Governance tension result does not match the create content")
            response = GovernanceTensionMutationResponse.model_validate(
                action_result.model_dump(mode="python", exclude={"tension_key"})
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension create response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension action unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")),
            status_code=201,
            headers=headers,
        )

    @router.post(
        "/operator/api/governance/{location_id}/tensions/{tension_id}/submit",
        response_model=GovernanceTensionSubmittedResponse,
        responses={
            200: {
                "model": GovernanceTensionSubmittedResponse,
                "description": (
                    "The caller's tension was submitted or an idempotent retry returned "
                    "the submitted receipt. The private operator/request key is omitted."
                ),
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            **tension_action_error_responses,
        },
    )
    async def submit_governance_tension_route(
        request: Request, location_id: str, tension_id: str
    ):
        headers = {"Cache-Control": "no-store", "Vary": "Cookie"}
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_governance_tension,
                request.state.operator_session.operator.operator_id,
                location_id,
                tension_id,
            )
        except (TenantContextDenied, GovernanceTensionInvalid, GovernanceTensionConflict, psycopg2.Error) as exc:
            return error_response(exc, headers=headers)
        try:
            action_result = _GovernanceTensionMutationResult.model_validate(result)
            if (
                action_result.tension_id != UUID(tension_id)
                or action_result.status != "submitted"
            ):
                raise ValueError("Governance tension result does not match the submit request")
            response = GovernanceTensionSubmittedResponse.model_validate(
                action_result.model_dump(mode="python", exclude={"tension_key"})
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.governance_tensions").warning(
                "Governance tension submit response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Governance tension action unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(response.model_dump(mode="python")), headers=headers
        )
