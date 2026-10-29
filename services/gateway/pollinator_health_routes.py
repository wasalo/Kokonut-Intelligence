"""OIDC route registration for location-scoped pollinator reads and capture."""

import json
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    ValidationError,
    model_validator,
)

_PollinatorType = Literal[
    "honeybee", "wild_bee", "butterfly", "moth", "beetle", "fly", "bird", "bat", "other"
]
_ObservationMethod = Literal["transect", "pan_trap", "visual_count", "hive_weight", "other"]
_ObservationStatus = Literal["verified", "reviewed"]


class _PollinatorResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PollinatorObservationCaptureResponse(_PollinatorResponseModel):
    observation_id: UUID
    location_id: UUID
    pollinator_type: _PollinatorType
    count: int = Field(ge=0, strict=True)
    observation_method: _ObservationMethod
    observation_date: date
    duration_minutes: int = Field(ge=0, strict=True)
    status: Literal["recorded"]
    replayed: bool = Field(strict=True)


class PollinatorObservationAggregate(_PollinatorResponseModel):
    pollinator_type: _PollinatorType
    observation_method: _ObservationMethod | None
    status: _ObservationStatus
    record_count: int = Field(ge=1, strict=True)
    total_observed: float | None
    mean_duration_minutes: float | None
    first_observation_date: date | None
    last_observation_date: date | None


class PollinatorObservationTrend(_PollinatorResponseModel):
    pollinator_type: _PollinatorType
    observation_count: int = Field(ge=1, strict=True)
    avg_count: float | None
    max_count: int | None
    first_observation_date: date | None
    last_observation_date: date | None
    total_count: float | None
    trend: Literal["increasing", "decreasing", "stable", "insufficient_data"]
    change_pct: float


class PollinatorHabitatAggregate(_PollinatorResponseModel):
    habitat_type: Literal[
        "wildflower_strip", "hedgerow", "nesting_site", "water_source",
        "cover_crop", "native_planting", "other",
    ]
    condition: Literal["excellent", "good", "fair", "poor"] | None
    status: Literal["active", "inactive", "degraded", "removed"]
    record_count: int = Field(ge=1, strict=True)
    total_area_m2: float | None


class VerifiedPesticideImpactAggregate(_PollinatorResponseModel):
    toxicity_class: Literal["low", "moderate", "high", "very_high"] | None
    pollinator_mortality_observed: bool
    record_count: int = Field(ge=1, strict=True)
    mean_mortality_pct: float | None
    first_application_date: date | None
    last_application_date: date | None


class PesticideRiskDistribution(_PollinatorResponseModel):
    low: int = Field(ge=0, strict=True)
    moderate: int = Field(ge=0, strict=True)
    high: int = Field(ge=0, strict=True)
    very_high: int = Field(ge=0, strict=True)
    unknown: int = Field(ge=0, strict=True)


class PesticideRiskSummary(_PollinatorResponseModel):
    period_days: Literal[90]
    total_applications: int = Field(ge=0, strict=True)
    overall_risk: Literal["low", "elevated", "critical"]
    risk_distribution: PesticideRiskDistribution
    mortality_events: int = Field(ge=0, strict=True)


class ActiveHiveAggregate(_PollinatorResponseModel):
    colony_strength: Literal["strong", "moderate", "weak", "dead"] | None
    queen_status: Literal["present", "absent", "replaced", "unknown"] | None
    hive_count: int = Field(ge=1, strict=True)
    total_honey_yield_kg: float | None
    mean_varroa_count: float | None
    last_inspection_date: date | None


class ActiveHiveSummary(_PollinatorResponseModel):
    total_hives: int = Field(ge=0, strict=True)
    avg_colony_strength_score: float | None


