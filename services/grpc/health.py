"""gRPC health check service."""

from __future__ import annotations

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


class HealthServicer(health_pb2_grpc.HealthServicer):
    """gRPC health check implementation."""

    def Check(self, request, context):
        from grpc_health.v1.health_pb2 import HealthCheckResponse
        return HealthCheckResponse(
            status=HealthCheckResponse.SERVING
        )

    def Watch(self, request, context):
        from grpc_health.v1.health_pb2 import HealthCheckResponse
        from services.common.logging import get_logger
        import time

        logger = get_logger("grpc.health")
        logger.info("Health Watch stream opened for service: %s", request.service or "all")

        try:
            yield HealthCheckResponse(
                status=HealthCheckResponse.SERVING
            )
            while context.is_active():
                time.sleep(10)
                yield HealthCheckResponse(
                    status=HealthCheckResponse.SERVING
                )
        except grpc.RpcError:
            pass
