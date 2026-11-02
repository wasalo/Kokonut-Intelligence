"""Focused data-service protobuf serialization regressions."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

from services.data_module import content_hash
from services.grpc import data_service


def test_find_iri_by_hash_serializes_hash_algorithm_field(monkeypatch) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "sdk/python")
    )
    from kokonut.grpc.data.v1 import service_pb2, types_pb2

    data_package = ModuleType("services.grpc.data")
    data_package.__path__ = []
    v1_package = ModuleType("services.grpc.data.v1")
    v1_package.service_pb2 = service_pb2
    v1_package.types_pb2 = types_pb2
    data_package.v1 = v1_package
    monkeypatch.setitem(sys.modules, "services.grpc.data", data_package)
    monkeypatch.setitem(sys.modules, "services.grpc.data.v1", v1_package)

    connection = object()
    db_factory = MagicMock(return_value=connection)
    monkeypatch.setattr(data_service, "require_scope", MagicMock())
    monkeypatch.setattr(
        content_hash,
        "find_iri_by_content_hash",
        lambda conn, hash_value: [
            {
                "iri": "kokonut:location:adelphi:v1",
                "entity_type": "location",
                "entity_id": "adelphi",
                "hash_value": hash_value,
                "hash_algorithm": "sha256",
            }
        ],
    )

    response = data_service.DataServiceServicer(db_factory).FindIRIByHash(
        service_pb2.FindIRIByHashRequest(hash_value="sha256:sample"),
        MagicMock(),
    )
    decoded = service_pb2.FindIRIByHashResponse.FromString(
        response.SerializeToString()
    )

    db_factory.assert_called_once_with()
    db_factory.release.assert_called_once_with(connection)
    assert len(decoded.results) == 1
    assert decoded.results[0].content_hash == "sha256:sample"
    assert decoded.results[0].hash_algorithm == "sha256"
