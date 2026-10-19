"""API key authentication interceptor for gRPC."""

from __future__ import annotations

import contextvars
import hashlib
from datetime import datetime, timezone

import grpc

from services.common.errors import safe_exception_class
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
        method = handler_call_details.method.lstrip("/")
        handler = continuation(handler_call_details)
        if handler is None:
            return None
        if method in self.EXEMPT_METHODS:
            return handler

        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get("x-api-key", "")

        if not api_key:
            return _abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "Missing x-api-key metadata",
                handler,
            )

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        try:
            conn = self._db_factory()
            try:
                result = (
                    conn.execute(
                        conn.text(
                            "SELECT ak.id, ak.is_active, ak.expires_at, ak.scopes, "
                            "ar.name AS role_name, ar.permissions "
                            "FROM api_key ak "
                            "LEFT JOIN app_role ar ON ar.id = ak.role_id "
                            "WHERE ak.key_hash = :hash"
                        ),
                        {"hash": key_hash},
                    )
                    .mappings()
                    .first()
                )
            finally:
                self._db_factory.release(conn)
        except Exception as e:
            logger.error("API key lookup failed (%s)", safe_exception_class(e))
            return _abort(
                grpc.StatusCode.INTERNAL,
                "Authentication service error",
                handler,
            )

        if not result:
            return _abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid API key", handler)

        if not result["is_active"]:
            return _abort(
                grpc.StatusCode.PERMISSION_DENIED,
                "API key is deactivated",
                handler,
            )

        if result["expires_at"] and result["expires_at"] < datetime.now(timezone.utc):
            return _abort(
                grpc.StatusCode.PERMISSION_DENIED,
                "API key has expired",
                handler,
            )

        # Propagate auth context via contextvars
        auth_info = {
            "api_key_id": str(result["id"]),
            "role_name": result.get("role_name"),
            "scopes": result.get("scopes") or [],
        }
        return _authenticated_handler(handler, auth_info)


def get_current_auth() -> dict | None:
    """Get the current gRPC authentication context (for use in service handlers)."""
    return grpc_auth_context.get()


def require_scope(context, resource: str, action: str) -> None:
    """Abort the current RPC if the caller lacks the required scope.

    Call this at the top of each service method:
        require_scope(context, "ecocredit:class", "read")

    Aborts with PERMISSION_DENIED if the scope is missing.
    """
    auth = get_current_auth()
    if auth is None:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Not authenticated")
    scopes = auth.get("scopes") or []
    if not isinstance(scopes, (list, tuple)):
        scopes = []
    for scope in scopes:
        if not isinstance(scope, str) or ":" not in scope:
            continue
        scope_resource, scope_action = scope.rsplit(":", 1)
        if not scope_resource or not scope_action:
            continue
        if scope_resource in ("*", resource) and scope_action in ("*", action):
            return
    context.abort(
        grpc.StatusCode.PERMISSION_DENIED,
        f"Scope '{resource}:{action}' required but not granted",
    )


def _authenticated_handler(handler, auth_info):
    """Bind identity during actual invocation, retaining wire codecs/cardinality."""
    if handler.request_streaming:
        behavior = handler.stream_stream if handler.response_streaming else handler.stream_unary
        builder = (
            grpc.stream_stream_rpc_method_handler
            if handler.response_streaming
            else grpc.stream_unary_rpc_method_handler
        )
    else:
        behavior = handler.unary_stream if handler.response_streaming else handler.unary_unary
        builder = (
            grpc.unary_stream_rpc_method_handler if handler.response_streaming else grpc.unary_unary_rpc_method_handler
        )

    def invoke(request, context):
        token = grpc_auth_context.set(auth_info)
        try:
            return behavior(request, context)
        finally:
            grpc_auth_context.reset(token)

    def stream(request, context):
        token = grpc_auth_context.set(auth_info)
        try:
            iterator = iter(behavior(request, context))
        finally:
            grpc_auth_context.reset(token)

        try:
            while True:
                token = grpc_auth_context.set(auth_info)
                try:
                    response = next(iterator)
                except StopIteration:
                    return
                finally:
                    grpc_auth_context.reset(token)
                yield response
        finally:
            close = getattr(iterator, "close", None)
            if close is not None:
                token = grpc_auth_context.set(auth_info)
                try:
                    close()
                finally:
                    grpc_auth_context.reset(token)

    return builder(
        stream if handler.response_streaming else invoke,
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )


def _abort(code: grpc.StatusCode, message: str, handler):
    """Reject an RPC without changing its registered streaming cardinality."""
    if handler.request_streaming:
        behavior = handler.stream_stream if handler.response_streaming else handler.stream_unary
        builder = (
            grpc.stream_stream_rpc_method_handler
            if handler.response_streaming
            else grpc.stream_unary_rpc_method_handler
        )
    else:
        behavior = handler.unary_stream if handler.response_streaming else handler.unary_unary
        builder = (
            grpc.unary_stream_rpc_method_handler
            if handler.response_streaming
            else grpc.unary_unary_rpc_method_handler
        )

    if handler.response_streaming:
        def abort_stream(request, context):
            context.abort(code, message)
            yield None

        behavior = abort_stream
    else:
        def abort_unary(request, context):
            context.abort(code, message)

        behavior = abort_unary

    return builder(
        behavior,
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )
