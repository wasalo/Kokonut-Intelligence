"""Public IRI resolution exposes only a bounded published-location projection."""

import hashlib
import json
from unittest.mock import Mock

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import public_iri  # noqa: E402
from services.gateway.app import create_app  # noqa: E402

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
PUBLIC_IRI = f"kokonut:location:{LOCATION_ID}:v2"
PREVIOUS_IRI = f"kokonut:location:{LOCATION_ID}:v1"


class Result:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class ReadOnlyConnection:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))
        if "SELECT iri.iri" in statement:
            return Result(self.row)
        return Result(None)


def public_row(**overrides):
    return {
        "iri": PUBLIC_IRI,
        "version": 2,
        "entity_id": LOCATION_ID,
        "public_projection": {
            "name": "Public Farm",
            "country": "DO",
            "region": "North",
            "status": "active",
        },
        "verified_previous_iri": PREVIOUS_IRI,
        **overrides,
    }


def public_document(*, previous_version=True):
    document = {
        "@context": {
            "schema": "http://schema.org/",
            "kokonut": "https://kokonut.network/ontology#",
        },
        "@id": PUBLIC_IRI,
        "@type": "kokonut:location",
        "schema:name": "Public Farm",
        "schema:addressCountry": "DO",
        "schema:addressRegion": "North",
        "kokonut:status": "active",
        "kokonut:version": 2,
    }
    if previous_version:
        document["kokonut:previousVersion"] = {"@id": PREVIOUS_IRI}
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    document["kokonut:publicProjectionHash"] = "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    document["kokonut:hashAlgorithm"] = "sha256"
    return document


def test_public_iri_returns_jsonld_projection_hash_and_validated_lineage():
    connection = ReadOnlyConnection(public_row())
    connection_factory = Mock(return_value=connection)

    document = public_iri.resolve_public_location_iri(
        PUBLIC_IRI,
        connection_factory=connection_factory,
    )

    connection_factory.assert_called_once_with(connect_timeout=3, readonly=True)
    assert connection.statements[0][0] == "SET LOCAL statement_timeout = '5s'"
    assert connection.statements[1][0] == "SET LOCAL lock_timeout = '2s'"
    query, parameters = connection.statements[2]
    assert "JOIN v_public_farm_summary" in query
    assert "iri.entity_type = 'location'" in query
    assert "iri.version = :version" in query
    assert "iri.public_projection IS NOT NULL" in query
    assert "metadata_json" not in query
    assert "content_hash" not in query
    assert parameters == {"iri": PUBLIC_IRI, "entity_id": LOCATION_ID, "version": 2}

    assert document == {
        "@context": {
            "schema": "http://schema.org/",
            "kokonut": "https://kokonut.network/ontology#",
        },
        "@id": PUBLIC_IRI,
        "@type": "kokonut:location",
        "schema:name": "Public Farm",
        "schema:addressCountry": "DO",
        "schema:addressRegion": "North",
        "kokonut:status": "active",
        "kokonut:version": 2,
        "kokonut:previousVersion": {"@id": PREVIOUS_IRI},
        "kokonut:publicProjectionHash": document["kokonut:publicProjectionHash"],
        "kokonut:hashAlgorithm": "sha256",
    }
    hash_input = {key: value for key, value in document.items() if key not in {
        "kokonut:publicProjectionHash", "kokonut:hashAlgorithm"
    }}
    canonical = json.dumps(hash_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected_hash = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert document["kokonut:publicProjectionHash"] == expected_hash


@pytest.mark.parametrize(
    "iri",
    [
        "kokonut:credit_class:11111111-1111-4111-8111-111111111111:v1",
        "kokonut:location:not-a-uuid:v1",
        "kokonut:location:11111111-1111-4111-8111-111111111111:v0",
        "https://example.org/private",
    ],
)
def test_noncanonical_or_non_location_iris_fail_before_database_access(iri):
    connection_factory = Mock()

    result = public_iri.resolve_public_location_iri(
        iri,
        connection_factory=connection_factory,
    )

    assert result is None
    connection_factory.assert_not_called()


def test_private_or_unpublished_location_is_indistinguishable_from_unknown_iri():
    connection = ReadOnlyConnection(None)
    connection_factory = Mock(return_value=connection)

    result = public_iri.resolve_public_location_iri(
        PUBLIC_IRI,
        connection_factory=connection_factory,
    )

    assert result is None


def test_invalid_previous_pointer_is_not_returned_as_lineage():
    connection = ReadOnlyConnection(
        public_row(verified_previous_iri=None)
    )

    document = public_iri.resolve_public_location_iri(
        PUBLIC_IRI,
        connection_factory=Mock(return_value=connection),
    )

    assert document is not None
    assert "kokonut:previousVersion" not in document


def test_malformed_stored_public_projection_fails_closed():
    connection = ReadOnlyConnection(
        public_row(public_projection={"name": "Private note", "status": "active"})
    )

    document = public_iri.resolve_public_location_iri(
        PUBLIC_IRI,
        connection_factory=Mock(return_value=connection),
    )

    assert document is None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH",
        str(tmp_path / "gateway-audit.sqlite3"),
    )
    with TestClient(create_app()) as test_client:
        yield test_client


