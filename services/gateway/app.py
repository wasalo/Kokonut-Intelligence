"""Gateway application — FastAPI app with auth, routing, rate limiting, and audit."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
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
    )
    if credential:
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()[:16]
        return f"credential:{digest}"
    return f"ip:{client_ip}"


async def _request_location(request, policy: dict) -> str | None:
    """Resolve a route's location scope, including data-stream request bodies."""
    if policy.get("location_id"):
        return policy["location_id"]
    if policy.get("resource") != "data_stream_post":
        return None
    try:
        body = await request.body()
        request._body = body
        payload = json.loads(body or b"{}")
        return payload.get("location_id")
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None


def create_app(*, rate_limiter: RateLimitBackend | None = None):
    """Create the FastAPI gateway application."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
        from starlette.concurrency import run_in_threadpool
    except ImportError:
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")

    from services.gateway.audit import GatewayAudit
    from services.gateway.auth import verify_request
    from services.gateway.router import get_route_policy, router
    from services.mobile.api import router as mobile_router

    app = FastAPI(
        title="Kokonut Intelligence Gateway",
        version="1.0.0",
        description="Unified API gateway for the Kokonut Intelligence platform",
    )
    cors_origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGIN", "").split(",")
        if origin.strip()
    ]
    if "*" in cors_origins:
        logger.warning("Ignoring wildcard CORS origin; configure explicit trusted origins")
        cors_origins = [origin for origin in cors_origins if origin != "*"]

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

    @app.on_event("startup")
    async def start_audit_replay():
        nonlocal audit_replay_task
        audit_replay_task = asyncio.create_task(audit_replay_loop())

    @app.on_event("shutdown")
    async def stop_audit_replay():
        nonlocal audit_replay_task
        if audit_replay_task is not None:
            audit_replay_task.cancel()
            try:
                await audit_replay_task
            except asyncio.CancelledError:
                pass
            audit_replay_task = None

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

        policy = get_route_policy(request.method, request.url.path)
        max_body_bytes = 2_000_000 if request.url.path == "/api/mobile/media/uploads" else 8_000_000
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
        auth_result = {"authenticated": True, "caller": "anonymous", **policy, "location_id": location_id} \
            if policy["public"] else verify_request(
                request,
                resource=policy["resource"],
                action=policy["action"],
                location_id=location_id,
            )
        if not auth_result.get("authenticated"):
            denial_status = 403 if auth_result.get("reason") == "api_key_scope_denied" else 401
            await run_in_threadpool(
                audit.log,
                caller=caller,
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
            )

        request.state.caller = auth_result.get("caller", "anonymous")

        mutation_reservation = None
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and policy.get("action") != "read":
            mutation_reservation = await run_in_threadpool(audit.reserve_mutation)
            if mutation_reservation is None:
                return JSONResponse(
                    status_code=503,
                    content={"error": "Write operations are temporarily unavailable"},
                    headers={"Retry-After": "30"},
                )

        # Process and audit the request before releasing reserved spool headroom.
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                await run_in_threadpool(
                    audit.log,
                    caller=auth_result.get("caller", caller),
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
            await run_in_threadpool(
                audit.log,
                caller=auth_result.get("caller", caller),
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
            if mutation_reservation is not None:
                await run_in_threadpool(audit.release_mutation, mutation_reservation)

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

    @app.get("/mobile")
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

    @app.get("/mobile/field-collector-vault.js")
    async def mobile_vault_script_alias():
        """Serve the encryption helper when the app is opened with a trailing slash."""
        from fastapi.responses import FileResponse

        from services.mobile.api import VAULT_SCRIPT_PATH

        return FileResponse(VAULT_SCRIPT_PATH, media_type="application/javascript")

    app.include_router(router, prefix="/api")
    app.include_router(mobile_router, prefix="/api")

    # Add CORS last so it wraps the gateway and also decorates auth, rate-limit,
    # and request-size responses. No origins are trusted unless explicitly set.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type", "Authorization", "x-api-key", "x-capability-token",
            "x-device-token", "x-collection-client-id",
        ],
    )

    logger.info("Gateway application created")
    return app
