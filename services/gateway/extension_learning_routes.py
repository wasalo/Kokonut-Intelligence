"""OIDC routes for private extension-learning aggregates."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_ModuleCategory = Literal[
    "soil_health", "water_management", "pest_control", "post_harvest",
    "financial_literacy", "agroforestry", "climate_adaptation",
    "organic_practices", "record_keeping", "cooperative_management", "other",
]
_Difficulty = Literal["beginner", "intermediate", "advanced"]
_ContentType = Literal["video", "guide", "quiz", "interactive", "audio", "field_practice"]


class _ExtensionLearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ExtensionModuleItem(_ExtensionLearningModel):
    id: UUID
    module_name: str
    category: _ModuleCategory
    difficulty: _Difficulty | None
    content_type: _ContentType
    duration_minutes: int | None = Field(default=None, strict=True)
    language: str | None


class ExtensionModulePage(_ExtensionLearningModel):
    location_id: UUID
    items: list[ExtensionModuleItem] = Field(max_length=50)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)


class LearningProgressGroup(_ExtensionLearningModel):
    module_category: _ModuleCategory
    progress_status: Literal[
        "not_started", "in_progress", "completed", "failed", "expired",
    ]
    enrollment_count: int = Field(ge=0, strict=True)


class ContentDeliveryGroup(_ExtensionLearningModel):
    delivery_channel: Literal[
        "sms", "whatsapp", "mobile_app", "video_link", "audio_broadcast",
        "community_screening", "print", "in_person",
    ]
    delivery_status: Literal["pending", "sent", "delivered", "viewed", "clicked", "failed"]
    delivery_count: int = Field(ge=0, strict=True)


class SkillAssessmentGroup(_ExtensionLearningModel):
    assessment_type: Literal[
        "pre_test", "post_test", "diagnostic", "self_assessment", "field_observation",
    ]
    assessment_count: int = Field(ge=0, strict=True)
    scored_assessment_count: int = Field(ge=0, strict=True)


class PeerNetworkGroup(_ExtensionLearningModel):
    network_type: Literal[
        "learning_group", "mentorship", "community_of_practice",
        "farmer_field_school", "cooperative", "other",
    ]
    network_status: Literal["active", "inactive", "archived"]
    network_count: int = Field(ge=0, strict=True)
    active_member_count: int = Field(ge=0, strict=True)


class ExtensionLearningSummary(_ExtensionLearningModel):
    location_id: UUID
    learning_progress: list[LearningProgressGroup] = Field(max_length=55)
    content_delivery: list[ContentDeliveryGroup] = Field(max_length=48)
    assessments: list[SkillAssessmentGroup] = Field(max_length=5)
    peer_networks: list[PeerNetworkGroup] = Field(max_length=18)


def register_extension_learning_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.extension_learning_reads import (
        MAX_OFFSET,
        get_location_extension_learning_summary,
        list_location_extension_modules,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    @router.get(
        "/operator/api/extension-learning/{location_id}/modules",
        response_model=ExtensionModulePage,
    )
    async def extension_learning_modules(
        request: Request,
        location_id: str,
        category: str | None = None,
        difficulty: str | None = None,
        content_type: str | None = None,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=MAX_OFFSET),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_extension_modules,
                request.state.operator_session.operator.operator_id,
                location_id,
                category=category,
                difficulty=difficulty,
                content_type=content_type,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified extension-learning access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension module catalog unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Extension module catalog unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = ExtensionModulePage.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.limit != limit
                or validated.offset != offset
                or len(validated.items) > limit
                or (
                    validated.has_more
                    and (len(validated.items) != limit or offset + limit > MAX_OFFSET)
                )
            ):
                raise ValueError("Extension catalog page does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension module response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Extension module catalog unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/extension-learning/{location_id}/summary",
        response_model=ExtensionLearningSummary,
    )
    async def extension_learning_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_extension_learning_summary,
                request.state.operator_session.operator.operator_id,
                location_id,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified extension-learning access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension-learning summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Extension-learning summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = ExtensionLearningSummary.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Extension summary location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension-learning response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Extension-learning summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )
