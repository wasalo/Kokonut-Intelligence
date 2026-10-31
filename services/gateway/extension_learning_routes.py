"""OIDC routes for private extension-learning reads and scoped mutations."""

import json
from datetime import datetime
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


def _extension_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError("UUID value is invalid") from exc
    raise ValueError("UUID value is invalid")


_ExtensionUUID = Annotated[UUID, BeforeValidator(_extension_uuid)]


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("JSON object contains a duplicate key")
        value[key] = item
    return value

_ModuleCategory = Literal[
    "soil_health", "water_management", "pest_control", "post_harvest",
    "financial_literacy", "agroforestry", "climate_adaptation",
    "organic_practices", "record_keeping", "cooperative_management", "other",
]
_Difficulty = Literal["beginner", "intermediate", "advanced"]
_ContentType = Literal["video", "guide", "quiz", "interactive", "audio", "field_practice"]


class _ExtensionLearningModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ExtensionPeerNetworkCreateRequest(_ExtensionLearningModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _ExtensionUUID
    network_name: str = Field(min_length=1, max_length=255, strict=True)
    network_type: Literal[
        "learning_group", "mentorship", "community_of_practice",
        "farmer_field_school", "cooperative", "other",
    ]
    description: str | None = Field(default=None, max_length=10000, strict=True)
    max_members: int | None = Field(
        default=None, ge=1, le=2_147_483_647, strict=True
    )
    meeting_cadence: str | None = Field(default=None, max_length=100, strict=True)
    language: str = Field(default="en", min_length=1, max_length=50, strict=True)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("network_name", "language")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("value must not be blank or contain null characters")
        return value

    @field_validator("description", "meeting_cadence")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "\x00" in value:
            raise ValueError("value cannot contain null characters")
        return value.strip() or None

    @model_validator(mode="after")
    def validate_metadata_size(self):
        try:
            encoded = json.dumps(
                self.metadata, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("metadata must contain JSON values") from exc
        if len(encoded) > 8 * 1024:
            raise ValueError("metadata exceeds 8 KiB")
        return self


class ExtensionPeerNetworkCreateResponse(_ExtensionLearningModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    peer_network_id: _ExtensionUUID
    location_id: _ExtensionUUID
    network_name: str = Field(min_length=1, max_length=255, strict=True)
    network_type: Literal[
        "learning_group", "mentorship", "community_of_practice",
        "farmer_field_school", "cooperative", "other",
    ]
    status: Literal["active"]
    created_at: AwareDatetime
    request_id: _ExtensionUUID
    created: bool

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("created_at must be an ISO timestamp") from exc
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("created_at must include a timezone")
        return value


class ExtensionLearningProgressUpdateRequest(_ExtensionLearningModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    request_id: _ExtensionUUID
    status: Literal[
        "not_started", "in_progress", "completed", "failed", "expired",
    ] | None = None
    score: float | None = Field(default=None, ge=0, le=100, strict=True)
    progress_pct: float | None = Field(default=None, ge=0, le=100, strict=True)
    time_spent_min_delta: int | None = Field(default=None, ge=1, le=1440, strict=True)
    metadata_patch: dict[str, object] | None = None

    @model_validator(mode="after")
    def require_update(self):
        fields = self.model_fields_set - {"request_id"}
        if not fields or all(
            getattr(self, field) is None
            or (field == "metadata_patch" and not getattr(self, field))
            for field in fields
        ):
            raise ValueError("at least one progress field must be supplied")
        return self

    @field_validator("metadata_patch")
    @classmethod
    def validate_metadata_patch(cls, value):
        if value is None:
            return None
        try:
            encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("metadata_patch must contain JSON values") from exc
        if len(encoded.encode("utf-8")) > 8 * 1024:
            raise ValueError("metadata_patch exceeds 8 KiB")
        return value


class ExtensionLearningProgressUpdateResponse(_ExtensionLearningModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    progress_id: _ExtensionUUID
    location_id: _ExtensionUUID
    module_id: _ExtensionUUID
    progress_pct: float = Field(ge=0, le=100, strict=True)
    score: float | None = Field(default=None, ge=0, le=100, strict=True)
    time_spent_min: int = Field(ge=0, strict=True)
    status: Literal[
        "not_started", "in_progress", "completed", "failed", "expired",
    ]
    completed_at: AwareDatetime | None
    updated_at: AwareDatetime
    request_id: _ExtensionUUID

    @field_validator("progress_pct", "score", mode="before")
    @classmethod
    def parse_numeric_values(cls, value):
        if isinstance(value, Decimal):
            return float(value)
        return value

    @field_validator("completed_at", "updated_at", mode="before")
    @classmethod
    def parse_timestamps(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("progress timestamp must be ISO formatted") from exc
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("progress timestamp must include a timezone")
        return value


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
    from services.gateway.extension_learning_writes import (
        ExtensionLearningWriteConflict,
        ExtensionLearningWriteInvalid,
        create_location_extension_peer_network,
        update_location_extension_learning_progress,
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

    @router.post(
        "/operator/api/extension-learning/{location_id}/peer-networks",
        response_model=ExtensionPeerNetworkCreateResponse,
        responses={
            201: {
                "model": ExtensionPeerNetworkCreateResponse,
                "description": "A location-bound extension peer network was created.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            200: {
                "model": ExtensionPeerNetworkCreateResponse,
                "description": "An idempotent retry returned the original network receipt.",
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            400: {"description": "The request is invalid."},
            403: {"description": "The operator lacks the exact location grant."},
            404: {"description": "Operator OIDC is disabled."},
            409: {"description": "The request conflicts with an existing receipt."},
            413: {"description": "The request body exceeds 16 KiB."},
            500: {"description": "The network receipt failed response validation."},
            503: {"description": "The peer-network operation is unavailable."},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": ExtensionPeerNetworkCreateRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def create_extension_peer_network(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            requested_location_id = UUID(location_id)
        except (TypeError, ValueError, AttributeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Location identifier is invalid"},
                headers=headers,
            )

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 16 * 1024:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Extension peer-network request exceeds 16 KiB"},
                    headers=headers,
                )
            body.extend(chunk)
        try:
            payload = json.loads(body, object_pairs_hook=_unique_json_object)
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            create_request = ExtensionPeerNetworkCreateRequest.model_validate(payload)
        except (ValueError, RecursionError, ValidationError):
            return JSONResponse(
                status_code=400,
                content={"error": "Extension peer-network request is invalid"},
                headers=headers,
            )

        try:
            result = await run_in_threadpool(
                create_location_extension_peer_network,
                request.state.operator_session.operator.operator_id,
                str(requested_location_id),
                str(create_request.request_id),
                network_name=create_request.network_name,
                network_type=create_request.network_type,
                description=create_request.description,
                max_members=create_request.max_members,
                meeting_cadence=create_request.meeting_cadence,
                language=create_request.language,
                metadata=create_request.metadata,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified extension-learning access is required"},
                headers=headers,
            )
        except ExtensionLearningWriteInvalid:
            return JSONResponse(
                status_code=400,
                content={"error": "Extension peer-network request is invalid"},
                headers=headers,
            )
        except ExtensionLearningWriteConflict:
            return JSONResponse(
                status_code=409,
                content={"error": "Extension peer-network request conflicts with existing state"},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension peer-network operation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Extension peer-network operation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        try:
            validated = ExtensionPeerNetworkCreateResponse.model_validate(result)
            if (
                validated.location_id != requested_location_id
                or validated.request_id != create_request.request_id
                or validated.network_name != create_request.network_name
                or validated.network_type != create_request.network_type
            ):
                raise ValueError("Peer-network receipt does not match request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension peer-network response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Extension peer-network operation unavailable"},
                headers=headers,
            )
        return JSONResponse(
            status_code=201 if validated.created else 200,
            content=jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )

    @router.patch(
        "/operator/api/extension-learning/{location_id}/progress/{progress_id}",
        response_model=ExtensionLearningProgressUpdateResponse,
        responses={
            200: {
                "model": ExtensionLearningProgressUpdateResponse,
                "description": (
                    "The location-bound progress record was updated or an idempotent "
                    "retry returned its original receipt. Participant identity is omitted."
                ),
                "headers": {
                    "Cache-Control": {"schema": {"type": "string", "example": "no-store"}},
                    "Vary": {"schema": {"type": "string", "example": "Cookie"}},
                },
            },
            400: {"description": "The request is invalid."},
            403: {"description": "The operator lacks the exact location grant."},
            404: {"description": "Operator OIDC is disabled or progress is unavailable."},
            409: {"description": "The request conflicts with an existing receipt."},
            413: {"description": "The request body exceeds 16 KiB."},
            500: {"description": "The progress receipt failed response validation."},
            503: {"description": "The progress operation is unavailable."},
        },
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": ExtensionLearningProgressUpdateRequest.model_json_schema()
                    }
                },
            }
        },
    )
    async def update_extension_learning_progress_route(
        request: Request, location_id: str, progress_id: str
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            requested_location_id = UUID(location_id)
            requested_progress_id = UUID(progress_id)
        except (TypeError, ValueError, AttributeError):
            return JSONResponse(
                status_code=400,
                content={"error": "Progress or location identifier is invalid"},
                headers=headers,
            )

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 16 * 1024:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Extension progress request exceeds 16 KiB"},
                    headers=headers,
                )
            body.extend(chunk)
        try:
            payload = json.loads(body, object_pairs_hook=_unique_json_object)
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            update_request = ExtensionLearningProgressUpdateRequest.model_validate(payload)
        except (ValueError, RecursionError, ValidationError):
            return JSONResponse(
                status_code=400,
                content={"error": "Extension progress request is invalid"},
                headers=headers,
            )

        try:
            result = await run_in_threadpool(
                update_location_extension_learning_progress,
                request.state.operator_session.operator.operator_id,
                str(requested_location_id),
                str(requested_progress_id),
                str(update_request.request_id),
                status=update_request.status,
                score=update_request.score,
                progress_pct=update_request.progress_pct,
                time_spent_min_delta=update_request.time_spent_min_delta,
                metadata_patch=update_request.metadata_patch,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified extension-learning access is required"},
                headers=headers,
            )
        except ExtensionLearningWriteInvalid:
            return JSONResponse(
                status_code=400,
                content={"error": "Extension progress request is invalid"},
                headers=headers,
            )
        except ExtensionLearningWriteConflict:
            return JSONResponse(
                status_code=409,
                content={"error": "Extension progress request conflicts with existing state"},
                headers=headers,
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension progress operation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Extension progress operation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )

        try:
            validated = ExtensionLearningProgressUpdateResponse.model_validate(result)
            if (
                validated.location_id != requested_location_id
                or validated.progress_id != requested_progress_id
                or validated.request_id != update_request.request_id
            ):
                raise ValueError("Extension progress receipt does not match request")
        except (ValidationError, TypeError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.extension_learning").warning(
                "Extension progress response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Extension progress operation unavailable"},
                headers=headers,
            )
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder(validated.model_dump(mode="json")),
            headers=headers,
        )
