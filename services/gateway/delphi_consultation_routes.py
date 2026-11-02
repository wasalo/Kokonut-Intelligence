"""OIDC route for location-scoped Delphi consultation summaries."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    FiniteFloat,
    ValidationError,
    model_validator,
)


def _strict_uuid(value):
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("UUID values must be strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError("UUID value is invalid") from exc


_StrictUuid = Annotated[UUID, BeforeValidator(_strict_uuid)]


def _strict_aware_datetime(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("datetime value is invalid") from exc
    else:
        raise ValueError("datetime values must be ISO strings or datetime objects")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime values must include a UTC offset")
    return parsed


_StrictAwareDatetime = Annotated[AwareDatetime, BeforeValidator(_strict_aware_datetime)]


class _DelphiConsultationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class _DelphiConsultationItem(_DelphiConsultationResponse):
    item_id: _StrictUuid
    label: str = Field(max_length=255)
    description: str | None
    item_type: Literal["issue", "goal", "option"]
    scale: Literal[
        "desirability",
        "feasibility_technical",
        "feasibility_political",
        "probability",
    ]
    minimum: FiniteFloat | None
    maximum: FiniteFloat | None
    results_available: bool
    participant_count: int | None = Field(default=None, ge=0, strict=True)
    median: FiniteFloat | None
    mean: FiniteFloat | None
    interquartile_range: FiniteFloat | None
    standard_deviation: FiniteFloat | None
    weighted_median: FiniteFloat | None
    coefficient_of_variation: FiniteFloat | None
    consensus_reached: bool | None
    # The item projection is JSONB, so PostgreSQL returns this timestamp as an
    # ISO string even though the outer study timestamps remain native datetimes.
    computed_at: _StrictAwareDatetime | None

    @model_validator(mode="after")
    def validate_privacy_gate(self):
        statistics = (
            self.median,
            self.mean,
            self.interquartile_range,
            self.standard_deviation,
            self.weighted_median,
            self.coefficient_of_variation,
            self.consensus_reached,
        )
        if self.results_available:
            if self.participant_count is None or self.participant_count < 3:
                raise ValueError("Available Delphi results require the privacy floor")
        elif self.participant_count is not None or any(value is not None for value in statistics):
            raise ValueError("Suppressed Delphi results cannot expose participant statistics")
        return self


class _DelphiConsultationStudy(_DelphiConsultationResponse):
    study_id: _StrictUuid
    title: str = Field(max_length=255)
    description: str | None
    variation: Literal[
        "classic", "policy", "argument", "disaggregative", "real_time", "fast_track"
    ]
    status: Literal["draft", "open", "closed"]
    opened_at: AwareDatetime | None
    closed_at: AwareDatetime | None
    created_at: AwareDatetime | None
    items: list[_DelphiConsultationItem]


class _DelphiConsultationPage(_DelphiConsultationResponse):
    location_id: _StrictUuid
    offset: int = Field(ge=0, le=10000, strict=True)
    studies: list[_DelphiConsultationStudy] = Field(max_length=50)
    has_more: bool

    @model_validator(mode="after")
    def validate_continuation(self):
        if self.has_more and (not self.studies or self.offset >= 10000):
            raise ValueError("Delphi consultation continuation is outside the page bounds")
        return self


def register_delphi_consultation_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_consultation import (
        DelphiConsultationInvalid,
        list_location_delphi_consultations,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/delphi/{location_id}/studies",
        response_model=_DelphiConsultationPage,
    )
    async def list_delphi_consultations(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
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
                list_location_delphi_consultations,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi access is required"},
                headers=headers,
            )
        except DelphiConsultationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi grant is required"},
                    headers=headers,
                )
            if getattr(exc, "pgcode", None) == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Delphi consultation request is invalid"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_consultation").warning(
                "Delphi consultation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi consultation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = _DelphiConsultationPage.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.offset != offset
                or len(validated.studies) > limit
                or (
                    validated.has_more
                    and (len(validated.studies) != limit or offset + limit > 10000)
                )
            ):
                raise ValueError("Delphi consultation response does not match request bounds")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_consultation").warning(
                "Delphi consultation response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi consultation unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
