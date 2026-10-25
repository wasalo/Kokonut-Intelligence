"""Waste-management Kernel reads remain private and location-scoped."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.waste_management_reads import get_location_waste_summary  # noqa: E402


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []
        self.rows = []
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM waste_stream" in query:
            columns = ("waste_type", "disposal_method", "quantity_unit", "record_count", "total_quantity", "first_date", "last_date")
            rows = [("crop_residue", "composting", "kg", 3, Decimal("12.5"), date(2026, 1, 2), date(2026, 1, 4))]
        elif "FROM composting_record" in query:
            columns = (
                "feedstock_type", "compost_method", "record_count", "total_quantity",
                "total_output_kg", "weighted_yield_pct", "mean_batch_yield_pct",
                "mean_duration_days", "mean_temperature_c", "mean_moisture_pct",
                "graded_batches", "first_date", "last_date",
            )
            rows = [(
                "manure", "vermiculture", 2, Decimal("8"), Decimal("3.2"),
                Decimal("40.0"), Decimal("42.5"), Decimal("25.0"),
                Decimal("54.5"), Decimal("58.0"), 1,
                date(2026, 1, 5), date(2026, 1, 6),
            )]
        elif "FROM recycling_log" in query:
            columns = ("material_type", "record_count", "total_quantity", "first_date", "last_date")
            rows = [("plastic", 1, Decimal("1.5"), date(2026, 1, 7), date(2026, 1, 7))]
        elif "summarize_location_pollution_incidents" in query:
            self.row = ([{
                "severity": "low", "status": "open", "record_count": 1,
                "first_date": "2026-01-08", "last_date": "2026-01-08",
            }],)
            columns, rows = (), []
        else:
            columns, rows = (), []
        self.description = [(column,) for column in columns]
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self):
        self.queries = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_waste_summary_has_exact_location_read_policy():
    location_id = str(uuid4())
    expected = {
        "resource": "waste_management",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", f"/operator/api/waste/{location_id}/summary", enabled=True) == expected
    assert auth_route_policy("POST", f"/operator/api/waste/{location_id}/summary", enabled=True) is None
    assert auth_route_policy("GET", f"/operator/api/waste/{location_id}/summary/extra", enabled=True) is None


def test_waste_summary_sets_signed_context_before_four_location_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    connection = _Connection()
    order = []

    def set_context(conn, **kwargs):
        assert conn is connection
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "waste_management",
            "action": "read",
        }
        order.append("context")

    original_execute = _Cursor.execute

    def observe_execute(self, query, params=None):
        order.append("query")
        original_execute(self, query, params)

    with patch("services.gateway.waste_management_reads.set_operator_tenant_context", set_context), patch.object(
        _Cursor, "execute", observe_execute
    ):
        result = get_location_waste_summary(
            operator_id, location_id, connection_factory=lambda: connection
        )

    queries = [(query, params) for query, params in connection.queries if "FROM " in query]
    assert len(queries) == 3
    assert all("location_id = %s::uuid" in query for query, _ in queries)
    assert all(params == (location_id,) for _, params in queries)
    assert "status = 'verified'" in queries[0][0]
    assert "status = 'verified'" in queries[1][0]
    assert "status = 'verified'" in queries[2][0]
    incident_query = next(
        (query, params) for query, params in connection.queries
        if "summarize_location_pollution_incidents" in query
    )
    assert incident_query[1] == (location_id,)
    assert "summarize_location_pollution_incidents" in incident_query[0]
    assert "FROM public.pollution_incident" not in incident_query[0]
    for query, _ in queries:
        for private_field in (
            "description", "affected_area", "remedial_action", "reported_to",
            "destination", "notes", "metadata", "created_by", "updated_by", "revenue",
        ):
            assert private_field not in query
    composting_sql = queries[1][0]
    assert "finished_volume_kg" in composting_sql
    assert "weighted_yield_pct" in composting_sql
    assert "mean_batch_yield_pct" in composting_sql
    assert "quality_grade IS NOT NULL" in composting_sql
    assert "quality_grade," not in composting_sql
    assert order == ["query", "query", "query", "context", "query", "query", "query", "query"]
    assert result == {
        "location_id": location_id,
        "waste_streams": [{
            "waste_type": "crop_residue", "disposal_method": "composting",
            "quantity_unit": "kg", "record_count": 3, "total_quantity": 12.5,
            "first_date": "2026-01-02", "last_date": "2026-01-04",
        }],
        "composting": [{
            "feedstock_type": "manure", "compost_method": "vermiculture",
            "record_count": 2, "feedstock_kg": 8.0,
            "total_output_kg": 3.2, "weighted_yield_pct": 40.0,
            "mean_batch_yield_pct": 42.5, "mean_duration_days": 25.0,
            "mean_temperature_c": 54.5, "mean_moisture_pct": 58.0,
            "graded_batches": 1,
            "first_date": "2026-01-05", "last_date": "2026-01-06",
        }],
        "recycling": [{
            "material_type": "plastic", "record_count": 1, "quantity_kg": 1.5,
            "first_date": "2026-01-07", "last_date": "2026-01-07",
        }],
        "pollution_incidents": [{
            "severity": "low", "status": "open", "record_count": 1,
            "first_date": "2026-01-08", "last_date": "2026-01-08",
        }],
    }
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [("bad", str(uuid4())), (str(uuid4()), "bad")])
def test_invalid_waste_summary_scope_fails_before_database_connection(operator_id, location_id):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before connecting")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_location_waste_summary(operator_id, location_id, connection_factory=connection_factory)
    assert not opened


@pytest.fixture
def gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_MAX_EVENTS", "1000")
    monkeypatch.setenv("KOKONUT_GATEWAY_AUDIT_SPOOL_ALERT_THRESHOLD", "0")

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


def test_waste_route_requires_location_scope_and_returns_no_store(monkeypatch, gateway_audit_spool):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "waste_management", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    expected = {"location_id": location_id, "waste_streams": [], "composting": [], "recycling": [], "pollution_incidents": []}
    monkeypatch.setattr(
        "services.gateway.waste_management_reads.get_location_waste_summary",
        lambda op, loc: expected if (op, loc) == (operator_id, location_id) else None,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/waste/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_waste_route_denies_missing_grant_before_query(monkeypatch, gateway_audit_spool):
    location_id = str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    called = False

    def unexpected_summary(*_args):
        nonlocal called
        called = True
        raise AssertionError("a missing grant must deny before entering the query")

    monkeypatch.setattr(
        "services.gateway.waste_management_reads.get_location_waste_summary", unexpected_summary
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/waste/{location_id}/summary")

    assert response.status_code == 403
    assert called is False
