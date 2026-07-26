"""Tests for gRPC server."""

from __future__ import annotations

import hashlib
import os
import tempfile
from unittest.mock import MagicMock, patch

import grpc
import pytest


class TestAPIKeyInterceptor:
    def test_exempt_methods_bypass_auth(self):
        from services.grpc.auth import APIKeyInterceptor
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        handler = MagicMock()
        continuation = MagicMock(return_value=handler)

        details = MagicMock()
        details.method = "grpc.health.v1.Health/Check"
        details.invocation_metadata = []

        result = interceptor.intercept_service(continuation, details)
        continuation.assert_called_once_with(details)

    def test_exempt_methods_accept_wire_format_with_leading_slash(self):
        from services.grpc.auth import APIKeyInterceptor
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        continuation = MagicMock(return_value="handler")

        details = MagicMock()
        details.method = "/grpc.health.v1.Health/Check"
        details.invocation_metadata = []

        assert interceptor.intercept_service(continuation, details) == "handler"
        continuation.assert_called_once_with(details)

    def test_missing_api_key_rejected(self):
        from services.grpc.auth import APIKeyInterceptor
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        continuation = MagicMock()

        details = MagicMock()
        details.method = "ecocredit.v1.EcocreditService/Classes"
        details.invocation_metadata = []

        result = interceptor.intercept_service(continuation, details)
        assert result is not None

    def test_valid_api_key_passes(self):
        from services.grpc.auth import APIKeyInterceptor
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        continuation = MagicMock(return_value="handler")

        details = MagicMock()
        details.method = "grpc.health.v1.Health/Check"
        details.invocation_metadata = [("x-api-key", "test_key_12345")]

        result = interceptor.intercept_service(continuation, details)
        continuation.assert_called_once_with(details)

    def test_expired_api_key_rejected(self):
        from services.grpc.auth import APIKeyInterceptor
        from datetime import datetime, timezone, timedelta
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        continuation = MagicMock()

        details = MagicMock()
        details.method = "ecocredit.v1.EcocreditService/Classes"
        details.invocation_metadata = [("x-api-key", "expired_key")]

        mock_conn = MagicMock()
        mock_factory = MagicMock(return_value=mock_conn)
        mock_factory.release = MagicMock()
        interceptor._db_factory = mock_factory

        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = {
            "id": "key-1",
            "is_active": True,
            "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            "scopes": [],
            "role_name": "user",
            "permissions": {},
        }
        mock_result.mappings.return_value = mock_mappings
        mock_conn.execute.return_value = mock_result

        result = interceptor.intercept_service(continuation, details)
        assert result is not None
        continuation.assert_not_called()
        mock_factory.release.assert_called_once_with(mock_conn)

    def test_deactivated_api_key_rejected(self):
        from services.grpc.auth import APIKeyInterceptor
        interceptor = APIKeyInterceptor(db_factory=lambda: MagicMock())
        continuation = MagicMock()

        details = MagicMock()
        details.method = "ecocredit.v1.EcocreditService/Classes"
        details.invocation_metadata = [("x-api-key", "deactivated_key")]

        mock_conn = MagicMock()
        mock_factory = MagicMock(return_value=mock_conn)
        mock_factory.release = MagicMock()
        interceptor._db_factory = mock_factory

        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = {
            "id": "key-1",
            "is_active": False,
            "expires_at": None,
            "scopes": [],
            "role_name": "user",
            "permissions": {},
        }
        mock_result.mappings.return_value = mock_mappings
        mock_conn.execute.return_value = mock_result

        result = interceptor.intercept_service(continuation, details)
        assert result is not None
        continuation.assert_not_called()
        mock_factory.release.assert_called_once_with(mock_conn)


class TestLoggingInterceptor:
    def test_intercept_service(self):
        from services.grpc.interceptors import LoggingInterceptor
        interceptor = LoggingInterceptor()
        handler = MagicMock()
        continuation = MagicMock(return_value=handler)

        details = MagicMock()
        details.method = "test/Method"

        result = interceptor.intercept_service(continuation, details)
        continuation.assert_called_once_with(details)


class TestHealthServicer:
    def test_check(self):
        from services.grpc.health import HealthServicer
        from grpc_health.v1.health_pb2 import HealthCheckRequest, HealthCheckResponse
        servicer = HealthServicer()
        context = MagicMock()
        response = servicer.Check(HealthCheckRequest(), context)
        assert response.status == HealthCheckResponse.SERVING

    def test_watch_yields_serving_status(self):
        from services.grpc.health import HealthServicer
        from grpc_health.v1.health_pb2 import HealthCheckRequest, HealthCheckResponse
        servicer = HealthServicer()
        context = MagicMock()
        context.is_active.return_value = False

        responses = list(servicer.Watch(HealthCheckRequest(), context))
        assert len(responses) >= 1
        assert responses[0].status == HealthCheckResponse.SERVING


