"""OIDC routes for location-scoped private Delphi minority-report review."""

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, ValidationError


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


class _MinorityReviewResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class DelphiMinorityReportReviewItem(_MinorityReviewResponseModel):
    report_id: StrictUuid
    study_id: StrictUuid
    study_title: str = Field(max_length=255)
    item_id: StrictUuid | None
    item_label: str | None = Field(max_length=255)
    title: str = Field(min_length=1, max_length=255)
    position_summary: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=8000)
    implications: str | None = Field(max_length=3000)
    submitted_at: AwareDatetime | None
    created_at: AwareDatetime | None


class DelphiMinorityReportReviewPage(_MinorityReviewResponseModel):
    location_id: StrictUuid
    offset: int = Field(ge=0, le=10_000)
    reports: list[DelphiMinorityReportReviewItem] = Field(max_length=50)
    has_more: bool

    def validate_request(self, *, location_id: UUID, limit: int, offset: int):
        if self.location_id != location_id or self.offset != offset:
            raise ValueError("response scope does not match request")
        if len(self.reports) > limit:
            raise ValueError("response exceeds requested page size")
        if self.has_more and (len(self.reports) != limit or offset + limit > 10_000):
            raise ValueError("response continuation exceeds requested bounds")
        return self


def register_delphi_minority_review_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_minority_review import (
        DelphiMinorityReviewInvalid,
        decide_location_delphi_minority_report,
        list_location_delphi_minority_reports,
    )

    headers = {"Cache-Control": "no-store", "Pragma": "no-cache", "Vary": "Cookie"}

    def database_error(exc):
        code = getattr(exc, "pgcode", None)
        if code == "42501":
            return JSONResponse(
                status_code=403,
                content={"error": "A current location Delphi review grant is required"},
                headers=headers,
            )
        if code == "55000":
            return JSONResponse(
                status_code=409,
                content={"error": "The minority report is not currently reviewable"},
                headers=headers,
            )
        if code == "22023":
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi minority-report review request is invalid"},
                headers=headers,
            )
        from services.common.logging import get_logger

        get_logger("gateway.delphi_minority_review").warning(
            "Delphi minority-report review unavailable (%s)", type(exc).__name__
        )
        return JSONResponse(
            status_code=503,
            content={"error": "Delphi minority-report review unavailable"},
            headers={**headers, "Retry-After": "30"},
        )

    @router.get(
        "/operator/api/delphi/{location_id}/minority-reports",
        response_model=DelphiMinorityReportReviewPage,
    )
    async def list_minority_reports(
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
                list_location_delphi_minority_reports,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiMinorityReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        try:
            page = DelphiMinorityReportReviewPage.model_validate(result)
            page.validate_request(
                location_id=UUID(location_id), limit=limit, offset=offset
            )
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_minority_review").warning(
                "Delphi minority-report response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi minority-report review unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(page.model_dump(mode="json")), headers=headers
        )

    @router.post(
        "/operator/api/delphi/{location_id}/minority-reports/{report_id}/decision"
    )
    async def decide_minority_report(request: Request, location_id: str, report_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "A JSON decision object is required"},
                headers=headers,
            )
        expected = {"decision", "request_id", "reason_code"}
        if (
            not isinstance(payload, dict)
            or set(payload) != expected
            or not all(isinstance(payload.get(key), str) for key in expected)
        ):
            return JSONResponse(
                status_code=400,
                content={"error": "Decision fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                decide_location_delphi_minority_report,
                request.state.operator_session.operator.operator_id,
                location_id,
                report_id,
                decision=payload["decision"],
                request_id=payload["request_id"],
                reason_code=payload["reason_code"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi review access is required"},
                headers=headers,
            )
        except DelphiMinorityReviewInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            return database_error(exc)
        return JSONResponse(jsonable_encoder(result), headers=headers)
