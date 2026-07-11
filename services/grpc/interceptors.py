"""gRPC logging interceptor."""

from __future__ import annotations

import time

import grpc

from services.common.logging import get_logger

logger = get_logger("grpc.interceptor")


class LoggingInterceptor(grpc.ServerInterceptor):
    """Logs all gRPC requests with timing."""

    def intercept_service(self, continuation, handler_call_details):
        method = handler_call_details.method
        start = time.time()

        try:
            response = continuation(handler_call_details)
            elapsed = time.time() - start
            logger.info("gRPC %s completed in %.3fs", method, elapsed)
            return response
        except Exception as e:
            elapsed = time.time() - start
            logger.error("gRPC %s failed after %.3fs: %s", method, elapsed, e)
            raise
