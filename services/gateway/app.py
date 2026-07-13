"""Gateway application — FastAPI app with auth, routing, rate limiting, and audit."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from services.common.logging import get_logger

logger = get_logger("gateway.app")


def create_app():
    """Create the FastAPI gateway application."""
    try:
        from fastapi import FastAPI, Request, HTTPException, Depends
        from fastapi.responses import JSONResponse
    except ImportError:
        raise ImportError("FastAPI is required: pip install fastapi uvicorn")

    from services.gateway.auth import verify_request
    from services.gateway.rate_limiter import RateLimiter
    from services.gateway.audit import GatewayAudit
    from services.gateway.router import get_route_policy, router

    app = FastAPI(
        title="Kokonut Intelligence Gateway",
        version="1.0.0",
        description="Unified API gateway for the Kokonut Intelligence platform",
    )

    rate_limiter = RateLimiter()
    audit = GatewayAudit()

    @app.middleware("http")
    async def gateway_middleware(request: Request, call_next):
        """Global middleware for auth, rate limiting, and audit."""
        start_time = datetime.now(timezone.utc)
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        # Health and API discovery are intentionally public.
        if request.url.path in ("/health", "/docs", "/openapi.json", "/"):
            response = await call_next(request)
            return response

        # Rate limiting
        caller = request.headers.get("x-api-key", client_ip)
        allowed = rate_limiter.check(caller)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
            )

        policy = get_route_policy(request.method, request.url.path)
        auth_result = (
            {"authenticated": True, "caller": "anonymous"}
            if policy["public"]
            else verify_request(
                request,
                resource=policy["resource"],
                action=policy["action"],
                location_id=policy["location_id"],
            )
        )
        if not auth_result.get("authenticated"):
            audit.log(
                caller=caller,
                path=request.url.path,
                method=request.method,
                status="denied",
                ip=client_ip,
                user_agent=user_agent,
                reason=auth_result.get("reason", "unauthenticated"),
            )
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "reason": auth_result.get("reason")},
            )

        request.state.caller = auth_result.get("caller", "anonymous")

        # Process request
        response = await call_next(request)

        # Audit logging
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        audit.log(
            caller=auth_result.get("caller", caller),
            path=request.url.path,
            method=request.method,
            status="allowed" if response.status_code < 400 else "error",
            ip=client_ip,
            user_agent=user_agent,
            duration_ms=duration_ms,
            status_code=response.status_code,
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

    app.include_router(router, prefix="/api")

    logger.info("Gateway application created")
    return app
