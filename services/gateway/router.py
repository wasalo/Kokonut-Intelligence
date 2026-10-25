"""Gateway router — route definitions and backend proxying."""

from __future__ import annotations

import re

from services.common.errors import safe_exception_class
from services.common.logging import get_logger

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    from services.gateway.public_models import (
        PublicCrispAssessment,
        PublicCrispAssessmentEnvelope,
        PublicError,
        PublicLocationListResponse,
        PublicLocationResponse,
        PublicLocationSummary,
        PublicLocationSummaryEnvelope,
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
    ("GET", re.compile(r"^/mobile/field-collector-service-worker\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/field-collector-service-worker\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/app$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/field-collector-vault\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/field-collector-service-worker\.js$"), "mobile_app", "read", True),
    ("GET", re.compile(r"^/api/mobile/forms$"), "mobile_form", "read", True),
    ("POST", re.compile(r"^/api/mobile/media/uploads$"), "mobile_media", "upload", True),
    ("POST", re.compile(r"^/api/mobile/register$"), "mobile_device", "register", True),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/enrollments$"), "mobile_device", "enroll", False),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/participants$"), "mobile_participant", "create", False),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/participants/revoke$"), "mobile_participant", "revoke", False),
    ("DELETE", re.compile(r"^/api/mobile/locations/([^/]+)/enrollments/([^/]+)$"), "mobile_device", "revoke", False),
    ("POST", re.compile(r"^/api/mobile/locations/([^/]+)/devices/([^/]+)/revoke$"), "mobile_device", "revoke", False),
    # These endpoints perform their own opaque device-token authentication.
    ("POST", re.compile(r"^/api/mobile/sync$"), "offline_collection", "write", True),
    ("GET", re.compile(r"^/api/mobile/sync/status$"), "offline_collection", "read", True),
    # Capability-token routes authenticate inside the handler and deliberately
    # do not create canonical party identities for Delphi participants.
    ("POST", re.compile(r"^/api/participation/delphi/preview$"), "delphi_participant", "preview", True),
    ("POST", re.compile(r"^/api/participation/delphi/accept$"), "delphi_participant", "accept", True),
    ("POST", re.compile(r"^/api/participation/delphi/withdraw$"), "delphi_participant", "withdraw", True),
    ("GET", re.compile(r"^/api/v1/locations(?:/([^/]+))?$"), "location", "read", True),
    ("GET", re.compile(r"^/api/v1/metrics/([^/]+)$"), "metric", "read", True),
    ("GET", re.compile(r"^/api/v1/crisp/([^/]+)$"), "crisp_risk_assessment", "read", True),
    ("GET", re.compile(r"^/api/v1/analytics/([^/]+)/summary$"), "analytics", "read", True),
    ("GET", re.compile(r"^/api/v1/governance/baal/config$"), "governance", "read", False),
    ("GET", re.compile(r"^/api/v1/governance/baal/proposals$"), "governance", "read", False),
    ("GET", re.compile(r"^/api/v1/governance/baal/proposals/[^/]+$"), "governance", "read", False),
    ("GET", re.compile(r"^/api/v1/governance/baal/members/[^/]+$"), "governance", "read", False),
    ("GET", re.compile(r"^/api/locations(?:/([^/]+))?$"), "location", "read", True),
    ("GET", re.compile(r"^/api/metrics/([^/]+)$"), "metric", "read", True),
    ("GET", re.compile(r"^/api/crisp/([^/]+)$"), "crisp_risk_assessment", "read", True),
    ("GET", re.compile(r"^/api/analytics/([^/]+)/summary$"), "analytics", "read", True),
    ("GET", re.compile(r"^/api/iri/resolve$"), "iri", "read", True),
    ("GET", re.compile(r"^/api/federation/nodes$"), "federation_node", "read", True),
    ("GET", re.compile(r"^/api/drivers$"), "driver", "read", True),
    ("GET", re.compile(r"^/api/health/services$"), "service_health", "read", True),
    ("GET", re.compile(r"^/api/data-stream/posts$"), "data_stream_post", "read", False),
    ("GET", re.compile(r"^/api/data-stream/posts/[^/]+/files$"), "data_stream_file", "read", False),
    ("GET", re.compile(r"^/api/data-stream/posts/[^/]+/attestation$"), "data_stream_proof", "read", False),
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
    logger.warning("Catch-all route hit — no explicit policy defined")
    return {"resource": "gateway", "action": method.lower(), "public": False, "location_id": None}


