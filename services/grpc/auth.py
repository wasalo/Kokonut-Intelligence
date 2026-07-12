"""API key authentication interceptor for gRPC."""

from __future__ import annotations

import contextvars
import hashlib
from concurrent import futures
from datetime import datetime, timezone

import grpc

from services.common.logging import get_logger

logger = get_logger("grpc.auth")

# Context variable to propagate auth info to downstream handlers
grpc_auth_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar("grpc_auth_context", default=None)


class APIKeyInterceptor(grpc.ServerInterceptor):
    """Validates API keys against the api_key table via metadata."""

    EXEMPT_METHODS = {
        "grpc.health.v1.Health/Check",
        "grpc.reflection.v1alpha.ServerReflection/ServerReflectionInfo",
    }

    def __init__(self, db_factory):
        self._db_factory = db_factory

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        if method in self.EXEMPT_METHODS:
            return continuation(handler_call_details)

        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get("x-api-key", "")

        if not api_key:
            return _abort(grpc.StatusCode.UNAUTHENTICATED, "Missing x-api-key metadata")

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        try:
            conn = self._db_factory()
            try:
                result = conn.execute(
                    conn.text(
                        "SELECT ak.id, ak.is_active, ak.expires_at, ak.scopes, "
                        "ar.name AS role_name, ar.permissions "
                        "FROM api_key ak "
                        "LEFT JOIN app_role ar ON ar.id = ak.role_id "
                        "WHERE ak.key_hash = :hash"
                    ),
                    {"hash": key_hash},
                ).mappings().first()
            finally:
                conn.close()
        except Exception as e:
            logger.error("API key lookup failed: %s", e)
            return _abort(grpc.StatusCode.INTERNAL, "Authentication service error")

        if not result:
            return _abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid API key")

        if not result["is_active"]:
            return _abort(grpc.StatusCode.PERMISSION_DENIED, "API key is deactivated")

        if result["expires_at"] and result["expires_at"] < datetime.now(timezone.utc):
            return _abort(grpc.StatusCode.PERMISSION_DENIED, "API key has expired")

        # Propagate auth context via contextvars
        auth_info = {
            "api_key_id": str(result["id"]),
            "role_name": result.get("role_name"),
            "scopes": result.get("scopes") or [],
        }
        token = grpc_auth_context.set(auth_info)
        try:
            return continuation(handler_call_details)
        finally:
            grpc_auth_context.reset(token)


def get_current_auth() -> dict | None:
    """Get the current gRPC authentication context (for use in service handlers)."""
    return grpc_auth_context.get()


def _abort(code: grpc.StatusCode, message: str):
    def abort_handler(request, context):
        context.abort(code, message)
    return grpc.unary_unary_rpc_method_handler(
        abort_handler,
        request_deserializer=None,
        response_serializer=None,
    )
