"""Lazy application boundary for the existing gRPC transport package."""

from __future__ import annotations


def require_enabled() -> None:
    from services.core.providers import ProviderSettings

    if not ProviderSettings.from_environment().grpc:
        raise RuntimeError("gRPC provider disabled; set KOKONUT_FEATURE_GRPC=true to enable it")


def serve() -> None:
    require_enabled()
    from services.grpc.server import serve as run_server

    run_server()


def check_health(target: str) -> int:
    """Return the existing gRPC health status, closing the channel on failure."""
    require_enabled()
    import grpc
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    channel = grpc.insecure_channel(target)
    try:
        stub = health_pb2_grpc.HealthStub(channel)
        response = stub.Check(health_pb2.HealthCheckRequest(), timeout=5, wait_for_ready=True)
        if response.status != health_pb2.HealthCheckResponse.SERVING:
            raise RuntimeError(f"Health check returned non-serving status: {response.status}")
        return response.status
    except grpc.RpcError as error:
        raise RuntimeError(f"Health check failed: {error}") from error
    finally:
        channel.close()
