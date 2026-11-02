"""OIDC routes for location-scoped, advisory-only backcast readback."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


def _uuid_value(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("invalid UUID") from exc
    raise ValueError("invalid UUID")


def _aware_datetime_value(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamp") from exc
    raise ValueError("invalid timestamp")


_UUID = Annotated[UUID, BeforeValidator(_uuid_value)]
_AwareDatetime = Annotated[AwareDatetime, BeforeValidator(_aware_datetime_value)]


class _ThreatcastingResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class BackcastPageCursor(_ThreatcastingResponseModel):
    created_at: _AwareDatetime
    plan_id: _UUID


class BackcastPlanSummary(_ThreatcastingResponseModel):
    id: _UUID
    plan_name: str = Field(min_length=1, max_length=200)
    future_state_description: str = Field(min_length=1)
    current_gap_analysis: str = Field(min_length=1)
    created_at: _AwareDatetime
    updated_at: _AwareDatetime
    narrative_id: _UUID
    narrative_type: Literal["desirable", "undesirable", "baseline", "wildcard"]
    narrative_title: str = Field(min_length=1, max_length=200)
    threat_id: _UUID
    threat_name: str = Field(min_length=1, max_length=200)
    milestone_count: int = Field(ge=0, strict=True)
    completed_milestone_count: int = Field(ge=0, strict=True)
    blocked_milestone_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_milestone_counts(self):
        if self.completed_milestone_count + self.blocked_milestone_count > self.milestone_count:
            raise ValueError("milestone counts exceed the total")
        return self


class BackcastPlanPage(_ThreatcastingResponseModel):
    location_id: _UUID
    advisory_only: Literal[True]
    items: list[BackcastPlanSummary] = Field(max_length=100)
    next_cursor: BackcastPageCursor | None


class BackcastMilestone(_ThreatcastingResponseModel):
    id: _UUID
    milestone_order: int = Field(gt=0, strict=True)
    milestone_description: str = Field(min_length=1)
    milestone_target_date: date | None
    milestone_status: Literal["pending", "in_progress", "completed", "skipped", "blocked"]
    dependencies: list[_UUID] | None
    responsible_party: str | None = Field(max_length=100)
    resource_requirements: str | None
    completion_evidence: str | None
    created_at: _AwareDatetime
    updated_at: _AwareDatetime


class BackcastPlanDetail(_ThreatcastingResponseModel):
    id: _UUID
    location_id: _UUID
    plan_name: str = Field(min_length=1, max_length=200)
    future_state_description: str = Field(min_length=1)
    current_gap_analysis: str = Field(min_length=1)
    created_at: _AwareDatetime
    updated_at: _AwareDatetime
    narrative_id: _UUID
    narrative_type: Literal["desirable", "undesirable", "baseline", "wildcard"]
    narrative_title: str = Field(min_length=1, max_length=200)
    threat_id: _UUID
    threat_name: str = Field(min_length=1, max_length=200)
    milestones: list[BackcastMilestone] = Field(max_length=500)
    advisory_only: Literal[True]

    @model_validator(mode="after")
    def validate_milestone_order(self):
        orders = [milestone.milestone_order for milestone in self.milestones]
        if orders != sorted(set(orders)):
            raise ValueError("milestones must have unique ascending order")
        return self


def _bind_page_to_request(page, *, location_id, limit, cursor_created_at, cursor_plan_id):
    expected_location = _uuid_value(location_id)
    if page.location_id != expected_location or len(page.items) > limit:
        raise ValueError("backcast page does not match request bounds")

    request_cursor = None
    if (cursor_created_at is None) != (cursor_plan_id is None):
        raise ValueError("backcast request cursor is incomplete")
    if cursor_created_at is not None:
        request_cursor = (
            _aware_datetime_value(cursor_created_at),
            _uuid_value(cursor_plan_id),
        )
        if request_cursor[0].tzinfo is None or request_cursor[0].utcoffset() is None:
            raise ValueError("backcast request cursor is not timezone-aware")

    keys = [(item.created_at, item.id) for item in page.items]
    if any(current >= previous for previous, current in zip(keys, keys[1:])):
        raise ValueError("backcast page is not strictly descending")
    if request_cursor is not None and keys and keys[0] >= request_cursor:
        raise ValueError("backcast page does not follow the requested cursor")

    if page.next_cursor is not None:
        if len(page.items) != limit or not keys:
            raise ValueError("backcast continuation cursor has no full page")
        if (page.next_cursor.created_at, page.next_cursor.plan_id) != keys[-1]:
            raise ValueError("backcast continuation cursor does not match the last item")
    return page


def register_threatcasting_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.threatcasting_reads import (
        ThreatcastingReadInvalid,
        ThreatcastingReadTooLarge,
        get_location_backcast_plan,
        list_location_backcast_plans,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def unavailable(exc):
        from services.common.logging import get_logger

        get_logger("gateway.threatcasting").warning("Threatcasting read unavailable (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"error": "Threatcasting read unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    def tenant_denied():
        return JSONResponse(
            status_code=403,
            content={"error": "Tenant-qualified operator access is required"},
            headers=headers,
        )

    @router.get(
        "/operator/api/threatcasting/{location_id}/backcast-plans",
        response_model=BackcastPlanPage,
    )
    async def location_backcast_plans(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
        cursor_created_at: str | None = Query(default=None, max_length=64),
        cursor_plan_id: str | None = Query(default=None, max_length=36),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_backcast_plans,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_plan_id=cursor_plan_id,
            )
        except TenantContextDenied:
            return tenant_denied()
        except ThreatcastingReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return tenant_denied()
            return unavailable(exc)
        try:
            page = _bind_page_to_request(
                BackcastPlanPage.model_validate(result),
                location_id=location_id,
                limit=limit,
                cursor_created_at=cursor_created_at,
                cursor_plan_id=cursor_plan_id,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.threatcasting").warning("Threatcasting page response rejected (%s)", type(exc).__name__)
            return JSONResponse(
                status_code=500,
                content={"error": "Threatcasting read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(page.model_dump(mode="json")), headers=headers)

    @router.get(
        "/operator/api/threatcasting/{location_id}/backcast-plans/{plan_id}",
        response_model=BackcastPlanDetail,
    )
    async def location_backcast_plan(request: Request, location_id: str, plan_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_backcast_plan,
                request.state.operator_session.operator.operator_id,
                location_id,
                plan_id,
            )
        except TenantContextDenied:
            return tenant_denied()
        except ThreatcastingReadTooLarge:
            return JSONResponse(
                status_code=413,
                content={"error": "Backcast plan exceeds the maximum readable response size"},
                headers=headers,
            )
        except ThreatcastingReadInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return tenant_denied()
            return unavailable(exc)
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Backcast plan not found in this location"},
                headers=headers,
            )
        try:
            plan = BackcastPlanDetail.model_validate(result)
            if plan.location_id != _uuid_value(location_id) or plan.id != _uuid_value(plan_id):
                raise ValueError("backcast detail does not match request identifiers")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.threatcasting").warning(
                "Threatcasting detail response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Threatcasting read unavailable"},
                headers=headers,
            )
        return JSONResponse(jsonable_encoder(plan.model_dump(mode="json")), headers=headers)
