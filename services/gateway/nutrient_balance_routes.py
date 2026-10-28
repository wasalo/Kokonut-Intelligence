"""OIDC route registration for location-scoped nutrient reads."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError


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


def register_nutrient_balance_routes(router, provider, run_in_threadpool, psycopg2):
    from typing import Literal

    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.nutrient_balances import get_location_nutrient_balances
    from services.gateway.nutrient_events import get_location_nutrient_events
    from services.gateway.nutrient_soil_tests import get_location_soil_tests

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

    @router.get("/operator/api/nutrients/{location_id}/soil-tests")
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
        return JSONResponse(
            jsonable_encoder(result),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )

    @router.get("/operator/api/nutrients/{location_id}/events/{event_type}")
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
        return JSONResponse(
            jsonable_encoder(result),
            headers={"Cache-Control": "no-store", "Vary": "Cookie"},
        )
