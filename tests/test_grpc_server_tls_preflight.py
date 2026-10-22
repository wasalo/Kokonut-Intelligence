"""gRPC TLS configuration fails before allocating the database pool."""

from __future__ import annotations

from pathlib import Path
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


@pytest.mark.parametrize("setting", [None, "false"])
def test_missing_tls_fails_closed_before_database_pool(monkeypatch, setting):
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.delenv("GRPC_TLS_CERT", raising=False)
    monkeypatch.delenv("GRPC_TLS_KEY", raising=False)
    if setting is None:
        monkeypatch.delenv("GRPC_ALLOW_INSECURE", raising=False)
    else:
        monkeypatch.setenv("GRPC_ALLOW_INSECURE", setting)
    get_db_pool = Mock()
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)

    with pytest.raises(ValueError, match="gRPC TLS is required"):
        server.serve()

    get_db_pool.assert_not_called()


def test_invalid_insecure_setting_fails_before_database_pool(monkeypatch):
    monkeypatch.setattr("services.core.adapters.grpc.require_enabled", lambda: None)
    monkeypatch.delenv("GRPC_TLS_CERT", raising=False)
    monkeypatch.delenv("GRPC_TLS_KEY", raising=False)
    monkeypatch.setenv("GRPC_ALLOW_INSECURE", "yes")
    get_db_pool = Mock()
    monkeypatch.setattr(server, "_get_db_pool", get_db_pool)

    with pytest.raises(ValueError, match="GRPC_ALLOW_INSECURE must be true or false"):
        server.serve()

    get_db_pool.assert_not_called()


def test_explicit_private_network_opt_in_allows_plaintext(monkeypatch):
    monkeypatch.setenv("GRPC_ALLOW_INSECURE", "true")
    monkeypatch.delenv("GRPC_TLS_CERT", raising=False)
    monkeypatch.delenv("GRPC_TLS_KEY", raising=False)

    assert server._configured_tls_credentials() is None


def test_compose_profiles_make_plaintext_policy_explicit():
    import yaml

    root = Path(__file__).resolve().parents[1]
    base = yaml.safe_load((root / "docker-compose.yml").read_text())
    production = yaml.safe_load((root / "docker-compose.prod.yml").read_text())
    kernel_grpc = yaml.safe_load((root / "docker-compose.kernel-grpc.yml").read_text())

    assert base["services"]["grpc"]["environment"]["GRPC_ALLOW_INSECURE"] == (
        "${GRPC_ALLOW_INSECURE:-true}"
    )
    assert production["services"]["grpc"]["environment"]["GRPC_ALLOW_INSECURE"] == "false"
    assert kernel_grpc["services"]["grpc"]["environment"]["GRPC_ALLOW_INSECURE"] == "true"
    assert "ports" not in kernel_grpc["services"]["grpc"]


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