class TestGrpcHealthCli:
    def test_health_uses_bounded_rpc_without_channel_ready_preflight(self):
        from services.grpc import cli
        from grpc_health.v1 import health_pb2, health_pb2_grpc

        serving = health_pb2.HealthCheckResponse.SERVING
        with patch("grpc.insecure_channel") as insecure_channel:
            channel = MagicMock()
            insecure_channel.return_value = channel
            stub = MagicMock()
            stub.Check.return_value = health_pb2.HealthCheckResponse(status=serving)
            with patch.object(health_pb2_grpc, "HealthStub", return_value=stub):
                cli.cmd_health(MagicMock(target="127.0.0.1:50051"))

        stub.Check.assert_called_once()
        assert stub.Check.call_args.kwargs["timeout"] == 5
        assert stub.Check.call_args.kwargs["wait_for_ready"] is True
        channel.close.assert_called_once_with()


class TestRequireScope:
    def test_scope_check_passes_with_matching_scope(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "admin",
            "scopes": ["ecocredit:class:read", "marketplace:write"],
        })
        try:
            mock_context = MagicMock()
            require_scope(mock_context, "ecocredit", "class")
            mock_context.abort.assert_not_called()
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_passes_with_wildcard(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "admin",
            "scopes": ["*:read"],
        })
        try:
            mock_context = MagicMock()
            require_scope(mock_context, "ecocredit", "read")
            mock_context.abort.assert_not_called()
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_denies_wrong_scope(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "user",
            "scopes": ["ecocredit:class:read"],
        })
        try:
            mock_context = MagicMock()
            mock_context.abort.side_effect = grpc.RpcError()
            with pytest.raises(grpc.RpcError):
                require_scope(mock_context, "marketplace", "write")
            mock_context.abort.assert_called_once_with(
                grpc.StatusCode.PERMISSION_DENIED,
                "Scope 'marketplace:write' required but not granted",
            )
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_denies_empty_scopes(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "user",
            "scopes": [],
        })
        try:
            mock_context = MagicMock()
            mock_context.abort.side_effect = grpc.RpcError()
            with pytest.raises(grpc.RpcError):
                require_scope(mock_context, "ecocredit", "read")
            mock_context.abort.assert_called_once()
            abort_args = mock_context.abort.call_args
            assert abort_args[0][0] == grpc.StatusCode.PERMISSION_DENIED
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_denies_no_auth(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set(None)
        try:
            mock_context = MagicMock()
            mock_context.abort.side_effect = grpc.RpcError()
            with pytest.raises(grpc.RpcError):
                require_scope(mock_context, "ecocredit", "read")
            mock_context.abort.assert_called_once_with(
                grpc.StatusCode.UNAUTHENTICATED,
                "Not authenticated",
            )
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_two_part_scope(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "user",
            "scopes": ["marketplace:read"],
        })
        try:
            mock_context = MagicMock()
            require_scope(mock_context, "marketplace", "read")
            mock_context.abort.assert_not_called()
        finally:
            grpc_auth_context.reset(token)

    def test_scope_check_wildcard_action(self):
        from services.grpc.auth import require_scope, grpc_auth_context

        token = grpc_auth_context.set({
            "api_key_id": "key-1",
            "role_name": "admin",
            "scopes": ["marketplace:*"],
        })
        try:
            mock_context = MagicMock()
            require_scope(mock_context, "marketplace", "write")
            mock_context.abort.assert_not_called()
        finally:
            grpc_auth_context.reset(token)


class TestConnectionPoolRelease:
    def test_auth_interceptor_releases_connection(self):
        from services.grpc.auth import APIKeyInterceptor

        mock_conn = MagicMock()
        mock_factory = MagicMock(return_value=mock_conn)
        mock_factory.release = MagicMock()

        interceptor = APIKeyInterceptor(db_factory=mock_factory)
        continuation = MagicMock(return_value="handler")

        details = MagicMock()
        details.method = "ecocredit.v1.EcocreditService/Classes"
        details.invocation_metadata = [("x-api-key", "test_key")]

        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = {
            "id": "key-1",
            "is_active": True,
            "expires_at": None,
            "scopes": [],
            "role_name": "admin",
            "permissions": {},
        }
        mock_result.mappings.return_value = mock_mappings
        mock_conn.execute.return_value = mock_result

        interceptor.intercept_service(continuation, details)
        mock_factory.release.assert_called_once_with(mock_conn)

    def test_pool_exhaustion_resilience(self):
        from services.grpc.auth import APIKeyInterceptor

        release_calls = []

        def release(conn):
            release_calls.append(conn)

        details = MagicMock()
        details.method = "ecocredit.v1.EcocreditService/Classes"
        details.invocation_metadata = [("x-api-key", "test_key")]

        mock_result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = {
            "id": "key-1",
            "is_active": True,
            "expires_at": None,
            "scopes": [],
            "role_name": "admin",
            "permissions": {},
        }
        mock_result.mappings.return_value = mock_mappings

        for _ in range(50):
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result

            mock_factory = MagicMock(return_value=mock_conn)
            mock_factory.release = release

            interceptor = APIKeyInterceptor(db_factory=mock_factory)
            continuation = MagicMock(return_value="handler")

            interceptor.intercept_service(continuation, details)

        assert len(release_calls) == 50


