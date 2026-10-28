"""Stored EAS proof metadata stays private, tenant-scoped, and read-only."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.attestations import list_location_attestations  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_location_attestation_policy_is_exact_and_location_scoped():
    location_id = str(uuid4())
    path = f"/operator/api/attestations/{location_id}"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "attestation",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM attestation_record AS record" in query:
            self.connection.events.append("attestation_read")
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id",
                    "attestation_uid",
                    "schema_uid",
                    "schema_name",
                    "claim_type",
                    "status",
                    "chain",
                    "tx_hash",
                    "attested_at",
                    "expiration_date",
                    "revocation_date",
                    "schema_version",
                    "created_at",
                )
            ]
            self.rows = [
                (
                    uuid4(),
                    "0x" + "1" * 64,
                    "0x" + "2" * 64,
                    "kokonut-mrv",
                    "mrv",
                    "published",
                    "celo",
                    "0x" + "3" * 64,
                    datetime(2026, 10, 1, tzinfo=timezone.utc),
                    date(2027, 10, 1),
                    None,
                    "v1",
                    datetime(2026, 10, 1, tzinfo=timezone.utc),
                )
            ]

    def fetchall(self):
        return self.rows


class _Connection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.events = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_location_attestation_read_sets_context_before_select_and_excludes_private_columns():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "attestation",
            "action": "read",
        }
        connection.events.append("tenant_context")

    with patch("services.gateway.attestations.set_operator_tenant_context", set_context):
        rows = list_location_attestations(
            operator_id, location_id, 10, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "attestation_read"]
    assert [query for query, _params in conn.queries[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '5s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert conn.queries[3][1] == (location_id, 10)
    query = conn.queries[3][0]
    assert "record.subject_type = 'location'" in query
    assert "COALESCE(record.chain, schema.chain) = 'celo'" in query
    assert "claim_data" not in query
    assert "evidence_urls" not in query
    assert "evidence_cids" not in query
    assert "review_notes" not in query
    assert rows[0]["schema_name"] == "kokonut-mrv"
    assert rows[0]["attested_at"] == "2026-10-01T00:00:00+00:00"
    assert rows[0]["expiration_date"] == "2027-10-01"
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize("limit", [0, 101, True, "10"])
def test_invalid_attestation_limit_fails_before_database_connection(limit):
    requested = False

    def connection_factory():
        nonlocal requested
        requested = True
        raise AssertionError("invalid limit must not open PostgreSQL")

    with pytest.raises(ValueError, match="limit must be between"):
        list_location_attestations(
            str(uuid4()), str(uuid4()), limit, connection_factory=connection_factory
        )
    assert requested is False


def test_attestation_tenant_denial_closes_connection():
    conn = _Connection()
    with patch(
        "services.gateway.attestations.set_operator_tenant_context",
        side_effect=TenantContextDenied("synthetic stale grant"),
    ):
        with pytest.raises(TenantContextDenied):
            list_location_attestations(
                str(uuid4()), str(uuid4()), connection_factory=lambda: conn
            )

    assert len(conn.queries) == 3
    assert conn.rolled_back and conn.closed


@pytest.fixture
def in_memory_audit(monkeypatch):
    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)


def test_location_attestation_route_denies_missing_scope_before_service(
    monkeypatch, in_memory_audit
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    service_called = False

    def unexpected_service(*_args):
        nonlocal service_called
        service_called = True
        raise AssertionError("scope denial must precede service access")

    monkeypatch.setattr(
        "services.gateway.attestations.list_location_attestations", unexpected_service
    )
    location_id = str(uuid4())
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/attestations/{location_id}")

    assert response.status_code == 403
    assert service_called is False


def test_location_attestation_route_returns_stored_metadata_no_store(
    monkeypatch, in_memory_audit
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="9" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "attestation"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.attestations.list_location_attestations",
        lambda scoped_operator, scoped_location, limit=50: [
            {
                "id": str(uuid4()),
                "attestation_uid": "0x" + "1" * 64,
                "schema_uid": "0x" + "2" * 64,
                "schema_name": "Location outcome",
                "claim_type": "impact",
                "status": "published",
                "chain": "celo",
                "tx_hash": "0x" + "3" * 64,
                "attested_at": "2026-10-28T10:00:00+00:00",
                "expiration_date": None,
                "revocation_date": None,
                "schema_version": "1.0",
                "created_at": "2026-10-28T10:00:00+00:00",
            }
        ],
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/attestations/{location_id}", params={"limit": 5}
        )

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.json()["data"][0]["status"] == "published"
    assert set(response.json()["data"][0]) == {
        "id",
        "attestation_uid",
        "schema_uid",
        "schema_name",
        "claim_type",
        "status",
        "chain",
        "tx_hash",
        "attested_at",
        "expiration_date",
        "revocation_date",
        "schema_version",
        "created_at",
    }
    assert response.headers["cache-control"] == "no-store"


def test_location_attestation_response_model_is_published_and_privacy_bounded():
    schema = create_app().openapi()
    operation = schema["paths"]["/operator/api/attestations/{location_id}"]["get"]
    response = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["$ref"].endswith("/LocationAttestationsResponse")

    record = schema["components"]["schemas"]["LocationAttestationRecord"]
    page_data = schema["components"]["schemas"]["LocationAttestationsResponse"]["properties"]["data"]
    assert page_data["maxItems"] == 100
    assert page_data["items"]["$ref"].endswith("/LocationAttestationRecord")
    assert set(record["properties"]) == {
        "id",
        "attestation_uid",
        "schema_uid",
        "schema_name",
        "claim_type",
        "status",
        "chain",
        "tx_hash",
        "attested_at",
        "expiration_date",
        "revocation_date",
        "schema_version",
        "created_at",
    }
    assert record["additionalProperties"] is False
    assert "claim_data" not in record["properties"]
    assert "evidence_urls" not in record["properties"]
