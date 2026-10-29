"""Gateway application — FastAPI app with auth, routing, rate limiting, and audit."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from services.common.logging import get_logger
from services.gateway.rate_limit_backend import RateLimitBackend, get_rate_limiter

logger = get_logger("gateway.app")


def _request_identity(request, client_ip: str) -> str:
    """Return a bounded, non-secret identity for rate limits and audit logs."""
    credential = (
        request.headers.get("x-api-key")
        or request.headers.get("api-key")
        or request.headers.get("x-capability-token")
        or request.headers.get("capability-token")
        or request.cookies.get("kokonut_operator_session")
    )
    if credential:
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()[:16]
        return f"credential:{digest}"
    return f"ip:{client_ip}"


async def _request_location(request, policy: dict) -> str | None:
    """Resolve a route's location scope, including data-stream request bodies."""
    if policy.get("location_id"):
        return policy["location_id"]
    if policy.get("resource") in {
        "report_snapshot_review",
        "report_snapshot_export",
        "mobile_collection_review",
        "mobile_collection_retention",
        "farm_activity",
    }:
        from uuid import UUID

        try:
            return str(UUID(request.query_params.get("location_id", "")))
        except ValueError:
            return None
    if policy.get("resource") in {
        "data_stream_post",
        "data_stream_file",
        "data_stream_proof",
    } and request.method == "GET":
        from uuid import UUID

        try:
            return str(UUID(request.query_params.get("location_id", "")))
        except ValueError:
            return None
    if policy.get("resource") != "data_stream_post":
        return None
    try:
        body = await request.body()
        request._body = body
        payload = json.loads(body or b"{}")
        if not isinstance(payload, dict):
            return None
        return payload.get("location_id")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None


