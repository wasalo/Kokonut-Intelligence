"""FastAPI route registration for Gateway-operated farm activity records."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
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
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp value is invalid") from exc
    raise ValueError("timestamp value is invalid")


_ResponseUUID = Annotated[UUID, BeforeValidator(_response_uuid)]
_ResponseDate = Annotated[date, BeforeValidator(_response_date)]
_ResponseDateTime = Annotated[datetime, BeforeValidator(_response_datetime)]


def _response_decimal(value):
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float)):
        raise ValueError("numeric value is invalid")
    try:
        result = Decimal(str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError("numeric value is invalid") from exc
    if not result.is_finite():
        raise ValueError("numeric value is invalid")
    return result


_ResponseDecimal = Annotated[Decimal, BeforeValidator(_response_decimal)]
FarmActivityStatus = Literal["draft", "submitted", "verified", "published", "rejected"]
FarmActivityOperatorAction = Literal[
    "draft_created",
    "draft_edited",
    "submitted",
    "verified",
    "published",
    "rejected",
    "rework_requested",
    "exception_closed",
]
FarmActivityChangedField = Literal[
    "plot_id",
    "crop_cycle_id",
    "activity_type",
    "activity_date",
    "description",
    "labor_hours",
    "labor_cost",
    "materials_used",
    "evidence_urls",
    "notes",
]


class FarmActivitySummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _ResponseUUID
    location_id: _ResponseUUID
    plot_id: _ResponseUUID | None
    crop_cycle_id: _ResponseUUID | None
    activity_type: str = Field(min_length=1, max_length=100)
    activity_date: _ResponseDate
    status: FarmActivityStatus
    source_system: str | None
    created_at: _ResponseDateTime | None
    updated_at: _ResponseDateTime | None


class FarmActivitySummaryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: list[FarmActivitySummaryResponse]
    location_id: _ResponseUUID

    @model_validator(mode="after")
    def validate_location_scope(self):
        for row in self.data:
            if row.location_id != self.location_id:
                raise ValueError("farm activity summary location does not match request scope")
            if row.source_system == "field_collector":
                raise ValueError("Field Collector records are outside this API contract")
        return self


class FarmActivityOperatorEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    action: FarmActivityOperatorAction
    from_status: FarmActivityStatus | None
    to_status: FarmActivityStatus
    reason: str | None
    actor_operator_id: _ResponseUUID
    changed_fields: list[FarmActivityChangedField] | None
    created_at: _ResponseDateTime


class FarmActivityDetailResponseData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    id: _ResponseUUID
    location_id: _ResponseUUID
    plot_id: _ResponseUUID | None
    crop_cycle_id: _ResponseUUID | None
    activity_type: str = Field(min_length=1, max_length=100)
    activity_date: _ResponseDate
    description: str | None
    labor_hours: _ResponseDecimal | None
    labor_cost: _ResponseDecimal | None
    materials_used: JsonValue
    evidence_urls: list[str | None] | None
    notes: str | None
    status: FarmActivityStatus
    source_system: str | None
    created_at: _ResponseDateTime | None
    updated_at: _ResponseDateTime | None
    operator_events: list[FarmActivityOperatorEventResponse] = Field(max_length=100)


class FarmActivityDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    data: FarmActivityDetailResponseData


def register_farm_activity_record_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.farm_activity_records import (
        FarmActivityRecordConflict,
        FarmActivityRecordInvalid,
        create_farm_activity_record,
        edit_farm_activity_record_draft,
        get_farm_activity_record,
        list_farm_activity_records,
        transition_farm_activity_record,
    )

    def _invalid_projection(exc):
        from services.common.logging import get_logger

        get_logger("gateway.farm_activity_records").warning(
            "Farm activity summary response rejected (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=500,
            content={"error": "Farm activity records are unavailable"},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    def _unavailable(exc):
        from services.common.logging import get_logger

        get_logger("gateway.farm_activity_records").warning(
            "Farm activity record operation unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Farm activity operation unavailable"},
            headers={"Retry-After": "30", "Cache-Control": "no-store", "Vary": "Cookie"},
        )

    def _disabled():
        return JSONResponse(
            status_code=404,
            content={"error": "Operator OIDC is disabled"},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    def _detail_response(result, activity_id, location_id, *, published_only):
        try:
            response = FarmActivityDetailResponse.model_validate({"data": result})
            if str(response.data.id) != str(UUID(activity_id)):
                raise ValueError("farm activity detail does not match request identifier")
            if str(response.data.location_id) != str(UUID(location_id)):
                raise ValueError("farm activity detail does not match request location")
            if response.data.source_system == "field_collector":
                raise ValueError("Field Collector records are outside this API contract")
            if published_only and response.data.status not in {"verified", "published"}:
                raise ValueError("published detail contains a non-verified record")
        except (ValidationError, ValueError, TypeError) as exc:
            return _invalid_projection(exc)
        return JSONResponse(
            jsonable_encoder(response.model_dump()),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    async def _invoke(function, *args, **kwargs):
        try:
            return await run_in_threadpool(function, *args, **kwargs)
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityRecordInvalid as exc:
            return JSONResponse(
                status_code=422,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except FarmActivityRecordConflict as exc:
            return JSONResponse(
                status_code=409,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "P0001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "Farm activity state or review requirements prevent this operation"},
                    headers={"Cache-Control": "no-store", "Vary": "Cookie"},
                )
            return _unavailable(exc)

    @router.get(
        "/operator/api/farm-activity-records",
        response_model=FarmActivitySummaryListResponse,
    )
    async def farm_activity_records(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            list_farm_activity_records,
            request.state.operator_session.operator.operator_id,
            location_id,
            limit,
        )
        if isinstance(result, JSONResponse):
            return result
        try:
            response = FarmActivitySummaryListResponse.model_validate(
                {"data": result, "location_id": location_id}
            )
        except (ValidationError, ValueError, TypeError) as exc:
            return _invalid_projection(exc)
        return JSONResponse(
            jsonable_encoder(response.model_dump()),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/farm-activity-records/published",
        response_model=FarmActivitySummaryListResponse,
    )
    async def published_farm_activity_records(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=100),
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            list_farm_activity_records,
            request.state.operator_session.operator.operator_id,
            location_id,
            limit,
            published_only=True,
        )
        if isinstance(result, JSONResponse):
            return result
        try:
            response = FarmActivitySummaryListResponse.model_validate(
                {"data": result, "location_id": location_id}
            )
            if any(row.status not in {"verified", "published"} for row in response.data):
                raise ValueError("published summary contains a non-verified record")
        except (ValidationError, ValueError, TypeError) as exc:
            return _invalid_projection(exc)
        return JSONResponse(
            jsonable_encoder(response.model_dump()),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/farm-activity-records/published/{activity_id}",
        response_model=FarmActivityDetailResponse,
    )
    async def published_farm_activity_record(
        request: Request, activity_id: str, location_id: str
    ):
        if provider is None:
            return _disabled()
        result = await _invoke(
            get_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            published_only=True,
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Published farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return _detail_response(result, activity_id, location_id, published_only=True)

    @router.get(
        "/operator/api/farm-activity-records/{activity_id}",
        response_model=FarmActivityDetailResponse,
    )
    async def farm_activity_record(request: Request, activity_id: str, location_id: str):
        if provider is None:
            return _disabled()
        result = await _invoke(
            get_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return _detail_response(result, activity_id, location_id, published_only=False)

    @router.post("/operator/api/farm-activity-records")
    async def create_farm_activity_record_route(
        request: Request, location_id: str, body: dict
    ):
        if provider is None:
            return _disabled()
        if set(body) != {"content"} or not isinstance(body.get("content"), dict):
            return JSONResponse(
                status_code=422,
                content={"error": "Create body must contain only a content object"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            create_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            location_id,
            body["content"],
        )
        if isinstance(result, JSONResponse):
            return result
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            status_code=201,
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.patch("/operator/api/farm-activity-records/{activity_id}/draft")
    async def edit_farm_activity_record_route(
        request: Request, activity_id: str, location_id: str, body: dict
    ):
        if provider is None:
            return _disabled()
        if set(body) != {"content", "reason"} or not isinstance(body.get("content"), dict):
            return JSONResponse(
                status_code=422,
                content={"error": "Draft edit body requires content and a correction reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            edit_farm_activity_record_draft,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            body["content"],
            body["reason"],
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Editable draft farm activity record not found"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.post("/operator/api/farm-activity-records/{activity_id}/{action}")
    async def transition_farm_activity_record_route(
        request: Request, activity_id: str, action: str, location_id: str, body: dict | None = None
    ):
        if provider is None:
            return _disabled()
        body = body or {}
        if set(body) - {"reason"}:
            return JSONResponse(
                status_code=422,
                content={"error": "Transition body accepts only a reason"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        result = await _invoke(
            transition_farm_activity_record,
            request.state.operator_session.operator.operator_id,
            activity_id,
            location_id,
            action,
            body.get("reason"),
        )
        if isinstance(result, JSONResponse):
            return result
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Farm activity record not found or transition grant unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            {"data": jsonable_encoder(result)},
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
