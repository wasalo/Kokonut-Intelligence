"""Gateway router — route definitions and backend proxying."""

from __future__ import annotations

import re

from services.common.logging import get_logger

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    from services.gateway.public_models import (
        PublicCrispAssessment,
        PublicError,
        PublicLocationListResponse,
        PublicLocationResponse,
        PublicLocationSummary,
        PublicLocationSummaryEnvelope,
        PublicCrispAssessmentEnvelope,
        PublicMetricSummary,
        PublicMetricSummaryEnvelope,
    )
except ImportError:
    # Stub for environments without FastAPI
    class APIRouter:
        def get(self, _path, **_kwargs):
            return lambda func: func

        def post(self, _path):
            return lambda func: func

    Request = None
    JSONResponse = None
    PublicCrispAssessment = PublicError = PublicLocationListResponse = None
    PublicLocationResponse = PublicLocationSummary = PublicMetricSummary = None
    PublicLocationSummaryEnvelope = PublicCrispAssessmentEnvelope = None
    PublicMetricSummaryEnvelope = None

router = APIRouter()
logger = get_logger("gateway.router")


# Public access is deliberately opt-in. Unknown routes remain protected.
_ROUTE_POLICIES = (
    ("GET", re.compile(r"^/health$"), "gateway", "read", True),
    ("GET", re.compile(r"^/mobile/?$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/mobile/field-collector-vault\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/field-collector-vault\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/app$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/field-collector-vault\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/forms$"), "mobile_form", "read", True),
    ("POST", re.compile(r"^/api/mobile/media/uploads$"), "mobile_media", "upload", True),
    ("POST", re.compile(r"^/api/mobile/register$"), "mobile_device", "register", True),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/enrollments$"), "mobile_device", "enroll", False),
    ("DELETE", re.compile(r"^/api/mobile/locations/([^/]+)/enrollments/([^/]+)$"), "mobile_device", "revoke", False),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/devices/([^/]+)/revoke$"), "mobile_device", "revoke", False),
    # These endpoints perform their own opaque device-token authentication.
    ("POST", re.compile(r"^/api/mobile/sync$"), "offline_collection", "write", True),
    ("GET", re.compile(r"^/api/mobile/sync/status$"), "offline_collection", "read", True),
    ("GET", re.compile(r"^/api/v1/locations(?:/([^/]+))?$"), "location", "read", True),
    ("GET", re.compile(r"^/api/v1/metrics/([^/]+)$"), "metric", "read", True),
    ("GET", re.compile(r"^/api/v1/crisp/([^/]+)$"), "crisp_risk_assessment", "read", True),
    ("GET", re.compile(r"^/api/v1/analytics/([^/]+)/summary$"), "analytics", "read", True),
    ("GET", re.compile(r"^/api/locations(?:/([^/]+))?$"), "location", "read", True),
    ("GET", re.compile(r"^/api/metrics/([^/]+)$"), "metric", "read", True),
    ("GET", re.compile(r"^/api/crisp/([^/]+)$"), "crisp_risk_assessment", "read", True),
    ("GET", re.compile(r"^/api/analytics/([^/]+)/summary$"), "analytics", "read", True),
    ("GET", re.compile(r"^/api/iri/resolve$"), "iri", "read", True),
    ("GET", re.compile(r"^/api/federation/nodes$"), "federation_node", "read", True),
    ("GET", re.compile(r"^/api/drivers$"), "driver", "read", True),
    ("GET", re.compile(r"^/api/health/services$"), "service_health", "read", True),
    ("POST", re.compile(r"^/api/data-stream/post$"), "data_stream_post", "create", False),
)


def get_route_policy(method: str, path: str) -> dict:
    """Return explicit authorization metadata for a gateway route."""
    for route_method, pattern, resource, action, public in _ROUTE_POLICIES:
        match = pattern.fullmatch(path) if route_method == method.upper() else None
        if match:
            return {
                "resource": resource,
                "action": action,
                "public": public,
                "location_id": match.group(1) if match.groups() else None,
            }
    logger.warning(
        "Catch-all route hit: %s %s — no explicit policy defined",
        method,
        path,
    )
    return {"resource": "gateway", "action": method.lower(), "public": False, "location_id": None}


def _internal_error(exc: Exception, message: str = "Gateway request failed"):
    logger.exception(message, exc_info=exc)
    return JSONResponse(status_code=500, content={"error": message})


