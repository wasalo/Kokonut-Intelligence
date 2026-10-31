"""Loopback acceptance for the enabled gRPC server and auth interceptor."""

from __future__ import annotations

import hashlib
import importlib
import re
import shutil
import subprocess
import threading
from concurrent import futures
from pathlib import Path
from unittest.mock import MagicMock

import grpc
import pytest

TEST_CREDIT_LOCATION_ID = "a4b1b9e3-4d44-4df3-8d13-539c6cb2a5f0"


class _Mappings:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Result:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _Mappings(self._row)


class _AuthConnection:
    def __init__(self, rows):
        self._rows = rows

    @staticmethod
    def text(statement):
        return statement

    def execute(self, _statement, parameters):
        return _Result(self._rows.get(parameters["hash"]))


class _DatabaseFactory:
    def __init__(self):
        self._lock = threading.Lock()
        self.connections = []
        self.released = []
        self.rows = {
            hashlib.sha256(b"read-key").hexdigest(): {
                "id": "read-key-id",
                "is_active": True,
                "expires_at": None,
                "scopes": ["iri_registry:read"],
                "role_name": "reader",
                "permissions": {},
            },
            hashlib.sha256(b"write-key").hexdigest(): {
                "id": "write-key-id",
                "is_active": True,
                "expires_at": None,
                "scopes": ["iri_registry:write"],
                "role_name": "writer",
                "permissions": {},
            },
            hashlib.sha256(b"ecocredit-reader").hexdigest(): {
                "id": "ecocredit-reader-id",
                "is_active": True,
                "expires_at": None,
                "scopes": ["ecocredit:class:read"],
                "role_name": "ecocredit-reader",
                "permissions": {},
            },
            hashlib.sha256(b"ecocredit-batch-writer").hexdigest(): {
                "id": "ecocredit-batch-writer-id",
                "is_active": True,
                "expires_at": None,
                "scopes": [f"ecocredit_batch:create:{TEST_CREDIT_LOCATION_ID}"],
                "role_name": "ecocredit-batch-writer",
                "permissions": {},
            },
        }

    def __call__(self):
        connection = _AuthConnection(self.rows)
        with self._lock:
            self.connections.append(connection)
        return connection

    def release(self, connection):
        with self._lock:
            self.released.append(connection)


@pytest.fixture
def running_server(tmp_path, monkeypatch, request):
    from grpc_tools import protoc

    repository_root = Path(__file__).parents[1]
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    proto_sources = (
        "proto/common/pagination.proto",
        "proto/ecocredit/v1/types.proto",
        "proto/ecocredit/v1/service.proto",
        "proto/data/v1/types.proto",
        "proto/data/v1/service.proto",
    )
    result = protoc.main([
        "grpc_tools.protoc",
        f"-I{repository_root / 'proto'}",
        f"--python_out={generated_root}",
        f"--grpc_python_out={generated_root}",
        *(str(repository_root / source) for source in proto_sources),
    ])
    assert result == 0, "optional gRPC service protos must generate cleanly"
    for package in ("common", "data", "data/v1", "ecocredit", "ecocredit/v1"):
        package_dir = generated_root / package
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").touch()
    monkeypatch.syspath_prepend(str(generated_root))
    grpc_package = importlib.import_module("services.grpc")
    monkeypatch.setattr(grpc_package, "__path__", [*grpc_package.__path__, str(generated_root)])

    from services.grpc.server import DEFAULT_MAX_MESSAGE_BYTES, _build_server

    database_factory = _DatabaseFactory()
    executor = futures.ThreadPoolExecutor(max_workers=4)
    max_message_bytes = getattr(request, "param", DEFAULT_MAX_MESSAGE_BYTES)
    server, services = _build_server(
        database_factory, executor, max_message_bytes=max_message_bytes
    )
    port = server.add_insecure_port("127.0.0.1:0")
    assert port, "gRPC server must bind an ephemeral loopback port"
    server.start()
    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    grpc.channel_ready_future(channel).result(timeout=5)
    try:
        yield channel, database_factory, services
    finally:
        channel.close()
        server.stop(grace=0).wait(timeout=5)
        executor.shutdown(wait=True, cancel_futures=True)


