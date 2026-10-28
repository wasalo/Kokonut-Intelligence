"""OIDC routes for location-scoped operating-pilot reads and private drafts."""

from datetime import date, datetime
from decimal import Decimal
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


_ResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]


def _response_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("date value is invalid") from exc
    raise ValueError("date value is invalid")


def _response_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_ResponseDate = Annotated[date, BeforeValidator(_response_date)]
_ResponseDateTime = Annotated[AwareDatetime, BeforeValidator(_response_datetime)]


def _response_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise ValueError("numeric value is invalid")
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError("numeric value is invalid") from exc
    if not result.is_finite() or max(0, -result.as_tuple().exponent) > 2:
        raise ValueError("numeric value is invalid")
    return result


_ResponseDecimal = Annotated[Decimal, BeforeValidator(_response_decimal)]


class OperatingPilotCapacityPeriodItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    period_start: _ResponseDate
    period_end: _ResponseDate
    suppressed: bool
    available_hours: _ResponseDecimal | None = Field(ge=0, strict=True)
    committed_hours: _ResponseDecimal | None = Field(ge=0, strict=True)
    protected_hours: _ResponseDecimal | None = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_capacity_period(self):
        if self.period_end < self.period_start:
            raise ValueError("capacity period is reversed")
        hours = (self.available_hours, self.committed_hours, self.protected_hours)
        if self.suppressed and any(value is not None for value in hours):
            raise ValueError("suppressed capacity hours must be hidden")
        if not self.suppressed and any(value is None for value in hours):
            raise ValueError("unsuppressed capacity hours must be present")
        if not self.suppressed and self.committed_hours + self.protected_hours > self.available_hours:
            raise ValueError("capacity commitments exceed available hours")
        return self


class OperatingPilotCapacityPeriodsPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    location_id: _ResponseUUID
    scope_configured: bool
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotCapacityPeriodItem] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        periods = [(item.period_start, item.period_end) for item in self.items]
        if len(self.items) > self.limit or periods != sorted(set(periods)):
            raise ValueError("capacity-period page is not ordered or bounded")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("capacity-period continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("capacity-period page has an unexpected continuation")
        if not self.scope_configured and (self.items or self.has_more):
            raise ValueError("unconfigured capacity scope cannot contain periods")
        return self


class OperatingPilotResourceCategoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    resource_category: Literal[
        "equipment",
        "tools",
        "inputs",
        "materials",
        "infrastructure",
        "transport",
        "labor",
        "training",
        "funding",
        "other",
    ]
    suppressed: bool
    request_count: int | None = Field(ge=3, strict=True)

    @model_validator(mode="after")
    def validate_suppression(self):
        if (self.suppressed and self.request_count is not None) or (
            not self.suppressed and self.request_count is None
        ):
            raise ValueError("resource count does not match its suppression flag")
        return self


class OperatingPilotWorkClaimItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    work_type: Literal[
        "general",
        "planting",
        "harvest",
        "irrigation",
        "monitoring",
        "maintenance",
        "tree-care",
        "agroforestry",
        "soil-health",
        "water-management",
        "other",
    ]
    suppressed: bool
    claim_count: int | None = Field(ge=3, strict=True)

    @model_validator(mode="after")
    def validate_suppression(self):
        if (self.suppressed and self.claim_count is not None) or (
            not self.suppressed and self.claim_count is None
        ):
            raise ValueError("work claim count does not match its suppression flag")
        return self


class OperatingPilotWorkClaimsPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    location_id: _ResponseUUID
    scope_configured: bool
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotWorkClaimItem] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        work_types = [item.work_type for item in self.items]
        if len(self.items) > self.limit or work_types != sorted(set(work_types)):
            raise ValueError("work-claim page is not ordered or bounded")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("work-claim continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("work-claim page has an unexpected continuation")
        if not self.scope_configured and (self.items or self.has_more):
            raise ValueError("unconfigured work-claim scope cannot contain claims")
        return self


class OperatingPilotWorkOpportunityItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    work_item_id: _ResponseUUID
    title: str = Field(min_length=1, max_length=255, strict=True)
    work_type: str = Field(min_length=1, max_length=50, strict=True)
    priority: Literal["low", "medium", "high", "critical"]
    status: Literal["draft", "assigned", "in_progress", "blocked"]
    selection_mode: Literal["self_selected", "delegated", "volunteer", "rotational"]
    estimated_effort_hours: _ResponseDecimal | None = Field(
        ge=0, le=Decimal("99999999.99"), strict=True
    )
    due_at: _ResponseDateTime | None
    allocation_status: Literal["open", "claimed"]
    has_own_claim: bool = Field(strict=True)
    own_claim_status: Literal["proposed", "accepted", "rejected", "withdrawn"] | None

    @model_validator(mode="after")
    def validate_own_claim_state(self):
        if self.has_own_claim != (self.own_claim_status is not None):
            raise ValueError("own-claim state does not match its status")
        return self


class OperatingPilotWorkOpportunitiesPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    location_id: _ResponseUUID
    scope_configured: bool = Field(strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotWorkOpportunityItem] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if not self.scope_configured:
            raise ValueError("work-opportunity scope must be configured")
        rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        item_ids = [item.work_item_id for item in self.items]
        page_order = [
            (
                -rank[item.priority],
                item.due_at is None,
                item.due_at,
                item.work_item_id,
            )
            for item in self.items
        ]
        if (
            len(self.items) > self.limit
            or len(item_ids) != len(set(item_ids))
            or page_order != sorted(page_order)
        ):
            raise ValueError("work-opportunity page is not ordered or bounded")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("work-opportunity continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("work-opportunity page has an unexpected continuation")
        return self


class OperatingPilotResourceCategoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    location_id: _ResponseUUID
    scope_configured: bool
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotResourceCategoryItem] = Field(max_length=50)
    has_more: bool
    next_offset: int | None = Field(ge=0, le=10000, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        categories = [item.resource_category for item in self.items]
        if len(self.items) > self.limit or categories != sorted(set(categories)):
            raise ValueError("resource category page is not ordered or bounded")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("resource category continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("resource category page has an unexpected continuation")
        if not self.scope_configured and (self.items or self.has_more):
            raise ValueError("unconfigured resource scope cannot contain categories")
        return self


class OperatingPilotOwnCapacityProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    profile_id: _ResponseUUID
    period_start: _ResponseDate
    period_end: _ResponseDate
    available_hours: float = Field(ge=0, strict=True)
    committed_hours: float = Field(ge=0, strict=True)
    protected_hours: float = Field(ge=0, strict=True)
    notes: str | None
    source: Literal["self_reported", "manager_reviewed", "system_derived", "field_coordinator"]
    status: Literal["draft", "submitted", "approved", "superseded"]
    created_at: _ResponseDateTime
    updated_at: _ResponseDateTime

    @model_validator(mode="after")
    def validate_capacity(self):
        if self.period_end < self.period_start:
            raise ValueError("capacity profile period is reversed")
        if self.committed_hours + self.protected_hours > self.available_hours:
            raise ValueError("capacity commitments exceed available hours")
        return self


class OperatingPilotOwnCapacityProfilesPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotOwnCapacityProfileResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_continuation(self):
        if len(self.items) > self.limit:
            raise ValueError("capacity profile page exceeds its limit")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("capacity profile continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("terminal capacity profile page cannot continue")
        return self


class OperatingPilotOwnCompetencyAssessmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    draft_id: _ResponseUUID
    competency_key: str = Field(
        min_length=1,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_.-]{0,119}$",
    )
    current_level: float = Field(ge=0, le=5, strict=True)
    target_level: float = Field(ge=0, le=5, strict=True)
    evidence_note: str | None = Field(max_length=2000)
    status: Literal["draft", "superseded", "submitted", "rejected", "verified"]
    review_reason: str | None = Field(max_length=2000)
    reviewed_at: _ResponseDateTime | None
    created_at: _ResponseDateTime
    updated_at: _ResponseDateTime

    @model_validator(mode="after")
    def validate_assessment(self):
        if self.target_level < self.current_level:
            raise ValueError("target competency level is below current level")
        if self.status == "rejected" and not (self.review_reason or "").strip():
            raise ValueError("rejected competency assessment requires a review reason")
        return self


class OperatingPilotOwnCompetencyAssessmentsPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    items: list[OperatingPilotOwnCompetencyAssessmentResponse] = Field(max_length=50)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("own competency page exceeds its limit")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("own competency continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("terminal own competency page cannot continue")

        draft_ids = [item.draft_id for item in self.items]
        if len(draft_ids) != len(set(draft_ids)):
            raise ValueError("own competency page contains duplicate draft IDs")
        if any(
            (previous.created_at, previous.draft_id.int)
            < (current.created_at, current.draft_id.int)
            for previous, current in zip(self.items, self.items[1:])
        ):
            raise ValueError("own competency page is not in descending SQL order")
        return self


class OperatingPilotOwnResourceRequestItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    draft_id: _ResponseUUID
    resource_type: str = Field(
        min_length=1,
        max_length=50,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,49}$",
    )
    description: str = Field(min_length=1, max_length=2000)
    urgency: Literal["low", "medium", "high", "critical"]
    requested_by: _ResponseDate
    status: Literal["draft", "superseded", "submitted"]
    created_at: _ResponseDateTime
    updated_at: _ResponseDateTime

    @field_validator("description")
    @classmethod
    def _description_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("description must not be blank")
        return value


class OperatingPilotOwnResourceRequestsPage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    location_id: _ResponseUUID
    items: list[OperatingPilotOwnResourceRequestItemResponse] = Field(max_length=50)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10000, strict=True)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(ge=0, le=10050, strict=True)
    total: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("own resource page exceeds its limit")
        if self.has_more != (self.total > self.offset + self.limit):
            raise ValueError("own resource continuation does not match its total")
        if self.has_more:
            if len(self.items) != self.limit or self.next_offset != self.offset + self.limit:
                raise ValueError("own resource continuation does not match its page")
        elif self.next_offset is not None:
            raise ValueError("terminal own resource page cannot continue")

        ids = [item.draft_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("own resource page contains duplicate draft IDs")
        if any(
            (previous.updated_at, previous.draft_id.int)
            < (current.updated_at, current.draft_id.int)
            for previous, current in zip(self.items, self.items[1:])
        ):
            raise ValueError("own resource page is not in descending SQL order")
        return self


def register_operating_pilot_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.operating_pilot_reads import (
        OperatingPilotReadInvalid,
        get_location_operating_pilot_capacity_periods,
        get_location_operating_pilot_capacity_review_queue,
        get_location_operating_pilot_coaching_participants,
        get_location_operating_pilot_competency_review_queue,
        get_location_operating_pilot_demand_review_queue,
        get_location_operating_pilot_demand_signals,
        get_location_operating_pilot_learning_plan_activation_queue,
        get_location_operating_pilot_learning_plan_review_queue,
        get_location_operating_pilot_own_capacity_profiles,
        get_location_operating_pilot_own_coaching_sessions,
        get_location_operating_pilot_own_competency_drafts,
        get_location_operating_pilot_own_demand_signals,
        get_location_operating_pilot_own_learning_plans,
        get_location_operating_pilot_own_resource_requests,
        get_location_operating_pilot_resource_categories,
        get_location_operating_pilot_resource_fulfillment_queue,
        get_location_operating_pilot_resource_review_queue,
        get_location_operating_pilot_summary,
        get_location_operating_pilot_work_claim_allocation_queue,
        get_location_operating_pilot_work_claim_review_queue,
        get_location_operating_pilot_work_claims,
        get_location_operating_pilot_work_opportunities,
    )
    from services.gateway.operating_pilot_writes import (
        OperatingPilotWriteInvalid,
        activate_location_operating_pilot_learning_plan,
        allocate_location_operating_pilot_work_claim,
        claim_location_operating_pilot_work,
        create_location_operating_pilot_capacity_draft,
        create_location_operating_pilot_coaching_session,
        create_location_operating_pilot_competency_draft,
        create_location_operating_pilot_demand_draft,
        create_location_operating_pilot_learning_plan_draft,
        create_location_operating_pilot_resource_draft,
        fulfill_location_operating_pilot_resource_request,
        review_location_operating_pilot_capacity,
        review_location_operating_pilot_competency_assessment,
        review_location_operating_pilot_demand,
        review_location_operating_pilot_learning_plan,
        review_location_operating_pilot_resource_request,
        review_location_operating_pilot_work_claim,
        revise_location_operating_pilot_capacity_draft,
        revise_location_operating_pilot_competency_draft,
        revise_location_operating_pilot_demand_draft,
        revise_location_operating_pilot_learning_plan_draft,
        revise_location_operating_pilot_resource_draft,
        submit_location_operating_pilot_capacity_draft,
        submit_location_operating_pilot_competency_draft,
        submit_location_operating_pilot_demand_draft,
        submit_location_operating_pilot_learning_plan,
        submit_location_operating_pilot_resource_draft,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def bounded_learning_plan_payload(request):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 32 * 1024:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Learning-plan request body exceeds 32 KiB"},
                    headers=headers,
                )
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Learning-plan request body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Learning-plan request body must be an object"},
                headers=headers,
            )
        return payload, None

    async def bounded_coaching_payload(request):
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 32 * 1024:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Coaching-session request body exceeds 32 KiB"},
                    headers=headers,
                )
            body.extend(chunk)
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Coaching-session request body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Coaching-session request body must be an object"},
                headers=headers,
            )
        return payload, None

    @router.post("/operator/api/operating-pilot/{location_id}/coaching-sessions")
    async def create_operating_pilot_coaching_session(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_coaching_payload(request)
        if body_error:
            return body_error
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_coaching_session,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified coaching access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location coaching grant, participant link, and consent are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Coaching request ID was reused with different input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Coaching-session input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating coaching-session write unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating coaching-session write unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/capacity-profiles")
    async def create_operating_pilot_capacity_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location create grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A capacity profile already exists for this person and period, or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/work-claim-review-queue")
    async def location_operating_pilot_work_claim_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_work_claim_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and active reviewer binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/review"
    )
    async def review_location_operating_pilot_work_claim_route(
        request: Request,
        location_id: str,
        claim_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_work_claim,
                request.state.operator_session.operator.operator_id,
                location_id,
                claim_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and eligible claim are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or the claim was already decided"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim decision or rejection reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/work-claim-allocation-queue"
    )
    async def location_operating_pilot_work_claim_allocation_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_work_claim_allocation_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot allocation access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location allocation grant and active allocator binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work-claim allocation page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim allocation queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim allocation queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-claims/{claim_id}/allocate"
    )
    async def allocate_location_operating_pilot_work_claim_route(
        request: Request,
        location_id: str,
        claim_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim allocation body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim allocation body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if payload:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim allocation contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                allocate_location_operating_pilot_work_claim,
                request.state.operator_session.operator.operator_id,
                location_id,
                claim_id,
                request_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot allocation access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location allocation grant and eligible accepted claim are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The allocation request conflicts or the claim was already allocated"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim allocation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim allocation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}")
    async def revise_operating_pilot_capacity_draft(request: Request, location_id: str, profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and editable personal capacity record are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A capacity profile already exists for this person and period, or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/submit"
    )
    async def submit_operating_pilot_capacity_draft(request: Request, location_id: str, profile_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_capacity_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and editable personal draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The submission request ID conflicts with another capacity profile"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The capacity draft changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/demand-signals")
    async def create_operating_pilot_demand_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot create grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Request ID was already used with different demand input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning("Operating demand draft unavailable (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/resource-requests")
    async def create_operating_pilot_resource_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_resource_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location create grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Resource draft request ID was reused with different input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/learning-plans")
    async def create_operating_pilot_learning_plan_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_learning_plan_payload(request)
        if body_error:
            return body_error
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_learning_plan_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location create grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Learning-plan draft request ID was reused with different input"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Learning-plan draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.put(
        "/operator/api/operating-pilot/{location_id}/learning-plans/{learning_plan_id}"
    )
    async def revise_operating_pilot_learning_plan_draft(
        request: Request, location_id: str, learning_plan_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_learning_plan_payload(request)
        if body_error:
            return body_error
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_learning_plan_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_plan_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and owned draft are required"},
                    headers=headers,
                )
            if pgcode in {"23505", "40001"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The draft changed or the revision request conflicts; reload your history before retrying"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Learning-plan revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/learning-plans/{learning_plan_id}/submit"
    )
    async def submit_operating_pilot_learning_plan(
        request: Request, location_id: str, learning_plan_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, error_response = await bounded_learning_plan_payload(request)
        if error_response is not None:
            return error_response
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Learning-plan submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_learning_plan,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_plan_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and owned draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The learning-plan submission request conflicts or this draft is already submitted"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The learning-plan draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        result_plan_id = result.get("learning_plan_id")
        if (
            not isinstance(result_plan_id, str)
            or result_plan_id.lower() != learning_plan_id.lower()
            or result.get("status") not in {"draft", "submitted", "active", "completed", "paused", "cancelled"}
        ):
            return JSONResponse(
                status_code=409,
                content={"error": "The learning plan is no longer pending submission; refresh your history"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post("/operator/api/operating-pilot/{location_id}/competency-assessments")
    async def create_operating_pilot_competency_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency draft body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency draft body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                create_location_operating_pilot_competency_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot create access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location create grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "An open competency draft exists or the request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency draft input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency draft unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)

    @router.put(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}"
    )
    async def revise_operating_pilot_competency_draft(
        request: Request, location_id: str, draft_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_competency_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and editable personal competency assessment are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "A competency draft already exists or the revision request conflicts"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The competency assessment changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}/submit"
    )
    async def submit_operating_pilot_competency_draft(
        request: Request, location_id: str, draft_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_competency_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and editable personal competency draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The submission request ID conflicts with another competency assessment"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The competency assessment changed; refresh before trying again"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}")
    async def revise_operating_pilot_resource_draft(request: Request, location_id: str, draft_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_resource_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and editable personal resource draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Resource revision request conflicts or the draft is no longer editable"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{draft_id}/submit"
    )
    async def submit_operating_pilot_resource_draft(
        request: Request, location_id: str, draft_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource submission requires only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_resource_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and owned resource draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource submission conflicts or this draft is already submitted"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/submit"
    )
    async def submit_operating_pilot_demand_draft(
        request: Request, location_id: str, signal_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand submission body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand submission accepts only a request_id"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                submit_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot submit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location submit-own grant and owned demand draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand submission conflicts or this draft is already submitted"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating demand submission unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand submission unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.put("/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}")
    async def revise_operating_pilot_demand_draft(request: Request, location_id: str, signal_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand revision body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand revision body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        try:
            result = await run_in_threadpool(
                revise_location_operating_pilot_demand_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot edit-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location edit-own grant and editable personal demand draft are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Demand revision request conflicts or the record is no longer editable"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The demand draft changed; refresh before trying again"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand revision input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating demand revision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand revision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/summary")
    async def location_operating_pilot_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating pilot summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating pilot summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/demand-signals")
    async def location_operating_pilot_demand_signals(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_demand_signals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning("Operating demand read unavailable (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/capacity-periods",
        response_model=OperatingPilotCapacityPeriodsPage,
    )
    async def location_operating_pilot_capacity_periods(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_capacity_periods,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotCapacityPeriodsPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Capacity-period page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity-period response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Operating capacity read unavailable"},
                headers=headers,
            )
        # Keep PostgreSQL's JSON numeric representation (numbers, not Decimal strings).
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/my-capacity-profiles",
        response_model=OperatingPilotOwnCapacityProfilesPage,
    )
    async def location_operating_pilot_own_capacity_profiles(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_capacity_profiles,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-capacity access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-capacity grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-capacity page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating capacity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating capacity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotOwnCapacityProfilesPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Own capacity page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating capacity response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Own operating capacity read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/my-competency-assessments",
        response_model=OperatingPilotOwnCompetencyAssessmentsPage,
    )
    async def location_operating_pilot_own_competency_drafts(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_competency_drafts,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-competency access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-history grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own competency page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own competency history unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own competency history unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotOwnCompetencyAssessmentsPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Own competency page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own competency response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Own competency history unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(page), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-learning-plans")
    async def location_operating_pilot_own_learning_plans(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_learning_plans,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-learning-plan access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-history grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own learning-plan page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own learning-plan history unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own learning-plan history unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-coaching-sessions")
    async def location_operating_pilot_own_coaching_sessions(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_coaching_sessions,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-coaching access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location coaching grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own coaching-session page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own coaching-session history unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own coaching-session history unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/coaching-participants")
    async def location_operating_pilot_coaching_participants(
        request: Request,
        location_id: str,
        q: str | None = None,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_coaching_participants,
                request.state.operator_session.operator.operator_id,
                location_id,
                search=q,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified coaching access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location coaching grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Coaching participant search or page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Coaching participant lookup unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Coaching participant lookup unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/my-demand-signals")
    async def location_operating_pilot_own_demand_signals(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_demand_signals,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-demand access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location own-demand grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-demand page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating demand read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating demand read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/my-resource-requests",
        response_model=OperatingPilotOwnResourceRequestsPage,
    )
    async def location_operating_pilot_own_resource_requests(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_own_resource_requests,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified own-resource access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location read_own grant and human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Own-resource page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating resource read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Own operating resource read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotOwnResourceRequestsPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Own resource page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Own operating resource response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Own operating resource read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/capacity-review-queue")
    async def location_operating_pilot_capacity_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_capacity_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified capacity review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/competency-review-queue")
    async def location_operating_pilot_competency_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_competency_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified competency review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/learning-plan-review-queue")
    async def location_operating_pilot_learning_plan_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_learning_plan_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified learning-plan review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Learning-plan review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/learning-plan-activation-queue")
    async def location_operating_pilot_learning_plan_activation_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_learning_plan_activation_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified learning-plan activation access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location activation grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Learning-plan activation page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan activation queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan activation queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/learning-plans/{learning_plan_id}/review"
    )
    async def review_operating_pilot_learning_plan(
        request: Request, location_id: str, learning_plan_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_learning_plan_payload(request)
        if body_error is not None:
            return body_error
        request_id = payload.pop("request_id", None)
        if set(payload) - {"submitted_at", "decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Learning-plan review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_learning_plan,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_plan_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified learning-plan review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or this submission already has a decision"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "This submitted plan changed; refresh the review queue"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Learning-plan review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/learning-plans/{learning_plan_id}/activate"
    )
    async def activate_operating_pilot_learning_plan(
        request: Request, location_id: str, learning_plan_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        payload, body_error = await bounded_learning_plan_payload(request)
        if body_error is not None:
            return body_error
        request_id = payload.pop("request_id", None)
        if set(payload) - {"submitted_at"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Learning-plan activation contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                activate_location_operating_pilot_learning_plan,
                request.state.operator_session.operator.operator_id,
                location_id,
                learning_plan_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified learning-plan activation access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location activation grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The activation request conflicts or this submission was already activated"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "This approved submission changed; refresh the activation queue"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating learning-plan activation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating learning-plan activation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/demand-review-queue")
    async def location_operating_pilot_demand_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_demand_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified demand review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating demand review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/resource-review-queue")
    async def location_operating_pilot_resource_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_resource_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource review access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource review page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get("/operator/api/operating-pilot/{location_id}/resource-fulfillment-queue")
    async def location_operating_pilot_resource_fulfillment_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_resource_fulfillment_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource fulfillment access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location fulfillment grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource fulfillment page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource fulfillment queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource fulfillment queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/review"
    )
    async def review_operating_pilot_resource_request(
        request: Request, location_id: str, resource_request_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Resource review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_resource_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                resource_request_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or this submission already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Resource review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/resource-requests/{resource_request_id}/fulfill"
    )
    async def fulfill_operating_pilot_resource_request(
        request: Request, location_id: str, resource_request_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource fulfillment body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Resource fulfillment requires only a request ID"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                fulfill_location_operating_pilot_resource_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                resource_request_id,
                payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified resource fulfillment access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location fulfillment grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The fulfillment request conflicts or this resource was already fulfilled"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The resource request changed before fulfillment was recorded"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource fulfillment unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource fulfillment unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/competency-assessments/{draft_id}/review"
    )
    async def review_operating_pilot_competency_assessment(
        request: Request, location_id: str, draft_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Competency review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Competency review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_competency_assessment,
                request.state.operator_session.operator.operator_id,
                location_id,
                draft_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified competency review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The competency review request conflicts or this assessment already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Competency review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating competency review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating competency review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/capacity-profiles/{profile_id}/review"
    )
    async def review_operating_pilot_capacity_profile(
        request: Request, location_id: str, profile_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Capacity review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_capacity,
                request.state.operator_session.operator.operator_id,
                location_id,
                profile_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or this submission already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Capacity review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating capacity review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating capacity review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/demand-signals/{signal_id}/review"
    )
    async def review_operating_pilot_demand_signal(
        request: Request, location_id: str, signal_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand review body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Demand review body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"decision", "reason"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Demand review contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                review_location_operating_pilot_demand,
                request.state.operator_session.operator.operator_id,
                location_id,
                signal_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot review access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location review grant and independent human binding are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request conflicts or this submission already has a decision"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Demand review decision or reason is invalid"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating demand review decision unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating demand review decision unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/work-claims",
        response_model=OperatingPilotWorkClaimsPage,
    )
    async def location_operating_pilot_work_claims(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_work_claims,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotWorkClaimsPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Work-claim page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Operating work-claim read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(page), headers=headers)

    @router.get(
        "/operator/api/operating-pilot/{location_id}/resource-categories",
        response_model=OperatingPilotResourceCategoryPage,
    )
    async def location_operating_pilot_resource_categories(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_resource_categories,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location operating-pilot read grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating resource read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotResourceCategoryPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Operating resource page does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating resource response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Operating resource read unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/operating-pilot/{location_id}/work-opportunities",
        response_model=OperatingPilotWorkOpportunitiesPage,
    )
    async def location_operating_pilot_work_opportunities(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_operating_pilot_work_opportunities,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot claim-own access is required"},
                headers=headers,
            )
        except OperatingPilotReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location claim-own grant and active human binding are required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Work opportunity page is outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-opportunity read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-opportunity read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            page = OperatingPilotWorkOpportunitiesPage.model_validate(result)
            if (
                page.location_id != UUID(location_id)
                or page.limit != limit
                or page.offset != offset
            ):
                raise ValueError("Work-opportunity page does not match request scope or bounds")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-opportunity response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Operating work-opportunity read unavailable"},
                headers=headers,
            )
        # Keep PostgreSQL's JSON numeric representation (numbers, not Decimal strings).
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/operating-pilot/{location_id}/work-opportunities/{work_item_id}/claims"
    )
    async def claim_location_operating_pilot_work_route(
        request: Request,
        location_id: str,
        work_item_id: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return JSONResponse(
                status_code=400,
                content={"error": "Work-claim body must be an object"},
                headers=headers,
            )
        request_id = payload.pop("request_id", None)
        if set(payload) - {"proposed_effort_hours"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Work claim contains unsupported fields"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                claim_location_operating_pilot_work,
                request.state.operator_session.operator.operator_id,
                location_id,
                work_item_id,
                request_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operating-pilot claim-own access is required"},
                headers=headers,
            )
        except OperatingPilotWriteInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location claim-own grant and open work opportunity are required"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The work-claim request conflicts or this person already has a claim"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Proposed work effort is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "No active operating-pilot scope is mapped to this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.operating_pilot").warning(
                "Operating work-claim proposal unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Operating work-claim proposal unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=201, headers=headers)