def test_gateway_iri_route_returns_jsonld_without_private_registry_fields(client, monkeypatch):
    safe_document = public_document()
    resolver = Mock(return_value=safe_document)
    monkeypatch.setattr(public_iri, "resolve_public_location_iri", resolver)

    response = client.get("/api/iri/resolve", params={"iri": PUBLIC_IRI})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/ld+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == safe_document
    resolver.assert_called_once_with(PUBLIC_IRI)


def test_gateway_iri_openapi_documents_jsonld_media_type_and_exact_fields(client):
    operation = client.app.openapi()["paths"]["/api/iri/resolve"]["get"]
    content = operation["responses"]["200"]["content"]
    assert set(content) == {"application/ld+json"}
    schema_ref = content["application/ld+json"]["schema"]["$ref"]
    schema = client.app.openapi()["components"]["schemas"][schema_ref.rsplit("/", 1)[-1]]

    assert operation["operationId"] == "resolvePublicLocationIri"
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {
        "@context",
        "@id",
        "@type",
        "schema:name",
        "schema:addressCountry",
        "schema:addressRegion",
        "kokonut:status",
        "kokonut:version",
        "kokonut:previousVersion",
        "kokonut:publicProjectionHash",
        "kokonut:hashAlgorithm",
    }


def test_gateway_iri_route_omits_only_absent_predecessor_and_keeps_nullable_fields(
    client, monkeypatch
):
    document = public_document(previous_version=False)
    document["schema:addressCountry"] = None
    document["schema:addressRegion"] = None
    unsigned = {key: value for key, value in document.items() if key not in {
        "kokonut:publicProjectionHash", "kokonut:hashAlgorithm"
    }}
    document["kokonut:publicProjectionHash"] = "sha256:" + hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr(public_iri, "resolve_public_location_iri", Mock(return_value=document))

    response = client.get("/api/iri/resolve", params={"iri": PUBLIC_IRI})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/ld+json")
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["schema:addressCountry"] is None
    assert response.json()["schema:addressRegion"] is None
    assert "kokonut:previousVersion" not in response.json()


def test_gateway_iri_route_rejects_malformed_jsonld_contract_without_leaking_fields(
    client, monkeypatch
):
    document = public_document()
    document["kokonut:publicProjectionHash"] = "sha256:" + "0" * 64
    monkeypatch.setattr(public_iri, "resolve_public_location_iri", Mock(return_value=document))

    response = client.get("/api/iri/resolve", params={"iri": PUBLIC_IRI})

    assert response.status_code == 500
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "IRI resolution unavailable"}
    assert "sha256:" not in response.text


def test_gateway_iri_route_returns_nonrevealing_404_for_private_or_unknown_iri(client, monkeypatch):
    resolver = Mock(return_value=None)
    monkeypatch.setattr(public_iri, "resolve_public_location_iri", resolver)

    response = client.get("/api/iri/resolve", params={"iri": "private-or-missing"})

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"error": "IRI not found"}
