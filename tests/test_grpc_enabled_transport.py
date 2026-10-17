"""Loopback acceptance for the enabled gRPC server and auth interceptor."""

from __future__ import annotations

import hashlib
import importlib
import re
import threading
from concurrent import futures
from pathlib import Path

import grpc
import pytest


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
def running_server(tmp_path, monkeypatch):
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

    from services.grpc.server import _build_server

    database_factory = _DatabaseFactory()
    executor = futures.ThreadPoolExecutor(max_workers=4)
    server, services = _build_server(database_factory, executor)
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
    assert len(database_factory.connections) == 5
    assert database_factory.released == database_factory.connections