def _internal_error(exc: Exception, message: str = "Gateway request failed"):
    logger.error("%s (%s)", message, safe_exception_class(exc))
    return JSONResponse(
        status_code=500,
        content={"error": message},
        headers={"Cache-Control": "no-store"},
    )


def _private_response(content: dict, status_code: int = 200):
    """Build a non-cacheable response for authenticated private resources."""
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={"Cache-Control": "no-store"},
    )


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
    """Read public locations through the governed native projection."""
    import json

    from starlette.concurrency import run_in_threadpool

    from services.gateway.locations import public_locations

    try:
        rows = await run_in_threadpool(public_locations)
        return JSONResponse(content={"data": json.dumps({"data": rows})})
    except Exception as exc:
        return _internal_error(exc)


@router.get("/locations/{location_id}")
async def get_location(location_id: str):
    """Read one public location through the governed native projection."""
    from uuid import UUID

    from starlette.concurrency import run_in_threadpool

    try:
        UUID(location_id)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid location identifier"})

    import json

    from services.gateway.locations import public_locations

    try:
        rows = await run_in_threadpool(public_locations, location_id)
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Location not found"})
        return JSONResponse(content={"data": json.dumps({"data": rows[0]})})
    except Exception as exc:
        return _internal_error(exc)


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


@router.get("/data-stream/posts")
async def list_data_stream_posts(request: Request):
    """List or search tenant-scoped Data Stream posts without caching content."""
    from starlette.concurrency import run_in_threadpool

    try:
        location_id = request.query_params.get("location_id")
        query_text = request.query_params.get("q")
        try:
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
        except ValueError as exc:
            raise ValueError("limit and offset must be integers") from exc

        from services.gateway.data_stream import list_gateway_data_stream_posts

        rows = await run_in_threadpool(
            list_gateway_data_stream_posts,
            location_id,
            request.state.gateway_authorization,
            query_text=query_text,
            limit=limit,
            offset=offset,
        )
        return _private_response({"data": rows})
    except ValueError as exc:
        return _private_response({"error": str(exc)}, status_code=400)
    except Exception as exc:
        from services.common.tenant_context import TenantContextDenied

        if isinstance(exc, TenantContextDenied):
            return _private_response({"error": "Tenant access denied"}, status_code=403)
        return _internal_error(exc)


@router.get("/data-stream/posts/{post_id}/files")
async def list_data_stream_post_files(post_id: str, request: Request):
    """List safe, tenant-scoped attachment metadata without caching it."""
    from starlette.concurrency import run_in_threadpool

    try:
        from services.gateway.data_stream import list_gateway_data_stream_files

        rows = await run_in_threadpool(
            list_gateway_data_stream_files,
            post_id,
            request.query_params.get("location_id"),
            request.state.gateway_authorization,
        )
        return _private_response({"data": rows})
    except ValueError as exc:
        return _private_response({"error": str(exc)}, status_code=400)
    except Exception as exc:
        from services.common.tenant_context import TenantContextDenied

        if isinstance(exc, TenantContextDenied):
            return _private_response({"error": "Tenant access denied"}, status_code=403)
        return _internal_error(exc)


@router.get("/data-stream/posts/{post_id}/attestation")
async def get_data_stream_post_attestation(post_id: str, request: Request):
    """Read stored attestation metadata without caching or querying the chain."""
    from starlette.concurrency import run_in_threadpool

    try:
        from services.gateway.data_stream import get_gateway_data_stream_attestation

        row = await run_in_threadpool(
            get_gateway_data_stream_attestation,
            post_id,
            request.query_params.get("location_id"),
            request.state.gateway_authorization,
        )
        if row is None:
            return _private_response({"error": "Data Stream post not found"}, status_code=404)
        return _private_response({"data": row})
    except ValueError as exc:
        return _private_response({"error": str(exc)}, status_code=400)
    except Exception as exc:
        from services.common.tenant_context import TenantContextDenied

        if isinstance(exc, TenantContextDenied):
            return _private_response({"error": "Tenant access denied"}, status_code=403)
        return _internal_error(exc)


