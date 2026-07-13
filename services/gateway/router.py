"""Gateway router — route definitions and backend proxying."""

from __future__ import annotations

import re

from services.common.logging import get_logger

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse
except ImportError:
    # Stub for environments without FastAPI
    APIRouter = None
    Request = None
    JSONResponse = None

router = APIRouter() if APIRouter else None
logger = get_logger("gateway.router")


# Public access is deliberately opt-in. Unknown routes remain protected.
_ROUTE_POLICIES = (
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
    return {"resource": "gateway", "action": method.lower(), "public": False, "location_id": None}


def _internal_error(exc: Exception, message: str = "Gateway request failed"):
    logger.exception(message, exc_info=exc)
    return JSONResponse(status_code=500, content={"error": message})


@router.get("/locations")
async def list_locations():
    """Proxy to Directus locations endpoint."""
    import os, urllib.request
    directus_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
    try:
        req = urllib.request.Request(f"{directus_url}/items/location?limit=100")
        resp = urllib.request.urlopen(req, timeout=10)
        return JSONResponse(content={"data": resp.read().decode()})
    except Exception as exc:
        logger.exception("Directus locations request failed", exc_info=exc)
        return JSONResponse(status_code=502, content={"error": "Upstream service unavailable"})


@router.get("/locations/{location_id}")
async def get_location(location_id: str):
    """Proxy to Directus single location endpoint."""
    import os, urllib.request
    directus_url = os.environ.get("DIRECTUS_URL", "http://localhost:8055")
    try:
        req = urllib.request.Request(f"{directus_url}/items/location/{location_id}")
        resp = urllib.request.urlopen(req, timeout=10)
        return JSONResponse(content={"data": resp.read().decode()})
    except Exception as exc:
        logger.exception("Directus location request failed", exc_info=exc)
        return JSONResponse(status_code=502, content={"error": "Upstream service unavailable"})


@router.get("/metrics/{location_id}")
async def get_metrics(location_id: str):
    """Get computed metrics for a location."""
    from services.metrics.engine import compute_all
    from services.ingestion.base import get_db

    conn = get_db()
    try:
        result = compute_all(conn, location_id)
        return JSONResponse(content=result)
    except Exception as exc:
        return _internal_error(exc)
    finally:
        conn.close()


@router.get("/crisp/{location_id}")
async def get_crisp(location_id: str):
    """Get CRISP risk score for a location."""
    try:
        from services.crisp import CRISPEngine
        engine = CRISPEngine()
        result = engine.composite_score(location_id)
        return JSONResponse(content=result)
    except Exception as exc:
        return _internal_error(exc)


@router.get("/analytics/{location_id}/summary")
async def get_analytics_summary(location_id: str):
    """Get analytics summary for a location."""
    try:
        from services.analytics.portfolio import PortfolioSummary
        summary = PortfolioSummary()
        result = summary.get_location_summary(location_id)
        return JSONResponse(content=result)
    except Exception as exc:
        return _internal_error(exc)


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
