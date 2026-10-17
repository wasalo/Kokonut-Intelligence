"""A disabled gRPC transport must not import its optional dependencies."""

import sys

import pytest

from services.core.adapters import grpc as grpc_adapter


@pytest.mark.parametrize(
    ("operation", "blocked_modules"),
    [
        ("serve", ("grpc", "services.grpc.server")),
        (
            "health",
            (
                "grpc",
                "grpc_health",
                "grpc_health.v1",
                "grpc_health.v1.health_pb2",
                "grpc_health.v1.health_pb2_grpc",
            ),
        ),
    ],
)
def test_disabled_provider_fails_before_optional_imports(monkeypatch, operation, blocked_modules):
    monkeypatch.setenv("KOKONUT_FEATURE_GRPC", "false")
    for module in blocked_modules:
        monkeypatch.setitem(sys.modules, module, None)

    with pytest.raises(RuntimeError, match="gRPC provider disabled"):
        if operation == "serve":
            grpc_adapter.serve()
        else:
            grpc_adapter.check_health("127.0.0.1:50051")