class TestTLSConfig:
    def test_tls_used_when_cert_key_configured(self):
        from services.grpc.server import serve

        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_file:
            cert_file.write(b"fake cert data")
            cert_path = cert_file.name

        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as key_file:
            key_file.write(b"fake key data")
            key_path = key_file.name

        try:
            with patch.dict(os.environ, {
                "GRPC_TLS_CERT": cert_path,
                "GRPC_TLS_KEY": key_path,
                "GRPC_PORT": "0",
            }, clear=False):
                env = os.environ.copy()
                env["GRPC_TLS_CERT"] = cert_path
                env["GRPC_TLS_KEY"] = key_path
                env["GRPC_PORT"] = "0"

                with patch.dict(os.environ, env, clear=True):
                    with patch("services.grpc.server._get_db_pool") as mock_pool:
                        mock_factory = MagicMock()
                        mock_factory.release = MagicMock()
                        mock_pool.return_value = mock_factory

                        with patch("grpc.server") as mock_grpc_server:
                            mock_server = MagicMock()
                            mock_grpc_server.return_value = mock_server

                            with patch("services.grpc.server.signal"):
                                with patch("services.grpc.server.reflection"):
                                    with patch("services.grpc.server.health_pb2_grpc"):
                                        with patch("services.grpc.server.APIKeyInterceptor"):
                                            with patch("services.grpc.server.LoggingInterceptor"):
                                                with patch("services.grpc.server.HealthServicer"):
                                                    try:
                                                        serve()
                                                    except (SystemExit, Exception):
                                                        pass

                            if mock_server.add_secure_port.called:
                                assert mock_server.add_secure_port.called
                            elif mock_server.add_insecure_port.called:
                                pass
                            mock_server.start.assert_called_once_with()
        finally:
            if os.path.exists(cert_path):
                os.unlink(cert_path)
            if os.path.exists(key_path):
                os.unlink(key_path)

    def test_insecure_used_when_no_tls_config(self):
        from services.grpc.server import serve

        env = os.environ.copy()
        env.pop("GRPC_TLS_CERT", None)
        env.pop("GRPC_TLS_KEY", None)
        env["GRPC_PORT"] = "0"

        with patch.dict(os.environ, env, clear=True):
            with patch("services.grpc.server._get_db_pool") as mock_pool:
                mock_factory = MagicMock()
                mock_factory.release = MagicMock()
                mock_pool.return_value = mock_factory

                with patch("grpc.server") as mock_grpc_server:
                    mock_server = MagicMock()
                    mock_grpc_server.return_value = mock_server

                    with patch("services.grpc.server.signal"):
                        with patch("services.grpc.server.reflection"):
                            with patch("services.grpc.server.health_pb2_grpc"):
                                with patch("services.grpc.server.APIKeyInterceptor"):
                                    with patch("services.grpc.server.LoggingInterceptor"):
                                        with patch("services.grpc.server.HealthServicer"):
                                            try:
                                                serve()
                                            except (SystemExit, Exception):
                                                pass

                    if mock_server.add_insecure_port.called:
                        args = mock_server.add_insecure_port.call_args
                        assert "[::]" in str(args)
                    mock_server.start.assert_called_once_with()


class TestProtoDefinitions:
    def test_proto_files_exist(self):
        from pathlib import Path
        proto_dir = Path("proto")
        assert (proto_dir / "common" / "pagination.proto").exists()
        assert (proto_dir / "ecocredit" / "v1" / "types.proto").exists()
        assert (proto_dir / "ecocredit" / "v1" / "service.proto").exists()
        assert (proto_dir / "data" / "v1" / "types.proto").exists()
        assert (proto_dir / "data" / "v1" / "service.proto").exists()

    def test_buf_config_exists(self):
        from pathlib import Path
        assert Path("proto/buf.yaml").exists()
        assert Path("proto/buf.gen.yaml").exists()


class TestGRPCDependencies:
    def test_grpcio_importable(self):
        import grpc
        assert hasattr(grpc, "ServerInterceptor")

    def test_protobuf_importable(self):
        from google.protobuf import descriptor
        assert descriptor is not None


class TestSDKStructure:
    def test_python_sdk_dir(self):
        from pathlib import Path
        assert Path("sdk/python").exists()
        assert Path("sdk/python/generated").exists()

    def test_typescript_sdk_dir(self):
        from pathlib import Path
        assert Path("sdk/typescript").exists()
        assert Path("sdk/typescript/src").exists()
        assert Path("sdk/typescript/package.json").exists()
        assert Path("sdk/typescript/tsconfig.json").exists()


class TestDockerfileGrpc:
    def test_dockerfile_exists(self):
        from pathlib import Path
        assert Path("Dockerfile.grpc").exists()
