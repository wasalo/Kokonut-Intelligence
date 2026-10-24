"""Ensure gRPC authentication and request logs omit raw failure details."""

import builtins
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.grpc.auth import APIKeyInterceptor
from services.grpc.interceptors import LoggingInterceptor


def test_api_key_database_failure_logs_only_exception_class(caplog):
    sensitive_detail = "postgresql://db-user:password@db.internal/private"
    factory = MagicMock(side_effect=RuntimeError(sensitive_detail))
    interceptor = APIKeyInterceptor(db_factory=factory)
    details = SimpleNamespace(
        method="ecocredit.v1.EcocreditService/Classes",
        invocation_metadata=[("x-api-key", "synthetic-api-key")],
    )
    caplog.set_level(logging.ERROR, logger="kokonut.grpc.auth")

    result = interceptor.intercept_service(MagicMock(), details)

    assert result is not None
    assert "API key lookup failed (RuntimeError)" in caplog.text
    assert sensitive_detail not in caplog.text
    assert "synthetic-api-key" not in caplog.text


def test_failed_rpc_logs_bounded_exception_and_preserves_propagation(caplog):
    sensitive_detail = "authorization=private-token; /private/request/path"
    interceptor = LoggingInterceptor()
    continuation = MagicMock(side_effect=RuntimeError(sensitive_detail))
    details = SimpleNamespace(method="data.v1.DataService/ResolveIRI")
    caplog.set_level(logging.ERROR, logger="kokonut.grpc.interceptor")

    with pytest.raises(RuntimeError):
        interceptor.intercept_service(continuation, details)

    assert "RuntimeError" in caplog.text
    assert details.method in caplog.text
    assert sensitive_detail not in caplog.text


def test_optional_service_import_failures_log_only_exception_class(caplog, monkeypatch):
    from services.grpc import server as grpc_server

    sensitive_detail = "optional module source /opt/kokonut-internal/plugin.py"
    original_import = builtins.__import__
    optional_modules = {
        "services.grpc.credit_class_service",
        "services.grpc.ecocredit.v1",
        "services.grpc.data.v1",
        "services.grpc.data_service",
    }

    def _import_with_optional_failures(name, *args, **kwargs):
        if name in optional_modules:
            raise ImportError(sensitive_detail)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _import_with_optional_failures)
    monkeypatch.setattr(grpc_server.grpc, "server", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(
        grpc_server.health_pb2_grpc, "add_HealthServicer_to_server", MagicMock()
    )
    monkeypatch.setattr(grpc_server.reflection, "enable_server_reflection", MagicMock())
    caplog.set_level(logging.WARNING, logger="kokonut.grpc.server")

    grpc_server._build_server(MagicMock(), MagicMock())

    assert "Ecocredit service not available (ImportError)" in caplog.text
    assert "Data service not available (ImportError)" in caplog.text
    assert sensitive_detail not in caplog.text
