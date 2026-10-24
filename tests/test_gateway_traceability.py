"""Location-scoped traceability reads expose bounded operational facts only."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied
from services.gateway.app import create_app
from services.gateway.operator_auth import auth_route_policy
from services.gateway.traceability import (
    _fetch_related_rows,
    get_location_traceability_batch,
    list_location_traceability_batches,
)


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self.rows = []
        self.one = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        if "FROM chain_of_custody" in query:
            self.description = [(name,) for name in (
                "sequence_num", "from_actor_type", "to_actor_type", "transfer_date",
                "received_date", "quantity", "unit", "transfer_method",
                "temperature_at_transfer_c", "status",
            )]
            self.rows = [(1, "farm", "cooperative", None, None, Decimal("120"), "kg", "truck", None, "received")]
        elif "FROM quality_inspection" in query:
            self.description = [(name,) for name in (
                "inspection_date", "inspection_point", "overall_grade", "score",
                "moisture_pct", "foreign_material_pct", "temperature_c",
                "appearance_score", "freshness_score", "size_uniformity",
                "defect_count", "passed", "status",
            )]
            self.rows = [(None, "receiving", "A", Decimal("91"), None, None, None, None, None, None, 0, True, "reviewed")]
        elif "FROM certification_verify" in query:
            self.description = [(name,) for name in (
                "certification", "category", "issued_date", "expiry_date", "verified", "chain_verified", "status",
            )]
            self.rows = [("Organic", "production", None, None, True, False, "verified")]
        elif "FROM food_safety_record" in query:
            self.description = [(name,) for name in (
                "record_type", "record_time", "temperature_c", "temperature_min_c",
                "temperature_max_c", "within_range", "humidity_pct", "ph_level",
                "hygiene_score", "hand_wash_ok", "protective_gear_ok",
                "pest_detected", "passed", "status",
            )]
            self.rows = [("temperature_log", None, Decimal("4"), None, None, True, None, None, None, True, True, False, True, "recorded")]
        elif "FROM provenance_event" in query:
            self.description = [(name,) for name in ("event_type", "event_time", "chain_verified", "status")]
            self.rows = [("harvest", None, False, "recorded")]
        elif "FROM produce_batch" in query and "LIMIT %s OFFSET %s" in query:
            self.description = [(name,) for name in (
                "id", "batch_number", "crop_name", "variety", "quantity", "unit",
                "harvest_date", "organic", "status", "created_at",
            )]
            self.rows = [
                (str(uuid4()), "PB-1", "maize", None, Decimal("4"), "kg", None, True, "active", None),
                (str(uuid4()), "PB-2", "beans", None, Decimal("3"), "kg", None, False, "active", None),
                (str(uuid4()), "PB-3", "cacao", None, Decimal("2"), "kg", None, True, "active", None),
            ]
        elif "FROM produce_batch" in query:
            self.description = [(name,) for name in (
                "id", "batch_number", "crop_name", "variety", "quantity", "unit",
                "harvest_date", "organic", "status", "expiry_date", "grade",
            )]
            if not self.conn.missing_batch:
                self.one = (
                    params[0], "PB-42", "maize", "criollo", Decimal("125.5"), "kg",
                    None, True, "in_transit", None, "A",
                )

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class _Connection:
    autocommit = False

    def __init__(self, *, missing_batch=False):
        self.queries = []
        self.rolled_back = False
        self.closed = False
        self.missing_batch = missing_batch

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_traceability_route_policy_is_exact_location_scoped_read():
    location_id, batch_id = str(uuid4()), str(uuid4())
    for path in (
        f"/operator/api/traceability/{location_id}/batches",
        f"/operator/api/traceability/{location_id}/batches/{batch_id}",
    ):
        assert auth_route_policy("GET", path, enabled=True) == {
            "resource": "traceability",
            "action": "read",
            "public": False,
            "location_id": location_id,
            "scope_required": True,
            "operator_auth": True,
        }
        assert auth_route_policy("POST", path, enabled=True) is None
        assert auth_route_policy("GET", path, enabled=False) is None
    assert auth_route_policy(
        "GET", f"/operator/api/traceability/{location_id}/batches/{batch_id}/events", enabled=True
    ) is None


def test_traceability_routes_are_registered_on_the_operator_router(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3")
    )
    app = create_app()
    paths = app.openapi()["paths"]
    assert "/operator/api/traceability/{location_id}/batches" in paths
    assert "/operator/api/traceability/{location_id}/batches/{batch_id}" in paths


@pytest.fixture
def isolated_audit(monkeypatch):
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


def test_traceability_route_checks_grant_then_returns_no_store_data(monkeypatch, isolated_audit):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "traceability"
                and action == "read"
                and scoped_location == location_id
            )

    result = {"location_id": location_id, "items": [], "limit": 25, "offset": 0, "has_more": False}
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    with patch(
        "services.gateway.traceability.list_location_traceability_batches", return_value=result
    ) as list_batches:
        with TestClient(
            create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
        ) as client:
            response = client.get(f"/operator/api/traceability/{location_id}/batches")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}
    assert response.json() == result
    list_batches.assert_called_once_with(operator_id, location_id, status=None, limit=25, offset=0)


def test_traceability_http_denial_precedes_read_query(monkeypatch, isolated_audit):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())

    def unexpected_read(*_args, **_kwargs):
        raise AssertionError("the service must not run after grant denial")

    monkeypatch.setattr("services.gateway.traceability.list_location_traceability_batches", unexpected_read)
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/traceability/{uuid4()}/batches")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_batch_page_establishes_signed_scope_before_exact_location_query():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "traceability",
            "action": "read",
        }

    with patch("services.gateway.traceability.set_operator_tenant_context", set_context):
        result = list_location_traceability_batches(
            operator_id, location_id, limit=2, offset=5, connection_factory=lambda: conn
        )

    query, params = conn.queries[3]
    assert "WHERE location_id = %s::uuid" in query
    assert params == (location_id, 3, 5)
    assert result["location_id"] == location_id
    assert len(result["items"]) == 2 and result["has_more"] is True
    assert conn.queries[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.rolled_back and conn.closed


def test_invalid_scope_and_page_fail_before_opening_connection():
    opened = False

    def connect():
        nonlocal opened
        opened = True
        raise AssertionError("invalid request must fail before DB access")

    with pytest.raises(ValueError, match="Invalid operator"):
        list_location_traceability_batches("bad", str(uuid4()), connection_factory=connect)
    with pytest.raises(ValueError, match="limit"):
        list_location_traceability_batches(
            str(uuid4()), str(uuid4()), limit=51, connection_factory=connect
        )
    with pytest.raises(ValueError, match="Unsupported batch status"):
        list_location_traceability_batches(
            str(uuid4()), str(uuid4()), status="unknown", connection_factory=connect
        )
    assert opened is False


def test_batch_detail_scopes_every_child_read_and_omits_sensitive_fields():
    operator_id, location_id, batch_id = str(uuid4()), str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "traceability",
            "action": "read",
        }

    with patch("services.gateway.traceability.set_operator_tenant_context", set_context):
        result = get_location_traceability_batch(
            operator_id, location_id, batch_id, connection_factory=lambda: conn
        )

    assert result is not None
    assert result["batch"]["batch_number"] == "PB-42"
    assert result["custody_transfers"]["items"][0]["sequence_num"] == 1
    assert result["quality_inspections"]["items"][0]["passed"] is True
    assert result["certifications"]["items"][0]["certification"] == "Organic"
    assert result["food_safety_records"]["items"][0]["within_range"] is True
    assert result["provenance_events"]["items"][0]["event_type"] == "harvest"
    child_queries = [query for query, _ in conn.queries[4:]]
    assert len(child_queries) == 5
    assert all("pb.location_id = %s::uuid" in query or "cv.location_id = %s::uuid" in query for query in child_queries)
    assert all(params == (batch_id, location_id, 101) for _query, params in conn.queries[4:])
    for query in conn.queries[3:]:
        sql = query[0].lower()
        for private_column in (
            "actor_name", "inspector_name", "recorded_by", "evidence_urls",
            "gps_latitude", "gps_longitude", "document_url", "rejection_reason",
            "corrective_action", "violation_notes", "metadata", "notes",
        ):
            assert private_column not in sql
    assert conn.rolled_back and conn.closed


def test_related_collection_truncates_at_one_hundred_and_marks_response():
    cursor = _Cursor(_Connection())
    cursor.description = [("ordinal",)]
    cursor.rows = [(value,) for value in range(101)]

    result = _fetch_related_rows(cursor)

    assert len(result["items"]) == 100
    assert result["items"][-1] == {"ordinal": 99}
    assert result["truncated"] is True


def test_batch_detail_hides_unknown_and_cross_location_batch_as_not_found():
    operator_id, location_id, batch_id = str(uuid4()), str(uuid4()), str(uuid4())
    conn = _Connection(missing_batch=True)

    def set_context(connection, **_kwargs):
        assert connection is conn

    with patch("services.gateway.traceability.set_operator_tenant_context", set_context):
        result = get_location_traceability_batch(
            operator_id, location_id, batch_id, connection_factory=lambda: conn
        )

    assert result is None
    assert len(conn.queries) == 4
    assert conn.rolled_back and conn.closed


def test_traceability_tenant_denial_prevents_data_reads_and_cleans_up():
    conn = _Connection()
    with patch(
        "services.gateway.traceability.set_operator_tenant_context",
        side_effect=TenantContextDenied("missing exact location grant"),
    ):
        with pytest.raises(TenantContextDenied):
            list_location_traceability_batches(
                str(uuid4()), str(uuid4()), connection_factory=lambda: conn
            )
    assert len(conn.queries) == 3
    assert conn.rolled_back and conn.closed
