"""OIDC route registration for location-scoped nutrient reads."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class _NutrientBalanceResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class NutrientQuantitiesResponse(_NutrientBalanceResponseModel):
    input_kg: float | None
    removal_kg: float | None
    surplus_kg: float | None


class NutrientBalanceGroupResponse(_NutrientBalanceResponseModel):
    season: str = Field(max_length=100)
    crop_name: str | None = Field(max_length=100)
    budget_count: int = Field(ge=1, strict=True)
    area_ha: float | None
    nitrogen: NutrientQuantitiesResponse
    phosphorus: NutrientQuantitiesResponse
    potassium: NutrientQuantitiesResponse


class NutrientBalancesResponse(_NutrientBalanceResponseModel):
    location_id: UUID
    total_summaries: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)
    balances: list[NutrientBalanceGroupResponse] = Field(max_length=50)


class _NutrientPageResponse(_NutrientBalanceResponseModel):
    location_id: UUID
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)

    def validate_page(self, total: int, page_length: int):
        if page_length > self.limit or self.offset + page_length > total:
            raise ValueError("page is inconsistent with its total")
        expected_has_more = (
            total > self.offset + page_length
            and self.offset + self.limit <= 10_000
        )
        if self.has_more != expected_has_more:
            raise ValueError("has_more is inconsistent with the returned page")
        return self


class SoilTestMeasurements(_NutrientBalanceResponseModel):
    soil_ph: float | None = Field(strict=True)
    organic_matter_pct: float | None = Field(strict=True)
    nitrogen_ppm: float | None = Field(strict=True)
    phosphorus_ppm: float | None = Field(strict=True)
    potassium_ppm: float | None = Field(strict=True)
    cec: float | None = Field(strict=True)


class SoilTestRecommendations(_NutrientBalanceResponseModel):
    nitrogen: float | None = Field(strict=True)
    phosphorus: float | None = Field(strict=True)
    potassium: float | None = Field(strict=True)


class SoilTestResponse(_NutrientBalanceResponseModel):
    test_id: UUID
    plot_id: UUID | None
    test_date: date
    status: Literal["recorded", "verified"]
    measurements: SoilTestMeasurements
    recommendations_kg_ha: SoilTestRecommendations


class SoilTestsResponse(_NutrientPageResponse):
    total_tests: int = Field(ge=0, strict=True)
    soil_tests: list[SoilTestResponse] = Field(max_length=50)

    @model_validator(mode="after")
    def validate_soil_tests_page(self):
        return self.validate_page(self.total_tests, len(self.soil_tests))


class NutrientQuantities(_NutrientBalanceResponseModel):
    nitrogen: float | None = Field(strict=True)
    phosphorus: float | None = Field(strict=True)
    potassium: float | None = Field(strict=True)


class NutrientCost(_NutrientBalanceResponseModel):
    amount: float = Field(strict=True)
    currency_code: str = Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$")


class _NutrientEventResponse(_NutrientBalanceResponseModel):
    event_id: UUID
    plot_id: UUID | None
    season: str = Field(max_length=100)
    budget_crop_name: str | None = Field(max_length=100)
    budget_status: Literal["draft", "submitted", "verified", "published", "rejected"]
    event_status: Literal["recorded", "verified"]
    nutrients_kg: NutrientQuantities


class NutrientInputEventResponse(_NutrientEventResponse):
    input_date: date
    input_type: Literal[
        "fertilizer", "manure", "compost", "biochar", "green_manure",
        "rainfall", "irrigation", "seed", "other",
    ]
    product_name: str | None = Field(max_length=200)
    application_rate: float | None = Field(strict=True)
    rate_unit: str | None = Field(max_length=50)
    cost: NutrientCost | None
    cost_status: Literal["not_recorded", "currency_unclassified", "classified"]

    @model_validator(mode="after")
    def validate_cost_status(self):
        if (self.cost_status == "classified") != (self.cost is not None):
            raise ValueError("cost does not match its classification")
        return self


class NutrientRemovalEventResponse(_NutrientEventResponse):
    harvest_date: date
    crop_name: str | None = Field(max_length=100)
    yield_amount: float | None = Field(strict=True)
    yield_unit: str | None = Field(max_length=50)


class NutrientEventsResponse(_NutrientPageResponse):
    event_type: Literal["inputs", "removals"]
    events: list[NutrientInputEventResponse | NutrientRemovalEventResponse] = Field(max_length=50)
    total_events: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_events_page(self):
        self.validate_page(self.total_events, len(self.events))
        expected_event = (
            NutrientInputEventResponse
            if self.event_type == "inputs"
            else NutrientRemovalEventResponse
        )
        if any(not isinstance(event, expected_event) for event in self.events):
            raise ValueError("event items do not match the requested event type")
        return self


def register_nutrient_balance_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.nutrient_balances import get_location_nutrient_balances
    from services.gateway.nutrient_events import get_location_nutrient_events
    from services.gateway.nutrient_soil_tests import get_location_soil_tests

    def contracted_response(model, result, *, expected, failure, logger_name):
        try:
            validated = model.model_validate(result)
            if any(getattr(validated, key) != value for key, value in expected.items()):
                raise ValueError("response does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger(logger_name).warning(
                "Nutrient response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": failure},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/nutrients/{location_id}/balances",
        response_model=NutrientBalancesResponse,
    )
    async def nutrient_balances(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_nutrient_balances,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.nutrient_balances").warning(
                "Nutrient balances unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Nutrient balances unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        try:
            validated = NutrientBalancesResponse.model_validate(result)
            if (
                validated.location_id != UUID(location_id)
                or validated.limit != limit
                or validated.offset != offset
                or len(validated.balances) > limit
                or offset + len(validated.balances) > validated.total_summaries
                or validated.has_more
                != (
                    validated.total_summaries > offset + len(validated.balances)
                    and offset + limit <= 10_000
                )
            ):
                raise ValueError("Nutrient balance scope does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.nutrient_balances").warning(
                "Nutrient balances response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": "Nutrient balances unavailable"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get(
        "/operator/api/nutrients/{location_id}/soil-tests",
        response_model=SoilTestsResponse,
    )
    async def nutrient_soil_tests(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_soil_tests,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.nutrient_soil_tests").warning(
                "Nutrient soil tests unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Nutrient soil tests unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        return contracted_response(
            SoilTestsResponse,
            result,
            expected={
                "location_id": UUID(location_id),
                "limit": limit,
                "offset": offset,
            },
            failure="Nutrient soil tests unavailable",
            logger_name="gateway.nutrient_soil_tests",
        )

    @router.get(
        "/operator/api/nutrients/{location_id}/events/{event_type}",
        response_model=NutrientEventsResponse,
    )
    async def nutrient_events(
        request: Request,
        location_id: str,
        event_type: Literal["inputs", "removals"],
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        try:
            result = await run_in_threadpool(
                get_location_nutrient_events,
                request.state.operator_session.operator.operator_id,
                location_id,
                event_type,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified operator access is required"},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
                headers={"Cache-Control": "no-store", "Vary": "Cookie"},
            )
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.nutrient_events").warning(
                "Nutrient events unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Nutrient events unavailable"},
                headers={
                    "Retry-After": "30",
                    "Cache-Control": "no-store",
                    "Vary": "Cookie",
                },
            )
        return contracted_response(
            NutrientEventsResponse,
            result,
            expected={
                "location_id": UUID(location_id),
                "event_type": event_type,
                "limit": limit,
                "offset": offset,
            },
            failure="Nutrient events unavailable",
            logger_name="gateway.nutrient_events",
        )
