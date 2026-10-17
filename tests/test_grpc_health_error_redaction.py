"""The optional gRPC health adapter must not echo remote diagnostics."""

from unittest.mock import Mock

import grpc
import pytest
from grpc_health.v1 import health_pb2_grpc

from services.core.adapters import grpc as grpc_adapter

DIAGNOSTIC = "synthetic remote health diagnostic marker"


class _RemoteHealthFailure(grpc.RpcError):
    def __str__(self):
        return DIAGNOSTIC


def test_health_rpc_error_is_redacted_and_channel_is_closed(monkeypatch):
    channel = Mock()
    stub = Mock()
    stub.Check.side_effect = _RemoteHealthFailure()

    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    monkeypatch.setattr(grpc, "insecure_channel", lambda _target: channel)
    monkeypatch.setattr(health_pb2_grpc, "HealthStub", lambda _channel: stub)

    with pytest.raises(RuntimeError, match="Health check failed \\(_RemoteHealthFailure\\)") as error:
        grpc_adapter.check_health("synthetic-target")

    assert DIAGNOSTIC not in str(error.value)
    channel.close.assert_called_once_with()