def create_app(*, rate_limiter: RateLimitBackend | None = None):
    """Create the FastAPI gateway application."""
    try:
        from fastapi import APIRouter, FastAPI, Request
        from fastapi.exceptions import RequestValidationError
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
        from starlette.concurrency import run_in_threadpool
    except ImportError:
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")

    import psycopg2

    from services.gateway.audit import GatewayAudit
    from services.gateway.auth import verify_request
    from services.gateway.delphi_participant_routes import register_delphi_participant_routes
    from services.gateway.operator_auth import (
        SESSION_COOKIE,
        OperatorAuthConfigurationError,
        auth_route_policy,
        authorize_auth_request,
        create_auth_router,
        create_provider,
    )
    from services.gateway.router import get_route_policy, router
    from services.mobile.api import router as mobile_router

    cors_origins = [
        origin.strip()
        for origin in os.environ.get("KOKONUT_GATEWAY_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if "*" in cors_origins:
        logger.warning("Ignoring wildcard CORS origin; configure explicit trusted origins")
        cors_origins = [origin for origin in cors_origins if origin != "*"]

    try:
        operator_provider = create_provider()
    except OperatorAuthConfigurationError:
        # Configuration errors must fail startup without echoing secret values.
        logger.error("Operator OIDC configuration is invalid")
        raise

    rate_limiter = get_rate_limiter() if rate_limiter is None else rate_limiter
    audit = GatewayAudit()
    audit_replay = GatewayAudit()
    audit_replay_task = None

    async def audit_replay_loop():
        while True:
            try:
                await run_in_threadpool(audit_replay.replay_pending, 100)
            except Exception as exc:
                logger.warning("Gateway audit replay unavailable (%s)", type(exc).__name__)
            await asyncio.sleep(15)

    @asynccontextmanager
    async def lifespan(_app):
        nonlocal audit_replay_task
        audit_replay_task = asyncio.create_task(audit_replay_loop())
        try:
            yield
        finally:
            if audit_replay_task is not None:
                audit_replay_task.cancel()
                try:
                    await audit_replay_task
                except asyncio.CancelledError:
                    pass
                audit_replay_task = None

    app = FastAPI(
        title="Kokonut Intelligence Gateway",
        version="1.0.0",
        description="Unified API gateway for the Kokonut Intelligence platform",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def gateway_middleware(request: Request, call_next):
        """Global middleware for auth, rate limiting, and audit."""
        if request.method == "OPTIONS":
            return await call_next(request)
        start_time = datetime.now(timezone.utc)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        # Rate limiting
        caller = _request_identity(request, client_ip)
        try:
            allowed = await run_in_threadpool(rate_limiter.check, caller)
            retry_after = await run_in_threadpool(rate_limiter.retry_after, caller) if not allowed else 0
        except Exception as exc:
            logger.warning("Gateway rate-limit backend unavailable (%s)", type(exc).__name__)
            await run_in_threadpool(
                audit.log,
                caller=caller, path=request.url.path, method=request.method,
                status="denied", ip=client_ip, user_agent=user_agent,
                status_code=503, reason="rate_limit_unavailable",
                resource="gateway", action=request.method.lower(),
            )
            return JSONResponse(
                status_code=503, content={"error": "Request limit service unavailable"},
                headers={"Retry-After": "30"},
            )
        if not allowed:
            await run_in_threadpool(
                audit.log,
                caller=caller,
                path=request.url.path,
                method=request.method,
                status="denied",
                ip=client_ip,
                user_agent=user_agent,
                status_code=429,
                reason="rate_limited",
                resource="gateway",
                action=request.method.lower(),
            )
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        operator_policy = auth_route_policy(
            request.method,
            request.url.path,
            enabled=operator_provider is not None,
        )
        policy = operator_policy or get_route_policy(request.method, request.url.path)
        if request.url.path == "/api/mobile/media/uploads":
            max_body_bytes = 2_000_000
        elif request.url.path == "/operator/api/report-exports":
            max_body_bytes = 8_192
        else:
            max_body_bytes = 8_000_000
        if request.method in {"POST", "PUT", "PATCH"}:
            async def reject_body(status_code: int, reason: str, message: str):
                await run_in_threadpool(
                    audit.log,
                    caller=auth_result_caller,
                    path=request.url.path,
                    method=request.method,
                    status="denied",
                    ip=client_ip,
                    user_agent=user_agent,
                    status_code=status_code,
                    reason=reason,
                    resource=policy["resource"],
                    action=policy["action"],
                )
                return JSONResponse(status_code=status_code, content={"error": message})

            auth_result_caller = caller
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    return await reject_body(400, "invalid_content_length", "Invalid Content-Length")
                if declared_size < 0:
                    return await reject_body(400, "invalid_content_length", "Invalid Content-Length")
                if declared_size > max_body_bytes:
                    return await reject_body(413, "request_body_too_large", "Request body too large")

            body_chunks = []
            body_size = 0
            async for chunk in request.stream():
                body_size += len(chunk)
                if body_size > max_body_bytes:
                    return await reject_body(413, "request_body_too_large", "Request body too large")
                body_chunks.append(chunk)
            body = b"".join(body_chunks)
            request._body = body
            delivered = False

            async def replay_body():
                nonlocal delivered
                if delivered:
                    return {"type": "http.disconnect"}
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = replay_body

        location_id = await _request_location(request, policy)
        try:
            if operator_policy is not None:
                auth_result = authorize_auth_request(
                    request,
                    operator_provider,
                    policy,
                    location_id=location_id,
                )
            elif policy["public"]:
                auth_result = {
                    "authenticated": True,
                    "caller": "anonymous",
                    **policy,
                    "location_id": location_id,
                }
            else:
                auth_result = verify_request(
                    request,
                    resource=policy["resource"],
                    action=policy["action"],
                    location_id=location_id,
                )
        except Exception as exc:
            logger.warning("Gateway authentication backend unavailable (%s)", type(exc).__name__)
            await run_in_threadpool(
                audit.log,
                caller=caller,
                path=request.url.path,
                method=request.method,
                status="error",
                ip=client_ip,
                user_agent=user_agent,
                status_code=503,
                reason="authentication_backend_unavailable",
                resource=policy["resource"],
                action=policy["action"],
                location_id=location_id,
            )
            return JSONResponse(
                status_code=503,
                content={"error": "Authentication service unavailable"},
                headers={"Retry-After": "30"},
            )
        if not auth_result.get("authenticated"):
            denial_status = 403 if auth_result.get("reason") in {
                "api_key_scope_denied", "csrf_validation_failed", "operator_scope_denied",
            } else 401
            await run_in_threadpool(
                audit.log,
                caller=auth_result.get("caller", caller),
                path=request.url.path,
                method=request.method,
                status="denied",
                ip=client_ip,
                user_agent=user_agent,
                reason=auth_result.get("reason", "unauthenticated"),
                status_code=denial_status,
                resource=policy["resource"],
                action=policy["action"],
                location_id=location_id,
                capability_token_id=auth_result.get("capability_token_id"),
                scope_checked=auth_result.get("scope_checked"),
            )
            return JSONResponse(
                status_code=denial_status,
                content={"error": "Unauthorized", "reason": auth_result.get("reason")},
                headers={"Cache-Control": "no-store"},
            )

        request.state.caller = auth_result.get("caller", "anonymous")
        request.state.gateway_authorization = {
            "resource": policy["resource"],
            "action": policy["action"],
            "location_id": location_id,
            "credential_type": auth_result.get("credential_type"),
            "credential_hash": auth_result.get("credential_hash"),
        }

        mutation_reservation = None
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and policy.get("action") != "read":
            mutation_reservation = await run_in_threadpool(audit.reserve_mutation)
            if mutation_reservation is None:
                return JSONResponse(
                    status_code=503,
                    content={"error": "Write operations are temporarily unavailable"},
                    headers={"Retry-After": "30"},
                )

        operator_session_context_token = None
        if operator_policy is not None and auth_result.get("authenticated"):
            operator_session = getattr(request.state, "operator_session", None)
            session_token_hash = getattr(operator_session, "session_token_hash", None)
            if session_token_hash is not None:
                from services.common.tenant_context import bind_operator_session_token_hash

                operator_session_context_token = bind_operator_session_token_hash(
                    session_token_hash
                )

        # Process and audit the request before releasing reserved spool headroom.
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                audit_caller = getattr(
                    request.state, "operator_audit_caller", auth_result.get("caller", caller)
                )
                await run_in_threadpool(
                    audit.log,
                    caller=audit_caller,
                    path=request.url.path,
                    method=request.method,
                    status="error",
                    ip=client_ip,
                    user_agent=user_agent,
                    reason=type(exc).__name__,
                    resource=policy["resource"],
                    action=policy["action"],
                    location_id=location_id,
                    capability_token_id=auth_result.get("capability_token_id"),
                    scope_checked=auth_result.get("scope_checked"),
                )
                raise

            # Audit logging
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            audit_caller = getattr(
                request.state, "operator_audit_caller", auth_result.get("caller", caller)
            )
            await run_in_threadpool(
                audit.log,
                caller=audit_caller,
                path=request.url.path,
                method=request.method,
                status="allowed" if response.status_code < 400 else "denied",
                ip=client_ip,
                user_agent=user_agent,
                duration_ms=duration_ms,
                status_code=response.status_code,
                reason="" if response.status_code < 400 else "handler_response",
                resource=policy["resource"],
                action=policy["action"],
                location_id=location_id,
                capability_token_id=auth_result.get("capability_token_id"),
                scope_checked=auth_result.get("scope_checked"),
            )
            return response
        finally:
            if operator_session_context_token is not None:
                from services.common.tenant_context import reset_operator_session_token_hash

                reset_operator_session_token_hash(operator_session_context_token)
            if mutation_reservation is not None:
                await run_in_threadpool(audit.release_mutation, mutation_reservation)

    @app.middleware("http")
    async def private_report_export_headers(request: Request, call_next):
        """Keep export API success, denial, validation, and error responses private."""
        response = await call_next(request)
        if (
            request.url.path == "/operator/api/report-export-snapshots"
            or request.url.path == "/operator/api/report-exports"
            or request.url.path.startswith("/operator/api/report-exports/")
        ):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
            vary = {
                item.strip()
                for item in response.headers.get("Vary", "").split(",")
                if item.strip()
            }
            vary.add("Cookie")
            response.headers["Vary"] = ", ".join(sorted(vary, key=str.casefold))
        return response

    @app.exception_handler(RequestValidationError)
    async def report_export_validation_error(request: Request, exc: RequestValidationError):
        if request.url.path == "/api/data-stream/post":
            return JSONResponse(
                status_code=422,
                content={"error": "Data Stream post request is invalid"},
                headers={"Cache-Control": "no-store"},
            )
        if (
            request.url.path == "/operator/api/report-export-snapshots"
            or request.url.path == "/operator/api/report-exports"
            or request.url.path.startswith("/operator/api/report-exports/")
        ):
            return JSONResponse(
                status_code=422,
                content={"error": "Report export request is invalid"},
            )
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        from services import __git_sha__, __version__

        return {
            "status": "ok",
            "audit_capture": await run_in_threadpool(audit.capture_status),
            "service": "gateway",
            "version": __version__,
            "git_sha": __git_sha__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Kokonut Intelligence Gateway",
            "version": __import__("services").__version__,
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/mobile", include_in_schema=False)
    async def mobile_companion_canonical_redirect():
        """Normalize the proxy entry URL so relative shell assets stay routed."""
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/mobile/", status_code=308)

    @app.get("/mobile/")
    async def mobile_companion():
        """Serve the standalone field collector companion app."""
        from fastapi.responses import FileResponse

        from services.mobile.api import APP_PATH

        return FileResponse(APP_PATH, media_type="text/html")

    @app.get("/field-collector-vault.js")
    async def field_collector_vault_script():
        """Serve the encryption helper relative to the /mobile entry point."""
        from fastapi.responses import FileResponse

        from services.mobile.api import VAULT_SCRIPT_PATH

        return FileResponse(VAULT_SCRIPT_PATH, media_type="application/javascript")

    @app.get("/field-collector-service-worker.js")
    async def field_collector_service_worker():
        """Serve the offline shell worker relative to the /mobile entry point."""
        from fastapi.responses import FileResponse

        from services.mobile.api import SERVICE_WORKER_PATH

        return FileResponse(SERVICE_WORKER_PATH, media_type="application/javascript")

    @app.get("/mobile/field-collector-vault.js")
    async def mobile_vault_script_alias():
        """Serve the encryption helper when the app is opened with a trailing slash."""
        from fastapi.responses import FileResponse

        from services.mobile.api import VAULT_SCRIPT_PATH

        return FileResponse(VAULT_SCRIPT_PATH, media_type="application/javascript")

    @app.get("/mobile/field-collector-service-worker.js")
    async def mobile_service_worker_alias():
        """Serve the offline shell worker when the app URL has a trailing slash."""
        from fastapi.responses import FileResponse

        from services.mobile.api import SERVICE_WORKER_PATH

        return FileResponse(SERVICE_WORKER_PATH, media_type="application/javascript")

    app.include_router(router, prefix="/api")
    app.include_router(mobile_router, prefix="/api")
    participant_router = APIRouter()
    register_delphi_participant_routes(participant_router, run_in_threadpool, psycopg2)
    app.include_router(participant_router, prefix="/api")
    app.include_router(create_auth_router(operator_provider))

    if operator_provider is not None:
        from starlette.middleware.sessions import SessionMiddleware

        app.add_middleware(
            SessionMiddleware,
            secret_key=operator_provider.settings.state_secret,
            session_cookie="kokonut_operator_oidc_state",
            max_age=600,
            same_site="lax",
            https_only=True,
            path="/operator/auth",
        )

    # Add CORS last so it wraps the gateway and also decorates auth, rate-limit,
    # and request-size responses. No origins are trusted unless explicitly set.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type", "Authorization", "api-key", "x-api-key",
            "capability-token", "x-capability-token", "x-csrf-token",
            "x-device-token", "x-collection-client-id", "x-collection-type",
            "x-form-id", "x-form-version", "x-participant-ref", "x-collected-at",
        ],
        allow_credentials=operator_provider is not None,
    )

    original_openapi = app.openapi

    def openapi_with_operator_session_security():
        """Describe the middleware-enforced session cookie on private operator APIs."""
        schema = app.openapi_schema or original_openapi()
        security_schemes = schema.setdefault("components", {}).setdefault(
            "securitySchemes", {}
        )
        security_schemes["OperatorSessionCookie"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": SESSION_COOKIE,
            "description": "HTTP-only OIDC operator session cookie.",
        }
        for path, path_item in schema.get("paths", {}).items():
            for method, operation in path_item.items():
                method = method.lower()
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                private_operator_api = path.startswith("/operator/api/")
                private_auth_session = (
                    (path == "/operator/auth/session" and method == "get")
                    or (path == "/operator/auth/logout" and method == "post")
                )
                if private_operator_api or private_auth_session:
                    operation["security"] = [{"OperatorSessionCookie": []}]

        app.openapi_schema = schema
        return schema

    app.openapi = openapi_with_operator_session_security

    logger.info("Gateway application created")
    return app
