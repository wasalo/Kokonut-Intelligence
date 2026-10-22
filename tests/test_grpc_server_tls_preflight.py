"""gRPC TLS configuration fails before allocating the database pool."""

from __future__ import annotations

from unittest.mock import Mock

import grpc
import pytest

from services.grpc import server


def test_incomplete_tls_pair_fails_before_database_pool(monkeypatch):
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", "/private/cert.pem")
    monkeypatch.delenv("GRPC_TLS_KEY", raising=False)
    get_db_pool = Mock()
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)

    with pytest.raises(ValueError, match="Both GRPC_TLS_CERT and GRPC_TLS_KEY"):
        server.serve()

    get_db_pool.assert_not_called()


def test_missing_tls_file_is_redacted_and_fails_before_database_pool(monkeypatch, tmp_path):
    private_path = tmp_path / "secret-certificate-path.pem"
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", str(private_path))
    monkeypatch.setenv("GRPC_TLS_KEY", str(tmp_path / "secret-key-path.pem"))
    get_db_pool = Mock()
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)

    with pytest.raises(RuntimeError, match="TLS certificate or key file is unavailable") as error:
        server.serve()

    assert str(private_path) not in str(error.value)
    get_db_pool.assert_not_called()


def test_invalid_tls_credentials_are_redacted_and_fail_before_database_pool(
    monkeypatch, tmp_path
):
    cert_file = tmp_path / "server.pem"
    key_file = tmp_path / "server-key.pem"
    cert_file.write_bytes(b"synthetic certificate")
    key_file.write_bytes(b"synthetic private key")
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", str(cert_file))
    monkeypatch.setenv("GRPC_TLS_KEY", str(key_file))
    credential_factory = Mock(side_effect=ValueError("private detail"))
    monkeypatch.setattr(grpc, "ssl_server_credentials", credential_factory)
    get_db_pool = Mock()
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)

    with pytest.raises(RuntimeError, match=r"TLS credentials are invalid \(ValueError\)") as error:
        server.serve()

    assert "private detail" not in str(error.value)
    assert str(cert_file) not in str(error.value)
    get_db_pool.assert_not_called()


def test_valid_tls_credentials_are_loaded_before_database_pool(monkeypatch, tmp_path):
    cert_file = tmp_path / "server.pem"
    key_file = tmp_path / "server-key.pem"
    cert_file.write_bytes(b"synthetic certificate")
    key_file.write_bytes(b"synthetic private key")
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.setenv("GRPC_TLS_CERT", str(cert_file))
    monkeypatch.setenv("GRPC_TLS_KEY", str(key_file))

    events = []
    credentials = object()
    db_factory = Mock()
    executor = Mock()
    credential_factory = Mock(
        side_effect=lambda identities: events.append(("credentials", identities)) or credentials
    )
    get_db_pool = Mock(side_effect=lambda: events.append(("pool", None)) or db_factory)
    run_transport = Mock(
        side_effect=lambda *args, **kwargs: events.append(("transport", kwargs.get("tls_credentials")))
    )
    monkeypatch.setattr(grpc, "ssl_server_credentials", credential_factory)
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)
    monkeypatch.setattr(server, "_serve_transport", run_transport)
    monkeypatch.setattr(server.futures, "ThreadPoolExecutor", Mock(return_value=executor))

    server.serve()

    assert events == [
        ("credentials", [(b"synthetic private key", b"synthetic certificate")]),
        ("pool", None),
        ("transport", credentials),
    ]
    db_factory.close.assert_called_once_with()
    executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
