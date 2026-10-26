"""Waste-management Kernel reads remain private and location-scoped."""

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
        if "summarize_location_waste_operations" in query:
            location_id = params[0]
            days = params[1]
            self.row = ({
                "location_id": location_id,
                "waste_summary": {
                    "period_days": days, "total_waste_kg": 12.5, "total_records": 3,
                    "by_type": [{"waste_type": "crop_residue", "total_kg": 12.5, "record_count": 3}],
                    "by_disposal_method": [{"disposal_method": "composting", "total_kg": 12.5, "record_count": 3}],
                },
                "waste_streams": [{
                    "waste_type": "crop_residue", "disposal_method": "composting",
                    "quantity_unit": "kg", "record_count": 3, "total_quantity": 12.5,
                    "first_date": "2026-01-02", "last_date": "2026-01-04",
                }],
                "composting": [{
                    "feedstock_type": "manure", "compost_method": "vermiculture",
                    "record_count": 2, "feedstock_kg": 8, "total_output_kg": 3.2,
                    "weighted_yield_pct": 40, "mean_batch_yield_pct": 42.5,
                    "mean_duration_days": 25, "mean_temperature_c": 54.5,
                    "mean_moisture_pct": 58, "graded_batches": 1,
                    "first_date": "2026-01-05", "last_date": "2026-01-06",
                }],
                "composting_efficiency": {
                    "location_id": location_id, "total_batches": 2,
                    "total_feedstock_kg": 8, "total_output_kg": 3.2,
                    "overall_yield_pct": 40,
                    "by_method": [{
                        "compost_method": "vermiculture", "batches": 2,
                        "avg_yield_pct": 42.5, "avg_feedstock_kg": 4,
                        "avg_output_kg": 1.6, "avg_duration_days": 25,
                    }],
                    "recent_quality": [{
                        "ph": 6.8, "moisture_pct": 58, "temperature_c": 54.5,
                        "output_yield_pct": 40, "recorded_at": "2026-01-06",
                    }],
                },
                "recycling": [{
                    "material_type": "plastic", "record_count": 1, "quantity_kg": 1.5,
                    "first_date": "2026-01-07", "last_date": "2026-01-07",
                }],
            },)
            columns, rows = (), []
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


def test_waste_summary_sets_signed_context_before_database_summary_functions():
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

    aggregate_query = next(
        (query, params) for query, params in connection.queries
        if "summarize_location_waste_operations" in query
    )
    assert aggregate_query[1] == (location_id, 30)
    assert "summarize_location_waste_operations" in aggregate_query[0]
    assert "FROM public.waste_stream" not in aggregate_query[0]
    assert "FROM public.composting_record" not in aggregate_query[0]
    assert "FROM public.recycling_log" not in aggregate_query[0]
    incident_query = next(
        (query, params) for query, params in connection.queries
        if "summarize_location_pollution_incidents" in query
    )
    assert incident_query[1] == (location_id,)
    assert "summarize_location_pollution_incidents" in incident_query[0]
    assert "FROM public.pollution_incident" not in incident_query[0]
    assert order == ["query", "query", "query", "context", "query", "query"]
    assert result == {
        "location_id": location_id,
        "waste_summary": {
            "period_days": 30, "total_waste_kg": 12.5, "total_records": 3,
            "by_type": [{"waste_type": "crop_residue", "total_kg": 12.5, "record_count": 3}],
            "by_disposal_method": [{"disposal_method": "composting", "total_kg": 12.5, "record_count": 3}],
        },
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
        "composting_efficiency": {
            "location_id": location_id, "total_batches": 2,
            "total_feedstock_kg": 8.0, "total_output_kg": 3.2,
            "overall_yield_pct": 40.0,
            "by_method": [{
                "compost_method": "vermiculture", "batches": 2,
                "avg_yield_pct": 42.5, "avg_feedstock_kg": 4.0,
                "avg_output_kg": 1.6, "avg_duration_days": 25.0,
            }],
            "recent_quality": [{
                "ph": 6.8, "moisture_pct": 58.0, "temperature_c": 54.5,
                "output_yield_pct": 40.0, "recorded_at": "2026-01-06",
            }],
        },
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


@pytest.mark.parametrize("days", [0, -1, 3651, True, 30.5, "30"])
def test_invalid_waste_summary_window_fails_before_database_connection(days):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid time windows must fail before connecting")

    with pytest.raises(ValueError, match="days must be an integer"):
        get_location_waste_summary(
            str(uuid4()), str(uuid4()), days=days, connection_factory=connection_factory
        )
    assert not opened


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
    expected = {"location_id": location_id, "waste_summary": {}, "waste_streams": [], "composting": [], "composting_efficiency": {}, "recycling": [], "pollution_incidents": []}
    monkeypatch.setattr(
        "services.gateway.waste_management_reads.get_location_waste_summary",
        lambda op, loc, *, days=30: expected if (op, loc) == (operator_id, location_id) and days == 90 else None,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/waste/{location_id}/summary?days=90")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_waste_route_rejects_invalid_period_with_no_store_before_query(monkeypatch, gateway_audit_spool):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="c" * 64,
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
    called = False

    def unexpected_summary(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("invalid periods must fail before querying")

    monkeypatch.setattr(
        "services.gateway.waste_management_reads.get_location_waste_summary", unexpected_summary
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        for query in ("days=0", "days=3651", "days=1.5", "days=invalid"):
            response = client.get(f"/operator/api/waste/{location_id}/summary?{query}")
            assert response.status_code == 400
            assert "no-store" in response.headers["cache-control"]
    assert called is False


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
