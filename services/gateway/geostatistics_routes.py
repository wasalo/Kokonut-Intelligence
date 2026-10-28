"""OIDC routes for saved, location-scoped geostatistics outputs."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator


class _SpatialAutocorrelationResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class _GeostatisticsResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SpatialAutocorrelationStatistic(_SpatialAutocorrelationResponseModel):
    property_key: str = Field(max_length=100)
    metric: Literal["morans_i", "gearys_c", "join_count"]
    statistic_value: float | None = Field(strict=True)
    expected_value: float | None = Field(strict=True)
    p_value: float | None = Field(strict=True)
    z_score: float | None = Field(strict=True)
    n_samples: int = Field(ge=0, strict=True)
    spatial_weights_type: Literal["queen", "rook", "distance", "knn"] | None
    distance_threshold: float | None = Field(strict=True)
    k_neighbors: int | None = Field(default=None, strict=True)
    computed_at: AwareDatetime


class SpatialAutocorrelationPage(_SpatialAutocorrelationResponseModel):
    location_id: UUID
    items: list[SpatialAutocorrelationStatistic] = Field(max_length=50)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) < self.limit and self.has_more:
            raise ValueError("has_more is inconsistent with the returned page")
        if self.has_more and self.offset + self.limit > 10_000:
            raise ValueError("has_more exceeds the supported offset boundary")
        return self


class GeostatisticsPage(_GeostatisticsResponseModel):
    location_id: UUID
    items: list
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("page contains more items than requested")
        if len(self.items) < self.limit and self.has_more:
            raise ValueError("has_more is inconsistent with the returned page")
        if self.has_more and self.offset + self.limit > 10_000:
            raise ValueError("has_more exceeds the supported offset boundary")
        return self


class SpatialCrossValidationFold(_GeostatisticsResponseModel):
    fold: int = Field(ge=1, strict=True)
    train_samples: int = Field(ge=1, strict=True)
    test_samples: int = Field(ge=5, strict=True)
    mean_error: float | None = Field(strict=True)
    mean_squared_error: float | None = Field(strict=True)
    rmse: float | None = Field(strict=True)
    mae: float | None = Field(strict=True)
    r_squared: float | None = Field(strict=True)


class SpatialCrossValidationSummary(_GeostatisticsResponseModel):
    property_key: str = Field(max_length=100)
    cv_strategy: Literal["spatial_block", "leave_one_out", "k_fold"]
    n_folds: int = Field(ge=1, strict=True)
    block_size_m: float | None = Field(strict=True)
    mean_error: float | None = Field(strict=True)
    mean_squared_error: float | None = Field(strict=True)
    root_mean_squared_error: float | None = Field(strict=True)
    mean_absolute_error: float | None = Field(strict=True)
    r_squared: float | None = Field(strict=True)
    computed_at: AwareDatetime
    fold_diagnostics: list[SpatialCrossValidationFold] = Field(max_length=10)


class SpatialCrossValidationPage(GeostatisticsPage):
    items: list[SpatialCrossValidationSummary] = Field(max_length=50)


class VariogramModelSummary(_GeostatisticsResponseModel):
    property_key: str = Field(max_length=100)
    model_type: Literal["spherical", "exponential", "gaussian", "matern"]
    sill: float = Field(strict=True)
    range: float = Field(strict=True)
    nugget: float = Field(strict=True)
    partial_sill: float | None = Field(strict=True)
    lag_distance: float | None = Field(strict=True)
    lag_tolerance: float | None = Field(strict=True)
    bandwidth: float | None = Field(strict=True)
    n_pairs: int | None = Field(ge=0, strict=True)
    r_squared: float | None = Field(strict=True)
    fitted_at: AwareDatetime


class VariogramModelPage(GeostatisticsPage):
    items: list[VariogramModelSummary] = Field(max_length=50)


class SensorNetworkDesignSummary(_GeostatisticsResponseModel):
    property_key: str = Field(max_length=100)
    optimal_spacing_m: float | None = Field(strict=True)
    coverage_radius_m: float | None = Field(strict=True)
    recommended_n_sensors: int | None = Field(ge=0, strict=True)
    current_n_sensors: int | None = Field(ge=0, strict=True)
    coverage_gap_pct: float | None = Field(strict=True)
    confidence_level: float | None = Field(strict=True)
    computed_at: AwareDatetime


class SensorNetworkDesignPage(GeostatisticsPage):
    items: list[SensorNetworkDesignSummary] = Field(max_length=50)


class KrigingSummary(_GeostatisticsResponseModel):
    prediction_id: UUID
    property_key: str = Field(max_length=100)
    method: Literal["ordinary", "simple", "indicator"]
    grid_resolution_m: float | None = Field(strict=True)
    n_points: int = Field(ge=0, strict=True)
    result_point_count: int = Field(ge=0, strict=True)
    mean_predicted: float | None = Field(strict=True)
    mean_variance: float | None = Field(strict=True)
    mean_std: float | None = Field(strict=True)
    min_predicted: float | None = Field(strict=True)
    max_predicted: float | None = Field(strict=True)
    created_at: AwareDatetime


class KrigingSummaryPage(GeostatisticsPage):
    items: list[KrigingSummary] = Field(max_length=50)


class KrigingPredictionMetadata(_GeostatisticsResponseModel):
    property_key: str = Field(max_length=100)
    method: Literal["ordinary", "simple", "indicator"]
    grid_resolution_m: float | None = Field(strict=True)
    n_points: int = Field(ge=0, strict=True)
    created_at: AwareDatetime


class KrigingPoint(_GeostatisticsResponseModel):
    longitude: float | None = Field(ge=-180, le=180, strict=True)
    latitude: float | None = Field(ge=-90, le=90, strict=True)
    predicted_value: float | None = Field(strict=True)
    prediction_variance: float | None = Field(ge=0, strict=True)
    prediction_std: float | None = Field(ge=0, strict=True)
    point_number: int = Field(ge=1, strict=True)


class KrigingPointPage(_GeostatisticsResponseModel):
    location_id: UUID
    prediction_id: UUID
    prediction: KrigingPredictionMetadata
    items: list[KrigingPoint] = Field(max_length=50)
    total: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("page contains more items than requested")
        if self.has_more and (
            len(self.items) != self.limit
            or self.offset + len(self.items) >= self.total
            or self.offset + self.limit > 10_000
        ):
            raise ValueError("has_more is inconsistent with the returned page")
        if any(point.point_number != self.offset + index for index, point in enumerate(self.items, 1)):
            raise ValueError("point numbering is inconsistent with the returned page")
        return self


class RealizationSummary(_GeostatisticsResponseModel):
    realization_id: UUID
    property_key: str = Field(max_length=100)
    realization_number: int = Field(ge=0, strict=True)
    method: Literal["sgs", "sis", "turning_bands"]
    grid_resolution_m: float | None = Field(strict=True)
    n_points: int = Field(ge=0, strict=True)
    result_point_count: int = Field(ge=0, strict=True)
    mean_simulated_value: float | None = Field(strict=True)
    stddev_simulated_value: float | None = Field(strict=True)
    min_simulated_value: float | None = Field(strict=True)
    max_simulated_value: float | None = Field(strict=True)
    created_at: AwareDatetime


class RealizationSummaryPage(GeostatisticsPage):
    items: list[RealizationSummary] = Field(max_length=50)


class RealizationMetadata(_GeostatisticsResponseModel):
    property_key: str = Field(max_length=100)
    realization_number: int = Field(ge=0, strict=True)
    method: Literal["sgs", "sis", "turning_bands"]
    grid_resolution_m: float | None = Field(strict=True)
    n_points: int = Field(ge=0, strict=True)
    created_at: AwareDatetime


class RealizationPoint(_GeostatisticsResponseModel):
    longitude: float | None = Field(ge=-180, le=180, strict=True)
    latitude: float | None = Field(ge=-90, le=90, strict=True)
    simulated_value: float | None = Field(strict=True)
    point_number: int = Field(ge=1, strict=True)


class RealizationPointPage(_GeostatisticsResponseModel):
    location_id: UUID
    realization_id: UUID
    realization: RealizationMetadata
    items: list[RealizationPoint] = Field(max_length=50)
    total: int = Field(ge=0, strict=True)
    limit: int = Field(ge=1, le=50, strict=True)
    offset: int = Field(ge=0, le=10_000, strict=True)
    has_more: bool = Field(strict=True)

    @model_validator(mode="after")
    def validate_page(self):
        if len(self.items) > self.limit:
            raise ValueError("page contains more items than requested")
        if self.has_more and (
            len(self.items) != self.limit
            or self.offset + len(self.items) >= self.total
            or self.offset + self.limit > 10_000
        ):
            raise ValueError("has_more is inconsistent with the returned page")
        if any(point.point_number != self.offset + index for index, point in enumerate(self.items, 1)):
            raise ValueError("point numbering is inconsistent with the returned page")
        return self


def register_geostatistics_routes(router, provider, run_in_threadpool, psycopg2):
    from fastapi import Query
    from fastapi.encoders import jsonable_encoder
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    from services.common.tenant_context import TenantContextDenied
    from services.gateway.geostatistics_reads import (
        GeostatisticalKrigingNotFound,
        GeostatisticalRealizationNotFound,
        list_location_cross_validation,
        list_location_kriging_points,
        list_location_kriging_summaries,
        list_location_realization_points,
        list_location_realization_summaries,
        list_location_sensor_network_designs,
        list_location_spatial_autocorrelation,
        list_location_variogram_models,
    )

    headers = {"Cache-Control": "no-store", "Vary": "Cookie"}

    def contracted_response(model, result, *, expected, failure):
        try:
            validated = model.model_validate(result)
            if any(getattr(validated, key) != value for key, value in expected.items()):
                raise ValueError("response does not match request")
        except (ValidationError, ValueError) as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Geostatistics response rejected (%s)", type(exc).__name__
            )
            return JSONResponse(status_code=500, content={"error": failure}, headers=headers)
        return JSONResponse(
            jsonable_encoder(validated.model_dump(mode="json")), headers=headers
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/autocorrelation",
        response_model=SpatialAutocorrelationPage,
    )
    async def spatial_autocorrelation(
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
                list_location_spatial_autocorrelation,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Spatial autocorrelation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Spatial autocorrelation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            SpatialAutocorrelationPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Spatial autocorrelation unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/cross-validation",
        response_model=SpatialCrossValidationPage,
    )
    async def spatial_cross_validation(
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
                list_location_cross_validation,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Spatial cross-validation unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Spatial cross-validation unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            SpatialCrossValidationPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Spatial cross-validation unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/variogram-models",
        response_model=VariogramModelPage,
    )
    async def variogram_models(
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
                list_location_variogram_models,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Variogram model summaries unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Variogram model summaries unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            VariogramModelPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Variogram model summaries unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/sensor-network-designs",
        response_model=SensorNetworkDesignPage,
    )
    async def sensor_network_designs(
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
                list_location_sensor_network_designs,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Sensor-network design summaries unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Sensor-network design summaries unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            SensorNetworkDesignPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Sensor-network design summaries unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/kriging-summaries",
        response_model=KrigingSummaryPage,
    )
    async def kriging_summaries(
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
                list_location_kriging_summaries,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Kriging summaries unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Kriging summaries unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            KrigingSummaryPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Kriging summaries unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/kriging/{prediction_id}/points",
        response_model=KrigingPointPage,
    )
    async def kriging_points(
        request: Request,
        location_id: str,
        prediction_id: str,
        limit: int = Query(default=50, ge=1, le=50),
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
                list_location_kriging_points,
                request.state.operator_session.operator.operator_id,
                location_id,
                prediction_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except GeostatisticalKrigingNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Kriging prediction not found"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Kriging prediction points unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Kriging prediction points unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            KrigingPointPage,
            result,
            expected={
                "location_id": UUID(location_id),
                "prediction_id": UUID(prediction_id),
                "limit": limit,
                "offset": offset,
            },
            failure="Kriging prediction points unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/realization-summaries",
        response_model=RealizationSummaryPage,
    )
    async def realization_summaries(
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
                list_location_realization_summaries,
                request.state.operator_session.operator.operator_id,
                location_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Geostatistical realization summaries unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Geostatistical realization summaries unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            RealizationSummaryPage,
            result,
            expected={"location_id": UUID(location_id), "limit": limit, "offset": offset},
            failure="Geostatistical realization summaries unavailable",
        )

    @router.get(
        "/operator/api/geostatistics/{location_id}/realizations/{realization_id}/points",
        response_model=RealizationPointPage,
    )
    async def realization_points(
        request: Request,
        location_id: str,
        realization_id: str,
        limit: int = Query(default=50, ge=1, le=50),
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
                list_location_realization_points,
                request.state.operator_session.operator.operator_id,
                location_id,
                realization_id,
                limit=limit,
                offset=offset,
            )
        except TenantContextDenied:
            return JSONResponse(
                status_code=403,
                content={"error": "Tenant-qualified geostatistics access is required"},
                headers=headers,
            )
        except GeostatisticalRealizationNotFound:
            return JSONResponse(
                status_code=404,
                content={"error": "Geostatistical realization not found"},
                headers=headers,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)}, headers=headers)
        except psycopg2.Error as exc:
            from services.common.logging import get_logger

            get_logger("gateway.geostatistics").warning(
                "Geostatistical realization points unavailable (%s)", type(exc).__name__
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Geostatistical realization points unavailable"},
                headers={**headers, "Retry-After": "30"},
            )
        return contracted_response(
            RealizationPointPage,
            result,
            expected={
                "location_id": UUID(location_id),
                "realization_id": UUID(realization_id),
                "limit": limit,
                "offset": offset,
            },
            failure="Geostatistical realization points unavailable",
        )