@router.post("/data-stream/post")
async def create_data_stream_post(request: Request):
    """Create a tenant-scoped draft Data Stream post."""
    from starlette.concurrency import run_in_threadpool

    try:
        body = await request.json()
        from services.gateway.data_stream import create_gateway_data_stream_post

        result = await run_in_threadpool(
            create_gateway_data_stream_post,
            body,
            request.state.gateway_authorization,
        )
        return _private_response({"post_id": result["id"]}, status_code=201)
    except ValueError as exc:
        return _private_response({"error": str(exc)}, status_code=400)
    except Exception as exc:
        from services.common.tenant_context import TenantContextDenied

        if isinstance(exc, TenantContextDenied):
            return _private_response({"error": "Tenant access denied"}, status_code=403)
        return _internal_error(exc)


@router.get("/iri/resolve")
async def resolve_iri(iri: str):
    """Resolve a public location IRI to its non-sensitive JSON-LD projection."""
    from starlette.concurrency import run_in_threadpool

    try:
        from services.gateway.public_iri import resolve_public_location_iri

        result = await run_in_threadpool(resolve_public_location_iri, iri)
        if result:
            return JSONResponse(
                content=result,
                media_type="application/ld+json",
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            status_code=404,
            content={"error": "IRI not found"},
            headers={"Cache-Control": "no-store"},
        )
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


@router.get("/v1/governance/baal/config")
async def get_baal_governance_config():
    """Read global Baal configuration under the governance:read credential scope."""
    from starlette.concurrency import run_in_threadpool

    from services.gateway.governance import read_baal_config

    try:
        result = await run_in_threadpool(read_baal_config)
        return _private_response({"data": result})
    except Exception as exc:
        return _governance_read_error(exc)


@router.get("/v1/governance/baal/proposals")
async def get_baal_governance_proposals(limit: str = "50"):
    """Read a bounded newest-first list of global Baal proposals."""
    from starlette.concurrency import run_in_threadpool

    from services.gateway.governance import read_baal_proposals

    try:
        parsed_limit = int(limit)
    except (TypeError, ValueError):
        return _private_response({"error": "limit must be an integer"}, status_code=400)
    try:
        result = await run_in_threadpool(read_baal_proposals, parsed_limit)
        return _private_response({"data": result})
    except Exception as exc:
        return _governance_read_error(exc)


@router.get("/v1/governance/baal/proposals/{proposal_id}")
async def get_baal_governance_proposal(proposal_id: str):
    """Read one global Baal proposal by decimal proposal identifier."""
    from starlette.concurrency import run_in_threadpool

    from services.gateway.governance import read_baal_proposal

    try:
        result = await run_in_threadpool(read_baal_proposal, proposal_id)
        return _private_response({"data": result})
    except Exception as exc:
        return _governance_read_error(exc)


@router.get("/v1/governance/baal/members/{wallet}")
async def get_baal_governance_member(wallet: str):
    """Read one requested public Baal member position by wallet address."""
    from starlette.concurrency import run_in_threadpool

    from services.gateway.governance import read_baal_member

    try:
        result = await run_in_threadpool(read_baal_member, wallet)
        return _private_response({"data": result})
    except Exception as exc:
        return _governance_read_error(exc)


def _governance_read_error(exc: Exception):
    from services.gateway.governance import (
        GovernanceProposalNotFound,
        GovernanceReadUnavailable,
    )

    if isinstance(exc, ValueError):
        return _private_response({"error": str(exc)}, status_code=400)
    if isinstance(exc, GovernanceProposalNotFound):
        return _private_response({"error": "Governance proposal not found"}, status_code=404)
    if isinstance(exc, GovernanceReadUnavailable):
        logger.warning("Baal governance read unavailable (%s)", type(exc).__name__)
        return _private_response({"error": "Governance read unavailable"}, status_code=503)
    return _internal_error(exc)