def _public_response(model, payload: dict):
    """Validate even when returning a Response that bypasses FastAPI filtering."""
    from fastapi.encoders import jsonable_encoder

    validated = model.model_validate(payload)
    return JSONResponse(content=jsonable_encoder(validated.model_dump(mode="python")))


def _versioned_envelope(response):
    """Wrap a successful legacy read response without changing its old route."""
    if isinstance(response, JSONResponse):
        if response.status_code >= 400:
            return response
        import json

        return {"data": json.loads(response.body)}
    return {"data": response}


@router.get("/locations")
async def list_locations():
    """Read public locations through the selected application/provider path."""
    from starlette.concurrency import run_in_threadpool

    from services.core.features import is_enabled

    if not is_enabled("directus"):
        import json

        from services.gateway.locations import public_locations

        try:
            rows = await run_in_threadpool(public_locations)
            return JSONResponse(content={"data": json.dumps({"data": rows})})
        except Exception as exc:
            return _internal_error(exc)

    import os

    from services.common.http import http

    directus_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
    try:
        resp = await run_in_threadpool(http.get, f"{directus_url}/items/location?limit=100")
        resp.raise_for_status()
        return JSONResponse(content={"data": resp.text})
    except Exception as exc:
        logger.exception("Directus locations request failed", exc_info=exc)
        return JSONResponse(status_code=502, content={"error": "Upstream service unavailable"})


@router.get("/locations/{location_id}")
async def get_location(location_id: str):
    """Read a public location through the selected application/provider path."""
    import os
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    from services.common.http import http

    try:
        UUID(location_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})

    from services.core.features import is_enabled

    if not is_enabled("directus"):
        import json

        from services.gateway.locations import public_locations

        try:
            rows = await run_in_threadpool(public_locations, location_id)
            if not rows:
                return JSONResponse(status_code=404, content={"error": "Location not found"})
            return JSONResponse(content={"data": json.dumps({"data": rows[0]})})
        except Exception as exc:
            return _internal_error(exc)

    directus_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
    try:
        resp = await run_in_threadpool(http.get, f"{directus_url}/items/location/{location_id}")
        resp.raise_for_status()
        return JSONResponse(content={"data": resp.text})
    except Exception as exc:
        logger.exception("Directus location request failed", exc_info=exc)
        return JSONResponse(status_code=502, content={"error": "Upstream service unavailable"})


@router.get(
    "/v1/locations",
    response_model=PublicLocationListResponse,
    responses={500: {"model": PublicError}},
    operation_id="listPublicLocationsV1",
)
async def list_public_locations_v1():
    """List the bounded, governed public location projection using the v1 envelope."""
    from starlette.concurrency import run_in_threadpool

    from services.gateway.locations import public_locations

    try:
        rows = await run_in_threadpool(public_locations)
        return {"data": rows}
    except Exception as exc:
        return _internal_error(exc)


@router.get(
    "/v1/locations/{location_id}",
    response_model=PublicLocationResponse,
    responses={400: {"model": PublicError}, 404: {"model": PublicError}, 500: {"model": PublicError}},
    operation_id="getPublicLocationV1",
)
async def get_public_location_v1(location_id: str):
    """Read one eligible public location using the v1 envelope."""
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    try:
        location_id = str(UUID(location_id))
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})

    from services.gateway.locations import public_locations

    try:
        rows = await run_in_threadpool(public_locations, location_id)
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Location not found"})
        return {"data": rows[0]}
    except Exception as exc:
        return _internal_error(exc)


@router.get("/metrics/{location_id}", response_model=PublicMetricSummary,
            responses={400: {"model": PublicError}, 500: {"model": PublicError}})
async def get_metrics(location_id: str):
    """Get verified public metrics for a location without creating records."""
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    from services.analytics.backend import get_analytics_backend
    from services.analytics.queries import AnalyticsContext, MetricSummaryRequest, QueryId

    try:
        UUID(location_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})

    try:
        rows = await run_in_threadpool(
            get_analytics_backend().execute,
            QueryId.PUBLIC_METRIC_SUMMARY,
            MetricSummaryRequest(location_id),
            AnalyticsContext(location_id),
        )
        return _public_response(
            PublicMetricSummary, {
                "location_id": location_id,
                "computed": [row.to_dict() for row in rows],
                "total_computed": len(rows),
            }
        )
    except Exception as exc:
        return _internal_error(exc)


