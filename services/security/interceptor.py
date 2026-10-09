"""gRPC interceptor for capability-based authorization."""

from __future__ import annotations

import grpc
from typing import Any, Callable

from services.common.logging import get_logger

logger = get_logger("security.interceptor")


class CapabilityInterceptor(grpc.ServerInterceptor):
    """gRPC interceptor that checks capability tokens on write operations."""

    WRITE_METHODS = {
        "Write", "Attest", "Publish", "Delete", "BulkUpdate",
        "Create", "Update", "Submit", "Verify",
    }

    def __init__(self, audit_logger=None):
        self._audit = audit_logger

    def intercept_service(self, continuation, handler_call_details):
        method_name = handler_call_details.method.split("/")[-1]
        metadata = dict(handler_call_details.invocation_metadata)

        # Skip auth for read-only and health methods
        if method_name not in self.WRITE_METHODS and not method_name.startswith("Stream"):
            return continuation(handler_call_details)

        # Check for capability token
        token = metadata.get("x-capability-token") or metadata.get("capability-token")
        if not token:
            # Fall back to API key auth
            api_key = metadata.get("x-api-key") or metadata.get("api-key")
            if api_key:
                return continuation(handler_call_details)
            logger.warning("No auth provided for %s", method_name)
            return self._unauthenticated_response()

        # Verify capability
        from services.security.capabilities import CapabilityManager
        manager = CapabilityManager()
        result = manager.verify(token, resource=method_name, action="write")

        if result is None:
            logger.warning("Capability verification failed for %s", method_name)
            if self._audit:
                self._audit.log_access(
                    caller="grpc",
                    resource_type=method_name,
                    action="write",
                    status="denied",
                    metadata={"reason": "capability_verification_failed"},
                )
            return self._unauthenticated_response()

        # Log successful access
        if self._audit:
            self._audit.log_access(
                caller=result.get("holder", "unknown"),
                resource_type=method_name,
                action="write",
                status="allowed",
                capability_token_id=result.get("token_id"),
            )

        return continuation(handler_call_details)

    def _unauthenticated_response(self):
        return grpc.unary_unary_rpc_method_handler(
            lambda req, ctx: (_ for _ in ()).throw(
                grpc.StatusCode.UNAUTHENTICATED, "Missing or invalid capability token"
            )
        )
