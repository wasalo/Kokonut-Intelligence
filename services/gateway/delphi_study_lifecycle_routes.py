"""OIDC routes for Delphi study opening readiness and lifecycle transitions."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


def _strict_response_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


_ResponseUUID = Annotated[UUID, BeforeValidator(_strict_response_uuid)]


class DelphiStudyOpenReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    study_id: _ResponseUUID
    location_id: _ResponseUUID
    status: Literal["draft", "open", "closed"]
    has_question: bool
    minimum_policy_valid: bool
    consent_minimum_met: bool
    eligible_to_open: bool
    blocker_codes: list[
        Literal[
            "study_not_draft",
            "question_required",
            "minimum_participants_invalid",
            "consented_panel_below_minimum",
        ]
    ] = Field(max_length=4)

    @model_validator(mode="after")
    def validate_readiness(self):
        if len(self.blocker_codes) != len(set(self.blocker_codes)):
            raise ValueError("readiness blocker codes must be unique")
        expected_blockers = []
        if self.status != "draft":
            expected_blockers.append("study_not_draft")
        if not self.has_question:
            expected_blockers.append("question_required")
        if not self.minimum_policy_valid:
            expected_blockers.append("minimum_participants_invalid")
            if self.consent_minimum_met:
                raise ValueError("consent minimum cannot be met with invalid policy")
        elif not self.consent_minimum_met:
            expected_blockers.append("consented_panel_below_minimum")
        if self.blocker_codes != expected_blockers:
            raise ValueError("readiness blocker codes do not match the source facts")
        if self.eligible_to_open != (not expected_blockers):
            raise ValueError("readiness eligibility does not match its blockers")
        return self


def register_delphi_study_lifecycle_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.delphi_study_lifecycle import (
        DelphiStudyLifecycleInvalid,
        evaluate_location_delphi_stopping,
        get_location_delphi_study_open_readiness,
        transition_location_delphi_study,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    async def transition(request: Request, location_id: str, study_id: str, action: str):
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
                content={"error": "A Delphi lifecycle request object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi lifecycle request fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                transition_location_delphi_study,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                action,
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": f"Tenant-qualified Delphi {action} access is required"},
                headers=headers,
            )
        except DelphiStudyLifecycleInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": f"A current location Delphi {action} grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The study is not ready for this transition or the request conflicts"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi study lifecycle request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study lifecycle request unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=200, headers=headers)

    @router.get(
        "/operator/api/delphi/{location_id}/studies/{study_id}/open-readiness",
        response_model=DelphiStudyOpenReadinessResponse,
    )
    async def open_readiness(request: Request, location_id: str, study_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_delphi_study_open_readiness,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi open access is required"},
                headers=headers,
            )
        except DelphiStudyLifecycleInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi open grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi study readiness request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi study readiness is unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            readiness = DelphiStudyOpenReadinessResponse.model_validate(result)
            if (
                readiness.location_id != UUID(location_id)
                or readiness.study_id != UUID(study_id)
            ):
                raise ValueError("Delphi readiness response does not match request scope")
        except (ValidationError, ValueError, TypeError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi study readiness response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Delphi study readiness is unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(readiness.model_dump()), status_code=200, headers=headers
        )

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/open")
    async def open_study(request: Request, location_id: str, study_id: str):
        return await transition(request, location_id, study_id, "open")

    @router.post("/operator/api/delphi/{location_id}/studies/{study_id}/close")
    async def close_study(request: Request, location_id: str, study_id: str):
        return await transition(request, location_id, study_id, "close")

    @router.post(
        "/operator/api/delphi/{location_id}/studies/{study_id}/stopping-evaluation"
    )
    async def evaluate_stopping(request: Request, location_id: str, study_id: str):
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
                content={"error": "A Delphi stopping request object is required"},
                headers=headers,
            )
        if not isinstance(payload, dict) or set(payload) != {"request_id"}:
            return JSONResponse(
                status_code=400,
                content={"error": "Delphi stopping request fields are invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                evaluate_location_delphi_stopping,
                request.state.operator_session.operator.operator_id,
                location_id,
                study_id,
                request_id=payload["request_id"],
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified Delphi stopping access is required"},
                headers=headers,
            )
        except DelphiStudyLifecycleInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location Delphi stopping grant is required"},
                    headers=headers,
                )
            if code in {"22023", "55000"}:
                return JSONResponse(
                    status_code=409,
                    content={"error": "The study or stopping request is not eligible"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.delphi_study_lifecycle").warning(
                "Delphi stopping evaluation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Delphi stopping evaluation is unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=200, headers=headers)