@router.get("/crisp/{location_id}", response_model=PublicCrispAssessment,
            responses={400: {"model": PublicError}, 404: {"model": PublicError},
                       500: {"model": PublicError}})
async def get_crisp(location_id: str):
    """Read the latest published CRISP assessment for a public location."""
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    from services.crisp.public_api import latest_published_assessment

    try:
        UUID(location_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})
    try:
        result = await run_in_threadpool(latest_published_assessment, location_id)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "Published assessment not found"})
        return _public_response(PublicCrispAssessment, result)
    except Exception as exc:
        return _internal_error(exc)


@router.get("/analytics/{location_id}/summary", response_model=PublicLocationSummary,
            responses={400: {"model": PublicError}, 404: {"model": PublicError},
                       500: {"model": PublicError}})
async def get_analytics_summary(location_id: str):
    """Read a governed public location roll-up without computing outputs."""
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    from services.analytics.public_summary import location_summary

    try:
        UUID(location_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})
    try:
        result = await run_in_threadpool(location_summary, location_id)
        if result is None:
            return JSONResponse(status_code=404, content={"error": "Location not found"})
        return _public_response(PublicLocationSummary, result)
    except Exception as exc:
        return _internal_error(exc)


@router.get(
    "/v1/metrics/{location_id}",
    response_model=PublicMetricSummaryEnvelope,
    responses={400: {"model": PublicError}, 500: {"model": PublicError}},
    operation_id="getPublicMetricSummaryV1",
)
async def get_public_metrics_v1(location_id: str):
    return _versioned_envelope(await get_metrics(location_id))


@router.get(
    "/v1/crisp/{location_id}",
    response_model=PublicCrispAssessmentEnvelope,
    responses={400: {"model": PublicError}, 404: {"model": PublicError},
               500: {"model": PublicError}},
    operation_id="getPublicCrispAssessmentV1",
)
async def get_public_crisp_v1(location_id: str):
    return _versioned_envelope(await get_crisp(location_id))


@router.get(
    "/v1/analytics/{location_id}/summary",
    response_model=PublicLocationSummaryEnvelope,
    responses={400: {"model": PublicError}, 404: {"model": PublicError},
               500: {"model": PublicError}},
    operation_id="getPublicLocationSummaryV1",
)
async def get_public_analytics_summary_v1(location_id: str):
    return _versioned_envelope(await get_analytics_summary(location_id))


@router.post("/data-stream/post")
async def create_data_stream_post(request: Request):
    """Create a data stream post."""
    try:
        body = await request.json()
        from services.data_stream.post import create_post
        post_id = create_post(
            location_id=body["location_id"],
            post_type=body.get("post_type", "monitoring_report"),
            title=body.get("title", ""),
            content=body.get("content", ""),
            created_by=request.state.caller,
        )
        return JSONResponse(content={"post_id": post_id}, status_code=201)
    except Exception as exc:
        return _internal_error(exc)


@router.get("/iri/resolve")
async def resolve_iri(iri: str):
    """Resolve an IRI to its governed record."""
    try:
        from services.iri.resolver import resolve
        result = resolve(iri)
        if result:
            return JSONResponse(content=result)
        return JSONResponse(status_code=404, content={"error": "IRI not found"})
    except Exception as exc:
        return _internal_error(exc)


@router.get("/federation/nodes")
async def list_federation_nodes():
    """List federation nodes."""
    try:
        from services.federation.node import FederationNode
        node = FederationNode()
        nodes = node.list_nodes()
        return JSONResponse(content={"nodes": nodes})
    except Exception as exc:
        return _internal_error(exc)


@router.get("/drivers")
async def list_drivers():
    """List registered drivers."""
    try:
        from services.drivers.registry import DriverRegistry
        registry = DriverRegistry()
        drivers = registry.list_drivers()
        return JSONResponse(content={"drivers": drivers})
    except Exception as exc:
        return _internal_error(exc)


@router.get("/health/services")
async def service_health():
    """Get health status of all services."""
    try:
        from services.core.health import overall_health
        result = overall_health()
        return JSONResponse(content=result)
    except Exception as exc:
        return _internal_error(exc)
