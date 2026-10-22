"""Lazy application boundary for the existing gRPC transport package."""

from __future__ import annotations

import os

from services.common.errors import safe_exception_class


def require_enabled() -> None:
    from services.core.providers import ProviderSettings

    if not ProviderSettings.from_environment().grpc:
        raise RuntimeError("gRPC provider disabled; set KOKONUT_FEATURE_GRPC=true to enable it")


def serve() -> None:
    require_enabled()
    from services.grpc.server import serve as run_server

    run_server()


def check_health(target: str, tls_ca_path: str | None = None) -> int:
    """Return gRPC health, using a configured CA for TLS and closing the channel."""
    require_enabled()
    import grpc
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    tls_ca_path = tls_ca_path or os.environ.get("GRPC_TLS_CA")
    server_tls_configured = bool(
        os.environ.get("GRPC_TLS_CERT") or os.environ.get("GRPC_TLS_KEY")
    )
    if server_tls_configured and not tls_ca_path:
        raise RuntimeError("GRPC_TLS_CA is required when gRPC server TLS is configured")

    if tls_ca_path:
        from pathlib import Path

        try:
            root_certificates = Path(tls_ca_path).read_bytes()
        except OSError as error:
            raise RuntimeError("gRPC health TLS trust file is unavailable") from error
        try:
            credentials = grpc.ssl_channel_credentials(root_certificates=root_certificates)
        except Exception as error:
            raise RuntimeError(
                f"gRPC health TLS configuration failed ({safe_exception_class(error)})"
            ) from error
        channel = grpc.secure_channel(target, credentials)
    else:
        channel = grpc.insecure_channel(target)
    try:
        stub = health_pb2_grpc.HealthStub(channel)
        response = stub.Check(health_pb2.HealthCheckRequest(), timeout=5, wait_for_ready=True)
        if response.status != health_pb2.HealthCheckResponse.SERVING:
            raise RuntimeError(f"Health check returned non-serving status: {response.status}")
        return response.status
    except grpc.RpcError as error:
        raise RuntimeError(
            f"Health check failed ({safe_exception_class(error)})"
        ) from error
    finally:
        channel.close()