class PollinatorHealthSummaryResponse(_PollinatorResponseModel):
    location_id: UUID
    verified_observations: list[PollinatorObservationAggregate] = Field(max_length=108)
    observation_trends: list[PollinatorObservationTrend] = Field(max_length=9)
    habitat_inventory: list[PollinatorHabitatAggregate] = Field(max_length=140)
    verified_pesticide_impacts: list[VerifiedPesticideImpactAggregate] = Field(max_length=10)
    pesticide_risk_summary: PesticideRiskSummary
    active_hives: list[ActiveHiveAggregate] = Field(max_length=25)
    active_hive_summary: ActiveHiveSummary


class PollinatorHabitatDetail(_PollinatorResponseModel):
    id: UUID
    habitat_name: str = Field(min_length=1, max_length=200)
    habitat_type: Literal[
        "wildflower_strip", "hedgerow", "nesting_site", "water_source",
        "cover_crop", "native_planting", "other",
    ]
    area_m2: float | None = Field(strict=True)
    condition: Literal["excellent", "good", "fair", "poor"] | None
    status: Literal["active", "inactive", "degraded", "removed"]
    last_maintenance: date | None
    updated_at: AwareDatetime


class PollinatorHiveDetail(_PollinatorResponseModel):
    id: UUID
    hive_id: str = Field(min_length=1, max_length=100)
    hive_type: str | None = Field(default=None, max_length=50)
    status: Literal["active", "inactive", "decommissioned"]
    colony_strength: Literal["strong", "moderate", "weak", "dead"] | None
    colony_strength_score: int | None = Field(default=None, ge=0, le=10, strict=True)
    queen_status: Literal["present", "absent", "replaced", "unknown"] | None
    frame_count: int | None = Field(default=None, ge=0, strict=True)
    inspection_date: date | None
    last_maintenance_date: date | None
    updated_at: AwareDatetime


class _PollinatorPage(_PollinatorResponseModel):
    location_id: UUID
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)
    next_offset: int | None = Field(default=None, ge=0, le=10_000, strict=True)

    def validate_page(self, page_length: int):
        if page_length > self.limit:
            raise ValueError("page contains more items than its limit")
        if self.has_more and page_length != self.limit:
            raise ValueError("has_more requires a full page")
        expected_next = self.offset + self.limit if self.has_more else None
        if self.next_offset != expected_next:
            raise ValueError("next_offset is inconsistent with the returned page")
        if self.has_more and (self.next_offset is None or self.next_offset > 10_000):
            raise ValueError("next_offset exceeds the supported offset boundary")
        return self


class PollinatorHabitatDetailPage(_PollinatorPage):
    habitats: list[PollinatorHabitatDetail] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_habitats_page(self):
        return self.validate_page(len(self.habitats))


class PollinatorHiveDetailPage(_PollinatorPage):
    hives: list[PollinatorHiveDetail] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_hives_page(self):
        return self.validate_page(len(self.hives))


_ReviewNumber = StrictInt | StrictFloat | None


class PollinatorObservationReviewDetails(_PollinatorResponseModel):
    pollinator_type: _PollinatorType | None
    count: int | None = Field(ge=0, strict=True)
    method: _ObservationMethod | None
    duration_minutes: int | None = Field(ge=0, strict=True)
    species_name: str | None = Field(max_length=200)
    notes: str | None = Field(max_length=2000)


class PollinatorPesticideReviewDetails(_PollinatorResponseModel):
    product_name: str | None = Field(max_length=200)
    active_ingredient: str | None = Field(max_length=200)
    toxicity_class: Literal["low", "moderate", "high", "very_high"] | None
    application_rate: _ReviewNumber
    rate_unit: str | None = Field(max_length=100)
    area_treated_m2: _ReviewNumber
    bloom_stage_at_application: str | None = Field(max_length=100)
    pollinator_distance_m: _ReviewNumber
    pollinator_safe_period_days: int | None = Field(ge=0, strict=True)
    mortality_observed: bool | None
    mortality_pct: _ReviewNumber
    notes: str | None = Field(max_length=2000)


