"""TLS trust configuration for the optional gRPC health client."""

from __future__ import annotations

import sys
from unittest.mock import Mock

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from services.core.adapters import grpc as grpc_adapter


def test_health_uses_secure_channel_and_closes_it_with_explicit_ca(tmp_path, monkeypatch):
    ca_file = tmp_path / "health-ca.pem"
    ca_file.write_bytes(b"synthetic CA bundle")
    channel = Mock()
    stub = Mock()
    stub.Check.return_value = health_pb2.HealthCheckResponse(
        status=health_pb2.HealthCheckResponse.SERVING
    )
    credentials = object()
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    monkeypatch.setattr(grpc, "ssl_channel_credentials", Mock(return_value=credentials))
    secure_channel = Mock(return_value=channel)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)
    monkeypatch.setattr(health_pb2_grpc, "HealthStub", lambda _channel: stub)

    status = grpc_adapter.check_health("grpc.internal:50051", tls_ca_path=str(ca_file))

    assert status == health_pb2.HealthCheckResponse.SERVING
    grpc.ssl_channel_credentials.assert_called_once_with(root_certificates=b"synthetic CA bundle")
    secure_channel.assert_called_once_with("grpc.internal:50051", credentials)
    stub.Check.assert_called_once()
    channel.close.assert_called_once_with()


def test_health_uses_environment_ca_for_tls_server(monkeypatch, tmp_path):
    ca_file = tmp_path / "health-ca.pem"
    ca_file.write_bytes(b"environment CA")
    channel = Mock()
    stub = Mock()
    stub.Check.return_value = health_pb2.HealthCheckResponse(
        status=health_pb2.HealthCheckResponse.SERVING
    )
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", "/mounted/server.pem")
    monkeypatch.setenv("GRPC_TLS_KEY", "/mounted/server-key.pem")
    monkeypatch.setenv("GRPC_TLS_CA", str(ca_file))
    monkeypatch.setattr(grpc, "ssl_channel_credentials", Mock(return_value=object()))
    insecure_channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", Mock(return_value=channel))
    monkeypatch.setattr(health_pb2_grpc, "HealthStub", lambda _channel: stub)

    grpc_adapter.check_health("localhost:50051")

    grpc.secure_channel.assert_called_once()
    insecure_channel.assert_not_called()
    channel.close.assert_called_once_with()


def test_health_fails_closed_when_server_tls_has_no_ca(monkeypatch):
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", "/mounted/server.pem")
    monkeypatch.setenv("GRPC_TLS_KEY", "/mounted/server-key.pem")
    monkeypatch.delenv("GRPC_TLS_CA", raising=False)
    insecure_channel = Mock()
    secure_channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    with pytest.raises(RuntimeError, match="GRPC_TLS_CA is required"):
        grpc_adapter.check_health("localhost:50051")

    insecure_channel.assert_not_called()
    secure_channel.assert_not_called()


def test_health_missing_ca_file_does_not_echo_path_or_open_channel(tmp_path, monkeypatch):
    missing_ca = tmp_path / "private-ca-path.pem"
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    secure_channel = Mock()
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    with pytest.raises(RuntimeError, match="TLS trust file is unavailable") as error:
        grpc_adapter.check_health("localhost:50051", tls_ca_path=str(missing_ca))

    assert str(missing_ca) not in str(error.value)
    secure_channel.assert_not_called()


def test_health_cli_forwards_tls_ca_argument(monkeypatch, capsys):
    check_health = Mock(return_value=health_pb2.HealthCheckResponse.SERVING)
    monkeypatch.setattr("services.core.adapters.grpc.check_health", check_health)
    monkeypatch.setattr(
        sys,
        "argv",
        ["kokonut-grpc", "health", "--target", "grpc.internal:50051", "--tls-ca", "/ca.pem"],
    )

    from services.grpc.cli import main

    main()

    check_health.assert_called_once_with(
        "grpc.internal:50051", tls_ca_path="/ca.pem", allow_insecure=False
    )
    assert "Status:" in capsys.readouterr().out


def test_health_rejects_plaintext_for_non_loopback_target(monkeypatch):
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    for name in ("GRPC_TLS_CERT", "GRPC_TLS_KEY", "GRPC_TLS_CA"):
        monkeypatch.delenv(name, raising=False)
    insecure_channel = Mock()
    secure_channel = Mock()
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", secure_channel)

    with pytest.raises(RuntimeError, match="non-loopback targets require GRPC_TLS_CA"):
        grpc_adapter.check_health("grpc.internal:50051")

    insecure_channel.assert_not_called()
    secure_channel.assert_not_called()


def test_health_allows_explicit_insecure_private_target(monkeypatch):
    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    for name in ("GRPC_TLS_CERT", "GRPC_TLS_KEY", "GRPC_TLS_CA"):
        monkeypatch.delenv(name, raising=False)
    channel = Mock()
    stub = Mock()
    stub.Check.return_value = health_pb2.HealthCheckResponse(
        status=health_pb2.HealthCheckResponse.SERVING
    )
    insecure_channel = Mock(return_value=channel)
    monkeypatch.setattr(grpc, "insecure_channel", insecure_channel)
    monkeypatch.setattr(grpc, "secure_channel", Mock())
    monkeypatch.setattr(health_pb2_grpc, "HealthStub", lambda _channel: stub)

    status = grpc_adapter.check_health("grpc.internal:50051", allow_insecure=True)

    assert status == health_pb2.HealthCheckResponse.SERVING
    insecure_channel.assert_called_once_with("grpc.internal:50051")
    channel.close.assert_called_once_with()