def test_registered_server_enforces_api_key_and_scope_over_loopback(running_server, monkeypatch):
    from grpc_health.v1 import health_pb2, health_pb2_grpc

    from services.grpc.data.v1 import service_pb2, service_pb2_grpc
    from services.grpc.data.v1 import service_pb2 as data_service_pb2
    from services.grpc.data.v1 import types_pb2 as data_types_pb2
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc
    from services.grpc.ecocredit.v1 import types_pb2 as ecocredit_types_pb2

    channel, database_factory, services = running_server
    assert "grpc.health.v1.Health" in services
    assert "data.v1.DataService" in services
    assert "ecocredit.v1.EcocreditService" in services

    generated_modules = {
        "data_service_pb2": data_service_pb2,
        "data_types_pb2": data_types_pb2,
        "ecocredit_service_pb2": ecocredit_service_pb2,
        "ecocredit_types_pb2": ecocredit_types_pb2,
    }
    for source_name in ("data_service.py", "credit_class_service.py"):
        source = (Path(__file__).parents[1] / "services" / "grpc" / source_name).read_text()
        for alias, message_name in re.findall(r"\b(data_service_pb2|data_types_pb2|ecocredit_service_pb2|ecocredit_types_pb2)\.([A-Za-z_]\w*)", source):
            assert hasattr(generated_modules[alias], message_name), f"unresolved {alias}.{message_name} in {source_name}"

    health = health_pb2_grpc.HealthStub(channel)
    response = health.Check(health_pb2.HealthCheckRequest(service=""), timeout=3)
    assert response.status == health_pb2.HealthCheckResponse.SERVING
    assert database_factory.connections == [], "health checks remain exempt from API-key lookup"

    data = service_pb2_grpc.DataServiceStub(channel)
    with pytest.raises(grpc.RpcError) as missing_key:
        data.GenerateIRI(service_pb2.GenerateIRIRequest(entity_type="location", entity_id="demo"), timeout=3)
    assert missing_key.value.code() == grpc.StatusCode.UNAUTHENTICATED
    assert database_factory.connections == []

    denied_stream = data.StreamNewIRIs(service_pb2.StreamNewIRIsRequest(), timeout=3)
    with pytest.raises(grpc.RpcError) as missing_stream_key:
        next(denied_stream)
    assert missing_stream_key.value.code() == grpc.StatusCode.UNAUTHENTICATED
    assert database_factory.connections == [], "stream auth denial must precede service DB acquisition"

    with pytest.raises(grpc.RpcError) as missing_scope:
        data.GenerateIRI(
            service_pb2.GenerateIRIRequest(entity_type="location", entity_id="demo"),
            metadata=(("x-api-key", "read-key"),),
            timeout=3,
        )
    assert missing_scope.value.code() == grpc.StatusCode.PERMISSION_DENIED
    assert len(database_factory.connections) == 1, "scope denial must happen before service DB acquisition"
    assert database_factory.released == database_factory.connections

    monkeypatch.setattr(
        "services.iri.resolver.generate_iri",
        lambda _connection, **_kwargs: "kokonut:location:demo:v1",
    )
    result = data.GenerateIRI(
        service_pb2.GenerateIRIRequest(entity_type="location", entity_id="demo"),
        metadata=(("x-api-key", "write-key"),),
        timeout=3,
    )
    assert result.iri == "kokonut:location:demo:v1"
    assert len(database_factory.connections) == 3
    assert database_factory.released == database_factory.connections

    monkeypatch.setattr(
        "services.credit_class.class_manager.list_classes",
        lambda _connection: [{"id": "class-1", "name": "Synthetic", "credit_type": "carbon", "status": "active"}],
    )
    ecocredit = ecocredit_service_pb2_grpc.EcocreditServiceStub(channel)
    classes = ecocredit.Classes(
        ecocredit_service_pb2.ClassesRequest(),
        metadata=(("x-api-key", "ecocredit-reader"),),
        timeout=3,
    )
    assert len(classes.classes) == 1
    assert classes.classes[0].id == "class-1"
    assert classes.classes[0].name == "Synthetic"
    assert not classes.HasField("pagination")
    assert len(database_factory.connections) == 5
    assert database_factory.released == database_factory.connections