class PollinatorHiveInspectionReviewDetails(_PollinatorResponseModel):
    hive_id: str = Field(min_length=1, max_length=100)
    colony_strength: Literal["strong", "moderate", "weak", "dead"] | None
    colony_strength_score: int | None = Field(ge=0, le=10, strict=True)
    queen_status: Literal["present", "absent", "replaced", "unknown"] | None
    queen_seen: bool | None
    varroa_count: int | None = Field(ge=0, strict=True)
    brood_pattern: str | None = Field(max_length=500)
    honey_stores: str | None = Field(max_length=500)
    disease_signs: str | None = Field(max_length=500)
    temperament: str | None = Field(max_length=200)
    population_estimate: int | None = Field(ge=0, strict=True)
    swarm_cells: bool | None
    notes: str | None = Field(max_length=2000)


class PollinatorObservationReviewItem(_PollinatorResponseModel):
    record_id: UUID
    record_type: Literal["observation"]
    occurred_on: date
    status: Literal["recorded"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    details: PollinatorObservationReviewDetails


class PollinatorPesticideReviewItem(_PollinatorResponseModel):
    record_id: UUID
    record_type: Literal["pesticide_impact"]
    occurred_on: date
    status: Literal["recorded"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    details: PollinatorPesticideReviewDetails


class PollinatorHiveInspectionReviewItem(_PollinatorResponseModel):
    record_id: UUID
    record_type: Literal["hive_inspection"]
    occurred_on: date
    status: Literal["recorded"]
    created_at: AwareDatetime
    updated_at: AwareDatetime
    details: PollinatorHiveInspectionReviewDetails


PollinatorReviewItem = Annotated[
    PollinatorObservationReviewItem
    | PollinatorPesticideReviewItem
    | PollinatorHiveInspectionReviewItem,
    Field(discriminator="record_type"),
]


class PollinatorReviewQueuePage(_PollinatorPage):
    items: list[PollinatorReviewItem] = Field(max_length=50)
    total: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_review_page(self):
        self.validate_page(len(self.items))
        if self.has_more and self.offset + len(self.items) >= self.total:
            raise ValueError("has_more exceeds the available review rows")
        return self


def register_pollinator_health_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.pollinator_health_reads import (
        get_location_pollinator_habitat_details,
        get_location_pollinator_hive_details,
        get_location_pollinator_summary,
        list_location_pollinator_review_queue,
    )
    from services.gateway.pollinator_health_writes import (
        PollinatorObservationInvalid,
        create_location_pesticide_impact,
        create_location_pollinator_habitat,
        create_location_pollinator_hive,
        create_location_pollinator_observation,
        record_location_pollinator_hive_inspection,
        review_location_pollinator_record,
        update_location_pollinator_habitat,
        update_location_pollinator_hive,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def _validated_private_response(
        model, result, error_message, expected, *, created_replay=False
    ):
        try:
            validated = model.model_validate(result)
            if any(getattr(validated, name) != value for name, value in expected.items()):
                raise ValueError("response does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500, content={"error": error_message}, headers=headers
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json", exclude_unset=True)),
            status_code=(200 if validated.replayed else 201) if created_replay else 200,
            headers=headers,
        )

    async def bounded_payload(request: Request, *, max_bytes: int = 12 * 1024):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_bytes:
                    return None, JSONResponse(
                        status_code=413,
                        content={"error": "Pollinator request body exceeds 12 KB"},
                        headers=headers,
                    )
            except ValueError:
                return None, JSONResponse(
                    status_code=400,
                    content={"error": "Invalid content length"},
                    headers=headers,
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > max_bytes:
                return None, JSONResponse(
                    status_code=413,
                    content={"error": "Pollinator request body exceeds 12 KB"},
                    headers=headers,
                )
        try:
            payload = json.loads(body)
        except (ValueError, RecursionError):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Pollinator request body must be valid JSON"},
                headers=headers,
            )
        if not isinstance(payload, dict):
            return None, JSONResponse(
                status_code=400,
                content={"error": "Pollinator request body must be an object"},
                headers=headers,
            )
        return payload, None

    @router.get(
        "/operator/api/pollinators/{location_id}/summary",
        response_model=PollinatorHealthSummaryResponse,
    )
    async def pollinator_summary(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_pollinator_summary,
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
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator summary unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator summary unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        try:
            validated = PollinatorHealthSummaryResponse.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("Pollinator summary location does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator summary response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Pollinator summary unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/pollinators/{location_id}/review-queue",
        response_model=PollinatorReviewQueuePage,
    )
    async def pollinator_review_queue(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                list_location_pollinator_review_queue,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pollinator review access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-review grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator review queue unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator review queue unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return _validated_private_response(
            PollinatorReviewQueuePage,
            result,
            "Pollinator review queue unavailable",
            {"location_id": UUID(location_id), "limit": limit, "offset": offset},
        )

    async def _review_pollinator_record(
        request: Request, location_id: str, record_type: str, record_id: str
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        normalized_type = {
            "observations": "observation",
            "pesticide-impacts": "pesticide_impact",
            "hives/inspections": "hive_inspection",
        }.get(record_type)
        if normalized_type is None:
            return JSONResponse(status_code=404, content={"error": "Pollinator item not found"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                review_location_pollinator_record,
                request.state.operator_session.operator.operator_id,
                location_id,
                normalized_type,
                record_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pollinator review access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "Independent exact location pollinator review is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Pollinator review input is invalid"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The review request ID was already used with different input"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The pollinator item changed; reload the review queue"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Pollinator item not found in this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator review unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator review unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), headers=headers)

    @router.post(
        "/operator/api/pollinators/{location_id}/observations/{record_id}/review"
    )
    async def review_pollinator_observation(request: Request, location_id: str, record_id: str):
        return await _review_pollinator_record(request, location_id, "observations", record_id)

    @router.post(
        "/operator/api/pollinators/{location_id}/pesticide-impacts/{record_id}/review"
    )
    async def review_pesticide_impact(request: Request, location_id: str, record_id: str):
        return await _review_pollinator_record(request, location_id, "pesticide-impacts", record_id)

    @router.post(
        "/operator/api/pollinators/{location_id}/hives/inspections/{record_id}/review"
    )
    async def review_pollinator_hive_inspection(request: Request, location_id: str, record_id: str):
        return await _review_pollinator_record(request, location_id, "hives/inspections", record_id)

    @router.get(
        "/operator/api/pollinators/{location_id}/habitats",
        response_model=PollinatorHabitatDetailPage,
    )
    async def pollinator_habitat_details(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_pollinator_habitat_details,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat detail access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-detail grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator habitat details unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator habitat details unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return _validated_private_response(
            PollinatorHabitatDetailPage,
            result,
            "Pollinator habitat details unavailable",
            {"location_id": UUID(location_id), "limit": limit, "offset": offset},
        )

    @router.get(
        "/operator/api/pollinators/{location_id}/hives",
        response_model=PollinatorHiveDetailPage,
    )
    async def pollinator_hive_details(
        request: Request,
        location_id: str,
        limit: int = Query(default=50, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10000),
    ):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        try:
            result = await run_in_threadpool(
                get_location_pollinator_hive_details,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified managed-hive detail access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            if getattr(exc, "pgcode", None) == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-detail grant is required"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Managed-hive details unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Managed-hive details unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return _validated_private_response(
            PollinatorHiveDetailPage,
            result,
            "Managed-hive details unavailable",
            {"location_id": UUID(location_id), "limit": limit, "offset": offset},
        )

    @router.post(
        "/operator/api/pollinators/{location_id}/observations",
        response_model=PollinatorObservationCaptureResponse,
        status_code=201,
        responses={200: {"model": PollinatorObservationCaptureResponse}},
    )
    async def create_pollinator_observation(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_observation,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pollinator capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Pollinator observation input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        expected = {
            "location_id": UUID(location_id),
            "pollinator_type": payload.get("pollinator_type"),
            "count": payload.get("count"),
            "observation_method": payload.get("observation_method"),
            "duration_minutes": payload.get("duration_minutes"),
        }
        if payload.get("observation_date") is not None:
            expected["observation_date"] = date.fromisoformat(payload["observation_date"])
        return _validated_private_response(
            PollinatorObservationCaptureResponse,
            result,
            "Pollinator capture unavailable",
            expected,
            created_replay=True,
        )

    @router.post("/operator/api/pollinators/{location_id}/pesticide-impacts")
    async def create_pesticide_impact(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pesticide_impact,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified pesticide-report capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Pesticide report input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pesticide report capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pesticide report capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/habitats")
    async def create_pollinator_habitat(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_habitat,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Habitat report input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Habitat capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Habitat capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.patch("/operator/api/pollinators/{location_id}/habitats/{habitat_id}")
    async def update_pollinator_habitat(request: Request, location_id: str, habitat_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                update_location_pollinator_habitat,
                request.state.operator_session.operator.operator_id,
                location_id,
                habitat_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified habitat update access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-edit grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Habitat update input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different habitat input"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The habitat changed; reload it before applying this update"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Habitat not found in this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Pollinator habitat update unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Pollinator habitat update unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200,
            headers=headers,
        )

    @router.patch("/operator/api/pollinators/{location_id}/hives/{hive_record_id}")
    async def update_pollinator_hive(request: Request, location_id: str, hive_record_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                update_location_pollinator_hive,
                request.state.operator_session.operator.operator_id,
                location_id,
                hive_record_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified managed-hive update access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-edit grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Managed-hive update input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different hive input"},
                    headers=headers,
                )
            if pgcode == "40001":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The hive changed; reload it before applying this update"},
                    headers=headers,
                )
            if pgcode == "P0002":
                return JSONResponse(
                    status_code=404,
                    content={"error": "Managed hive not found in this location"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Managed-hive update unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Managed-hive update unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(jsonable_encoder(result), status_code=200, headers=headers)

    @router.post("/operator/api/pollinators/{location_id}/hives")
    async def create_pollinator_hive(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                create_location_pollinator_hive,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified hive capture access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Managed-hive input is invalid or outside its bounds"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The hive identifier exists or the request ID was reused with different input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Managed-hive capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Managed-hive capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )

    @router.post("/operator/api/pollinators/{location_id}/hives/inspections")
    async def record_pollinator_hive_inspection(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(status_code=404, content={"error": "Operator OIDC is disabled"}, headers=headers)
        payload, body_error = await bounded_payload(request)
        if body_error:
            return body_error
        try:
            result = await run_in_threadpool(
                record_location_pollinator_hive_inspection,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified hive inspection access is required"},
                headers=headers,
            )
        except PollinatorObservationInvalid as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            pgcode = getattr(exc, "pgcode", None)
            if pgcode == "42501":
                return JSONResponse(
                    status_code=403,
                    content={"error": "A current exact location pollinator-create grant is required"},
                    headers=headers,
                )
            if pgcode == "22023":
                return JSONResponse(
                    status_code=400,
                    content={"error": "Hive inspection input or location-scoped hive identifier is invalid"},
                    headers=headers,
                )
            if pgcode == "23505":
                return JSONResponse(
                    status_code=409,
                    content={"error": "The request ID was already used with different inspection input"},
                    headers=headers,
                )
            from services.common.logging import get_logger

            get_logger("gateway.pollinators").warning(
                "Hive inspection capture unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Hive inspection capture unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=200 if result["replayed"] else 201,
            headers=headers,
        )
