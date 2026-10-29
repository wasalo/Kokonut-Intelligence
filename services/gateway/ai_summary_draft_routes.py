"""OIDC routes for authenticated AI-summary and synthesis draft requests."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

from services.gateway.ai_summary_contracts import (
    AiSummaryContractError,
    AiSummaryDraftRequest,
    AiSummaryDraftResponse,
)
from services.gateway.ai_summary_task_request import TASK_SUMMARY_TYPES

RegisteredTaskKey = Literal[
    "ai_summary_synthesis",
    "organic_readiness_synthesis",
    "ecological_modeling_synthesis",
    "holistic_wellbeing_synthesis",
    "feedback_synthesis",
    "commons_liberation_synthesis",
    "gnh_alignment_synthesis",
    "regenerator_synthesis",
    "capital_efficiency_synthesis",
    "financial_resilience_synthesis",
    "bio_factory_synthesis",
    "open_source_capitalist_synthesis",
    "kokonut_commons_synthesis",
]
RegisteredSummaryType = Literal[
    "operations",
    "financial",
    "environmental",
    "combined",
    "organic_readiness",
    "ecological_modeling",
    "holistic_wellbeing",
    "stakeholder_feedback",
    "commons_liberation",
    "gnh_alignment",
    "regenerative_outcomes",
    "capital_efficiency",
    "financial_resilience",
    "bio_factory",
    "open_source_capitalist",
    "kokonut_commons",
]


class _AiSummaryTaskContract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AiSummaryTaskRequestBody(_AiSummaryTaskContract):
    task_key: RegisteredTaskKey = Field(description="Registered synthesis task key.")
    summary_type: RegisteredSummaryType = Field(
        description="Summary type registered for this task key."
    )
    request_id: UUID

    @model_validator(mode="after")
    def summary_type_matches_task(self):
        if self.summary_type not in TASK_SUMMARY_TYPES[self.task_key]:
            raise ValueError("summary_type is not registered for task_key")
        return self


class AiSummaryTaskReceipt(_AiSummaryTaskContract):
    request_id: UUID
    location_id: UUID
    task_key: RegisteredTaskKey
    summary_type: RegisteredSummaryType
    created_at: AwareDatetime
    replayed: bool = Field(strict=True)
    status: Literal["authorized"]

    @model_validator(mode="after")
    def summary_type_matches_task(self):
        if self.summary_type not in TASK_SUMMARY_TYPES[self.task_key]:
            raise ValueError("summary_type is not registered for task_key")
        return self


class AiSummaryTaskError(_AiSummaryTaskContract):
    error: str


def register_ai_summary_draft_routes(router, provider, run_in_threadpool, psycopg2):
    import json

    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.ai_summary_draft import (
        AiSummaryDraftInvalid,
        create_operator_ai_summary_draft,
    )
    from services.gateway.ai_summary_task_request import (
        AiSummaryTaskRequestInvalid,
        create_operator_ai_summary_task_request,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    draft_error_responses = {
        status: {
            "model": AiSummaryContractError,
            "description": description,
            "headers": {
                "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                "Vary": {"schema": {"type": "string", "example": "Cookie"}},
            },
        }
        for status, description in {
            400: "The AI-summary draft request is invalid.",
            403: "The operator lacks a current location-scoped draft grant.",
            404: "Operator OIDC is disabled.",
            409: "The retry ID conflicts or reviewed source data is insufficient.",
            500: "The private draft failed its response contract.",
            503: "The AI-summary draft service is unavailable.",
        }.items()
    }

    @router.post(
        "/operator/api/ai-summaries/{location_id}/drafts",
        response_model=AiSummaryDraftResponse,
        responses={201: {"model": AiSummaryDraftResponse}, **draft_error_responses},
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": AiSummaryDraftRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def create_summary_draft(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(status_code=400, content={"error": "Invalid JSON body"}, headers=headers)
        try:
            draft_request = AiSummaryDraftRequest.model_validate(payload)
            requested_location_id = UUID(location_id)
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "AI summary draft request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_operator_ai_summary_draft,
                request.state.operator_session.operator.operator_id,
                location_id,
                summary_type=draft_request.summary_type,
                request_id=str(draft_request.request_id),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary draft access is required"},
                headers=headers,
            )
        except AiSummaryDraftInvalid:
            return JSONResponse(
                status_code=400,
                content={"error": "AI summary draft request is invalid"},
                headers=headers,
            )
        except ValueError:
            return JSONResponse(
                status_code=409,
                content={"error": "Current reviewed location data is insufficient to generate this summary"},
                headers=headers,
            )
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location AI-summary draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The retry ID was reused with different draft content"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_draft").warning(
                "AI summary draft unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "AI summary draft generation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            draft = AiSummaryDraftResponse.model_validate(result)
            if (
                draft.location_id != requested_location_id
                or draft.summary_type != draft_request.summary_type
            ):
                raise ValueError("draft response does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_draft").warning(
                "AI summary draft rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "AI summary draft generation unavailable"},
                headers=headers,
            )
        status_code = 200 if draft.replayed else 201
        return JSONResponse(
            jsonable_encoder(draft.model_dump(mode="python")),
            status_code=status_code,
            headers=headers,
        )

    task_request_body = {
        "required": True,
        "content": {
            "application/json": {
                "schema": AiSummaryTaskRequestBody.model_json_schema()
            }
        },
    }
    task_error_responses = {
        status: {"model": AiSummaryTaskError, "description": description}
        for status, description in {
            400: "The synthesis task request is invalid.",
            403: "The operator lacks a location-scoped AI-summary draft grant.",
            404: "Operator OIDC is disabled.",
            409: "The retry ID conflicts with a different task intent.",
            500: "The task receipt failed its response contract.",
            503: "The task request service is unavailable.",
        }.items()
    }

    @router.post(
        "/operator/api/ai-summaries/{location_id}/synthesis-requests",
        response_model=AiSummaryTaskReceipt,
        responses={201: {"model": AiSummaryTaskReceipt}, **task_error_responses},
        openapi_extra={"requestBody": task_request_body},
    )
    async def create_synthesis_request(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Synthesis task request is invalid"},
                headers=headers,
            )
        try:
            payload = AiSummaryTaskRequestBody.model_validate(body)
        except (ValidationError, TypeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"error": "Synthesis task request is invalid"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                create_operator_ai_summary_task_request,
                request.state.operator_session.operator.operator_id,
                location_id,
                task_key=payload.task_key,
                summary_type=payload.summary_type,
                request_id=str(payload.request_id),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified AI-summary draft access is required"},
                headers=headers,
            )
        except AiSummaryTaskRequestInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            code = getattr(exc, "pgcode", None)
            if code == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current location AI-summary draft grant is required"},
                    headers=headers,
                )
            if code == "22023":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The retry ID was reused with different task intent"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_task_request").warning(
                "AI summary task request unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "AI summary task request unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            receipt = AiSummaryTaskReceipt.model_validate(result)
            if (
                receipt.request_id != payload.request_id
                or receipt.location_id != UUID(location_id)
                or receipt.task_key != payload.task_key
                or receipt.summary_type != payload.summary_type
            ):
                raise ValueError("task receipt does not match the request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.ai_summary_task_request").warning(
                "AI summary task receipt rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "AI summary task request unavailable"},
                headers=headers,
            )
        status_code = 200 if receipt.replayed else 201
        return JSONResponse(
            jsonable_encoder(receipt.model_dump(mode="python")),
            status_code=status_code,
            headers=headers,
        )
