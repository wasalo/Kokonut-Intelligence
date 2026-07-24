"""Gateway application — FastAPI app with auth, routing, rate limiting, and audit."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from services.common.logging import get_logger

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


def create_app():
    """Create the FastAPI gateway application."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")

    from services.gateway.audit import GatewayAudit
    from services.gateway.auth import verify_request
    from services.gateway.rate_limiter import RateLimiter
    from services.gateway.router import get_route_policy, router
    from services.mobile.api import router as mobile_router

    app = FastAPI(
        title="Kokonut Intelligence Gateway",
        version="1.0.0",
        description="Unified API gateway for the Kokonut Intelligence platform",
    )
    cors_origins = [
        origin.strip()
        for origin in os.environ.get("CORS_ORIGIN", "*").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "x-api-key", "x-capability-token", "x-device-token"],
    )

    rate_limiter = RateLimiter()
    audit = GatewayAudit()

    @app.middleware("http")
    async def gateway_middleware(request: Request, call_next):
        """Global middleware for auth, rate limiting, and audit."""
        start_time = datetime.now(timezone.utc)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        # Rate limiting
        caller = _request_identity(request, client_ip)
        allowed = rate_limiter.check(caller)
        if not allowed:
            audit.log(
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
                headers={"Retry-After": str(rate_limiter.retry_after(caller))},
            )

        policy = get_route_policy(request.method, request.url.path)
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
            audit.log(
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
            )
            return JSONResponse(
                status_code=denial_status,
                content={"error": "Unauthorized", "reason": auth_result.get("reason")},
            )

        request.state.caller = auth_result.get("caller", "anonymous")

        # Process request, retaining an audit record if the handler fails.
        try:
            response = await call_next(request)
        except Exception as exc:
            audit.log(
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
            )
            raise

        # Audit logging
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        audit.log(
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
        )

        return response

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "gateway", "timestamp": datetime.now(timezone.utc).isoformat()}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "service": "Kokonut Intelligence Gateway",
            "version": "1.0.0",
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

    app.include_router(router, prefix="/api")
    app.include_router(mobile_router, prefix="/api")

    logger.info("Gateway application created")
    return app