def test_tls_health_client_completes_verified_loopback_handshake(tmp_path, monkeypatch):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("OpenSSL is required to create an ephemeral loopback certificate")

    cert_path = tmp_path / "grpc-loopback-cert.pem"
    key_path = tmp_path / "grpc-loopback-key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-addext",
            "basicConstraints=critical,CA:TRUE",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    from grpc_health.v1 import health_pb2, health_pb2_grpc

    from services.core.adapters import grpc as grpc_adapter
    from services.grpc.health import HealthServicer

    monkeypatch.setattr(grpc_adapter, "require_enabled", lambda: None)
    executor = futures.ThreadPoolExecutor(max_workers=1)
    server = grpc.server(executor)
    health_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
    credentials = grpc.ssl_server_credentials(
        [(key_path.read_bytes(), cert_path.read_bytes())]
    )
    port = server.add_secure_port("127.0.0.1:0", credentials)
    assert port, "TLS health server must bind an ephemeral loopback port"
    server.start()
    try:
        status = grpc_adapter.check_health(
            f"127.0.0.1:{port}", tls_ca_path=str(cert_path)
        )
        assert status == health_pb2.HealthCheckResponse.SERVING
    finally:
        server.stop(grace=0).wait(timeout=5)
        executor.shutdown(wait=True, cancel_futures=True)


def test_ecocredit_classes_support_cursor_pagination_over_loopback(running_server, monkeypatch):
    from services.grpc.common import pagination_pb2
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc

    channel, database_factory, _services = running_server
    classes = [
        {
            "id": "class-1",
            "name": "First",
            "description": "",
            "credit_type": "carbon",
            "admin_address": "admin-1",
            "status": "published",
        },
        {
            "id": "class-2",
            "name": "Second",
            "description": "",
            "credit_type": "carbon",
            "admin_address": "admin-1",
            "status": "published",
        },
    ]
    monkeypatch.setattr(
        "services.credit_class.class_manager.list_classes_page",
        lambda _connection, *, limit, offset, **_filters: (
            classes[offset:offset + limit], len(classes)
        ),
    )
    client = ecocredit_service_pb2_grpc.EcocreditServiceStub(channel)
    metadata = (("x-api-key", "ecocredit-reader"),)

    first = client.Classes(
        ecocredit_service_pb2.ClassesRequest(
            pagination=pagination_pb2.PageRequest(limit=1),
        ),
        metadata=metadata,
        timeout=3,
    )
    second = client.Classes(
        ecocredit_service_pb2.ClassesRequest(
            pagination=pagination_pb2.PageRequest(
                limit=1,
                offset=first.pagination.next_key,
            ),
        ),
        metadata=metadata,
        timeout=3,
    )

    assert [item.id for item in first.classes] == ["class-1"]
    assert first.pagination.next_key == b"1"
    assert first.pagination.total == 2
    assert [item.id for item in second.classes] == ["class-2"]
    assert second.pagination.next_key == b""
    assert second.pagination.total == 2
    assert database_factory.released == database_factory.connections


def test_invalid_ecocredit_page_request_fails_before_service_database_acquisition(running_server):
    from services.grpc.common import pagination_pb2
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc

    channel, database_factory, _services = running_server

    with pytest.raises(grpc.RpcError) as invalid_page:
        ecocredit_service_pb2_grpc.EcocreditServiceStub(channel).Classes(
            ecocredit_service_pb2.ClassesRequest(
                pagination=pagination_pb2.PageRequest(limit=501),
            ),
            metadata=(("x-api-key", "ecocredit-reader"),),
            timeout=3,
        )

    assert invalid_page.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert len(database_factory.connections) == 1
    assert database_factory.released == database_factory.connections


