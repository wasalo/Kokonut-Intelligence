"""OIDC routes for saved, location-scoped trend-analysis outputs."""

import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError


class _TrendResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TrendEstimateResponse(_TrendResponseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    period_start: AwareDatetime
    period_end: AwareDatetime
    data_points: int = Field(ge=0, strict=True)
    slope: float | None
    intercept: float | None
    r_squared: float | None
    standard_error: float | None
    slope_p_value: float | None
    direction: Literal["improving", "stable", "declining", "insufficient_data"]
    confidence_level: Literal["high", "moderate", "low", "insufficient_data"]
    slope_ci_lower: float | None
    slope_ci_upper: float | None
    time_unit: str = Field(min_length=1, max_length=20)
    computed_at: AwareDatetime


class TrendEstimatesResponse(_TrendResponseModel):
    location_id: UUID
    items: list[TrendEstimateResponse] = Field(max_length=50)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)


class TrendSmoothingPointResponse(_TrendResponseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    smoothing_type: Literal[
        "moving_average", "weighted_moving_average", "exponential", "holt_linear"
    ]
    timestamp: AwareDatetime
    original_value: float | None
    smoothed_value: float | None
    computed_at: AwareDatetime


class TrendSmoothingResponse(_TrendResponseModel):
    location_id: UUID
    metric_key: str = Field(min_length=1, max_length=100)
    items: list[TrendSmoothingPointResponse] = Field(max_length=100)


class TrendChangePointResponse(_TrendResponseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    detection_method: Literal["cusum", "pelt", "binary_segmentation", "window_slider"]
    change_point_index: int = Field(ge=0, strict=True)
    change_point_timestamp: AwareDatetime | None
    magnitude: float | None
    direction: Literal["increase", "decrease", "variance_change"]
    confidence: float | None
    segment_count: int = Field(ge=0, strict=True)
    status: Literal["detected", "confirmed", "dismissed"]
    detected_at: AwareDatetime


class TrendChangePointsResponse(_TrendResponseModel):
    location_id: UUID
    metric_key: str = Field(min_length=1, max_length=100)
    items: list[TrendChangePointResponse] = Field(max_length=100)


class TrendDecompositionResponse(_TrendResponseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    decomposition_method: Literal["classical", "stl", "x11"]
    period: int = Field(gt=0, strict=True)
    trend_component: list[float | None] = Field(max_length=200)
    seasonal_component: list[float | None] = Field(max_length=200)
    residual_component: list[float | None] = Field(max_length=200)
    seasonal_strength: float | None
    trend_strength: float | None
    residual_variance: float | None
    data_points: int = Field(ge=0, strict=True)
    trend_component_points: int = Field(ge=0, strict=True)
    seasonal_component_points: int = Field(ge=0, strict=True)
    residual_component_points: int = Field(ge=0, strict=True)
    truncated: bool = Field(strict=True)
    computed_at: AwareDatetime


class TrendDecompositionResultResponse(_TrendResponseModel):
    location_id: UUID
    metric_key: str = Field(min_length=1, max_length=100)
    item: TrendDecompositionResponse | None


class TrendForecastIntervalResponse(_TrendResponseModel):
    step: int = Field(gt=0, strict=True)
    forecast: float | None
    lower: float | None
    upper: float | None


class TrendForecastResponse(_TrendResponseModel):
    metric_key: str = Field(min_length=1, max_length=100)
    model_type: Literal[
        "arima", "exponential_smoothing", "prophet", "naive", "seasonal_naive"
    ]
    forecast_values: list[float | None] = Field(max_length=100)
    intervals: list[TrendForecastIntervalResponse] = Field(max_length=100)
    interval_confidence: float | None
    forecast_horizon: int = Field(gt=0, strict=True)
    time_unit: str = Field(min_length=1, max_length=20)
    training_points: int = Field(ge=0, strict=True)
    status: Literal["active", "superseded", "expired"]
    truncated: bool = Field(strict=True)
    forecast_at: AwareDatetime


class TrendForecastResultResponse(_TrendResponseModel):
    location_id: UUID
    metric_key: str = Field(min_length=1, max_length=100)
    item: TrendForecastResponse | None


def register_trend_analysis_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.trend_analysis_reads import (
        get_location_seasonal_decomposition,
        get_location_time_series_forecast,
        list_location_change_points,
        list_location_trend_estimates,
        list_location_trend_smoothing,
    )
    from services.gateway.trend_forecast_compute import (
        create_location_time_series_forecast,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def success_response(
        result,
        response_model,
        *,
        resource_name,
        location_id,
        metric_key=None,
        limit=None,
        offset=None,
    ):
        try:
            validated = response_model.model_validate(result)
            if validated.location_id != UUID(location_id):
                raise ValueError("response location does not match request")
            if metric_key is not None and validated.metric_key != metric_key:
                raise ValueError("response metric does not match request")
            if limit is not None:
                if hasattr(validated, "limit") and validated.limit != limit:
                    raise ValueError("response page size does not match request")
                if len(validated.items) > limit:
                    raise ValueError("response page exceeds request limit")
            if offset is not None and validated.offset != offset:
                raise ValueError("response offset does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "%s projection rejected (%s)", resource_name, type(exc).__name__
            )
            return JSONResponse(
                status_code=500,
                content={"error": f"{resource_name} unavailable"},
                headers=headers,
            )
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/trends/{location_id}/estimates",
        response_model=TrendEstimatesResponse,
    )
    async def trend_estimates(
        request: Request,
        location_id: str,
        limit: int = Query(default=25, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=10_000),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_trend_estimates,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend estimates unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend estimates unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return success_response(
            result,
            TrendEstimatesResponse,
            resource_name="Trend estimates",
            location_id=location_id,
            limit=limit,
            offset=offset,
        )

    @router.get(
        "/operator/api/trends/{location_id}/change-points",
        response_model=TrendChangePointsResponse,
    )
    async def trend_change_points(
        request: Request,
        location_id: str,
        metric_key: str,
        limit: int = Query(default=100, ge=1, le=100),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_change_points,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
                limit=limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend change-point read unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend change-point read unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return success_response(
            result,
            TrendChangePointsResponse,
            resource_name="Trend change-point read",
            location_id=location_id,
            metric_key=metric_key,
            limit=limit,
        )

    @router.get(
        "/operator/api/trends/{location_id}/decomposition",
        response_model=TrendDecompositionResultResponse,
    )
    async def trend_decomposition(
        request: Request,
        location_id: str,
        metric_key: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_seasonal_decomposition,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend decomposition unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend decomposition unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return success_response(
            result,
            TrendDecompositionResultResponse,
            resource_name="Trend decomposition",
            location_id=location_id,
            metric_key=metric_key,
        )

    @router.get(
        "/operator/api/trends/{location_id}/forecast",
        response_model=TrendForecastResultResponse,
    )
    async def trend_forecast(
        request: Request,
        location_id: str,
        metric_key: str,
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                get_location_time_series_forecast,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend forecast unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend forecast unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return success_response(
            result,
            TrendForecastResultResponse,
            resource_name="Trend forecast",
            location_id=location_id,
            metric_key=metric_key,
        )

    @router.post("/operator/api/trends/{location_id}/forecast")
    async def generate_trend_forecast(request: Request, location_id: str):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 4096:
                    raise ValueError("Forecast request must not exceed 4 KiB")
                body.extend(chunk)
            payload = json.loads(bytes(body))
            if not isinstance(payload, dict) or set(payload) - {
                "metric_key", "forecast_horizon", "confidence"
            }:
                raise ValueError("Forecast request must contain supported fields")
            result = await run_in_threadpool(
                create_location_time_series_forecast,
                request.state.operator_session.operator.operator_id,
                location_id,
                payload.get("metric_key"),
                forecast_horizon=payload.get("forecast_horizon", 12),
                confidence=payload.get("confidence", 0.95),
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend compute access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend forecast compute unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend forecast compute unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return JSONResponse(
            jsonable_encoder(result),
            status_code=201 if result.get("created") else 200,
            headers=headers,
        )

    @router.get(
        "/operator/api/trends/{location_id}/smoothing",
        response_model=TrendSmoothingResponse,
    )
    async def trend_smoothing(
        request: Request,
        location_id: str,
        metric_key: str,
        limit: int = Query(default=100, ge=1, le=100),
    ):
        if provider is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Operator OIDC is disabled"},
                headers=headers,
            )
        try:
            result = await run_in_threadpool(
                list_location_trend_smoothing,
                request.state.operator_session.operator.operator_id,
                location_id,
                metric_key,
                limit=limit,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified trend access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.trend_analysis").warning(
                "Trend smoothing unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Trend smoothing unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return success_response(
            result,
            TrendSmoothingResponse,
            resource_name="Trend smoothing",
            location_id=location_id,
            metric_key=metric_key,
            limit=limit,
        )