@pytest.mark.parametrize("running_server", [1024], indirect=True)
def test_server_rejects_oversized_request_before_service_database_acquisition(running_server):
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc

    channel, database_factory, _services = running_server

    with pytest.raises(grpc.RpcError) as oversized:
        ecocredit_service_pb2_grpc.EcocreditServiceStub(channel).ClassesByAdmin(
            ecocredit_service_pb2.ClassesByAdminRequest(admin="a" * 2048),
            metadata=(("x-api-key", "ecocredit-reader"),),
            timeout=3,
        )

    assert oversized.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    assert len(database_factory.connections) == 1, "only API-key authentication may borrow a connection"
    assert database_factory.released == database_factory.connections


@pytest.mark.parametrize("running_server", [1024], indirect=True)
def test_server_rejects_oversized_response(running_server, monkeypatch):
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc

    channel, database_factory, _services = running_server
    monkeypatch.setattr(
        "services.credit_class.class_manager.list_classes",
        lambda _connection: [
            {
                "id": "class-1",
                "name": "x" * 2048,
                "description": "",
                "credit_type": "carbon",
                "admin_address": "admin-1",
                "status": "published",
            }
        ],
    )

    with pytest.raises(grpc.RpcError) as oversized:
        ecocredit_service_pb2_grpc.EcocreditServiceStub(channel).Classes(
            ecocredit_service_pb2.ClassesRequest(),
            metadata=(("x-api-key", "ecocredit-reader"),),
            timeout=3,
        )

    assert oversized.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED
    assert len(database_factory.connections) == 2
    assert database_factory.released == database_factory.connections


def test_create_batch_rpc_forwards_origin_transaction_reference(running_server, monkeypatch):
    from services.grpc.ecocredit.v1 import service_pb2 as ecocredit_service_pb2
    from services.grpc.ecocredit.v1 import service_pb2_grpc as ecocredit_service_pb2_grpc

    channel, database_factory, _services = running_server
    create_batch = MagicMock(return_value={"id": "batch-1", "batch_code": "BATCH-1"})
    monkeypatch.setattr("services.credit_class.batch_manager.create_batch", create_batch)
    set_location_context = MagicMock()
    monkeypatch.setattr("services.grpc.credit_class_service.set_location_tenant_context", set_location_context)
    request = ecocredit_service_pb2.CreateBatchRequest(
        credit_class_id="class-1",
        location_id=TEST_CREDIT_LOCATION_ID,
        vintage_year=2026,
        total_quantity=10,
        origin_tx_id="0xorigin",
        origin_tx_source="celo",
        origin_tx_contract="0xcontract",
    )

    response = ecocredit_service_pb2_grpc.EcocreditServiceStub(channel).CreateBatch(
        request,
        metadata=(("x-api-key", "ecocredit-batch-writer"),),
        timeout=3,
    )

    assert response.batch_id == "batch-1"
    assert response.batch_code == "BATCH-1"
    assert set_location_context.call_args.args[1] is database_factory.connections[-1]
    assert set_location_context.call_args.kwargs["resource"] == "ecocredit_batch"
    assert set_location_context.call_args.kwargs["action"] == "create"
    assert set_location_context.call_args.kwargs["location_id"] == TEST_CREDIT_LOCATION_ID
    assert create_batch.call_args.kwargs == {
        "credit_class_id": "class-1",
        "location_id": TEST_CREDIT_LOCATION_ID,
        "vintage_year": 2026,
        "total_quantity": 10.0,
        "unit": "tonneCO2e",
        "origin_tx_id": "0xorigin",
        "origin_tx_source": "celo",
        "origin_tx_contract": "0xcontract",
    }
    assert database_factory.released == database_factory.connections
