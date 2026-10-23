"""Tests for private nutrient input/removal Kernel reads."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.nutrient_events import get_location_nutrient_events  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


@pytest.mark.parametrize("event_type", ["inputs", "removals"])
def test_nutrient_event_policy_is_exact_location_read(event_type):
    location_id = str(uuid4())
    path = f"/operator/api/nutrients/{location_id}/events/{event_type}"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "nutrient_budget",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None
    assert auth_route_policy("GET", f"/operator/api/nutrients/{location_id}/events/unknown", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self.one = None
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        self.conn.events.append("sql")
        if "SELECT COUNT(*)" in query:
            self.one = (2,)
            return

        event_type = "inputs" if "FROM nutrient_input AS event" in query else "removals"
        if event_type == "inputs":
            columns = [
                "id", "plot_id", "season", "budget_crop_name", "budget_status",
                "event_status", "input_date", "input_type", "product_name",
                "nitrogen_kg", "phosphorus_kg", "potassium_kg", "application_rate",
                "rate_unit",
            ]
            self.rows = [
                (
                    uuid4(), uuid4(), "2026-wet", "maize", "draft", "verified",
                    date(2026, 10, 22), "compost", "mature compost", 24, 8, 17,
                    120, "kg/ha",
                ),
                (
                    uuid4(), None, "2026-wet", "maize", "published", "recorded",
                    date(2026, 10, 20), "manure", None, 6, 2, 5, None, None,
                ),
            ]
        else:
            columns = [
                "id", "plot_id", "season", "budget_crop_name", "budget_status",
                "event_status", "harvest_date", "crop_name", "yield_amount",
                "yield_unit", "nitrogen_kg", "phosphorus_kg", "potassium_kg",
            ]
            self.rows = [
                (
                    uuid4(), uuid4(), "2026-wet", "maize", "published", "recorded",
                    date(2026, 10, 21), "maize", 1.25, "tonne", 32, 11, 22,
                ),
                (
                    uuid4(), None, "2026-dry", "beans", "verified", "verified",
                    date(2026, 10, 18), "beans", 0.4, "tonne", 18, 4, 13,
                ),
            ]
        self.description = [(name,) for name in columns]

    def fetchone(self):
        return self.one

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


@pytest.mark.parametrize("event_type", ["inputs", "removals"])
def test_nutrient_event_read_sets_context_and_returns_parent_and_event_lifecycle(event_type):
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "nutrient_budget",
            "action": "read",
        }
        conn.events.append("tenant_context")

    with patch("services.gateway.nutrient_events.set_operator_tenant_context", set_context):
        result = get_location_nutrient_events(
            operator_id,
            location_id,
            event_type,
            limit=2,
            connection_factory=lambda: conn,
        )

    reads = [(query, params) for query, params in conn.queries if "nutrient_" in query]
    assert len(reads) == 2
    assert conn.queries[:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql"]
    for query, _params in reads:
        assert "budget.location_id = %s::uuid" in query
        assert "event.status IN ('recorded', 'verified')" in query
    assert reads[0][1] == (location_id,)
    assert reads[1][1] == (location_id, 3, 0)
    page_sql = reads[1][0]
    assert "farm.location_id = budget.location_id" in page_sql
    assert "CASE WHEN farm.id IS NOT NULL THEN plot.id END" in page_sql
    assert "notes" not in page_sql.lower()
    assert "metadata" not in page_sql.lower()
    assert "cost" not in page_sql.lower()
    assert result["location_id"] == location_id
    assert result["event_type"] == event_type
    assert result["total_events"] == 2
    assert result["has_more"] is False
    assert [item["event_status"] for item in result["events"]] == (
        ["verified", "recorded"] if event_type == "inputs" else ["recorded", "verified"]
    )
    assert result["events"][0]["budget_status"] == ("draft" if event_type == "inputs" else "published")
    assert "budget_id" not in result["events"][0]
    assert conn.rolled_back and conn.closed

    first = result["events"][0]
    assert first["nutrients_kg"] == (
        {"nitrogen": 24.0, "phosphorus": 8.0, "potassium": 17.0}
        if event_type == "inputs"
        else {"nitrogen": 32.0, "phosphorus": 11.0, "potassium": 22.0}
    )
    if event_type == "inputs":
        assert first["input_type"] == "compost"
        assert first["product_name"] == "mature compost"
        assert first["application_rate"] == 120.0
        assert "cost" not in first
    else:
        assert first["harvest_date"] == "2026-10-21"
        assert first["crop_name"] == "maize"
        assert first["yield_amount"] == 1.25
        assert first["yield_unit"] == "tonne"


def test_nutrient_event_read_rejects_unknown_kind_before_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("unknown kind must fail before opening PostgreSQL")

    with pytest.raises(ValueError, match="event_type must be"):
        get_location_nutrient_events(
            str(uuid4()), str(uuid4()), "costs", connection_factory=connection_factory
        )
    assert opened is False


@pytest.mark.parametrize("event_type", ["inputs", "removals"])
def test_nutrient_event_page_is_bounded_and_reports_more_rows(event_type):
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    with patch("services.gateway.nutrient_events.set_operator_tenant_context"):
        result = get_location_nutrient_events(
            operator_id,
            location_id,
            event_type,
            limit=1,
            offset=0,
            connection_factory=lambda: conn,
        )

    page_query, page_params = conn.queries[-1]
    assert "LIMIT %s OFFSET %s" in page_query
    assert page_params == (location_id, 2, 0)
    assert result["has_more"] is True
    assert len(result["events"]) == 1
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("location_id", "limit", "offset"),
    [("bad-location", 25, 0), (str(uuid4()), 0, 0), (str(uuid4()), 25, -1)],
)
def test_nutrient_event_read_rejects_bad_scope_or_page_before_database(location_id, limit, offset):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid inputs must fail before connecting")

    with pytest.raises(ValueError):
        get_location_nutrient_events(
            str(uuid4()), location_id, "inputs", limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


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


@pytest.mark.parametrize("event_type", ["inputs", "removals"])
def test_nutrient_event_route_returns_no_store(monkeypatch, gateway_audit_spool, event_type):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="e" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "nutrient_budget", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.nutrient_events.get_location_nutrient_events",
        lambda op, loc, kind, **_kwargs: {
            "location_id": loc, "event_type": kind, "total_events": 0, "events": []
        },
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/nutrients/{location_id}/events/{event_type}")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.json()["event_type"] == event_type
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


@pytest.mark.parametrize("event_type", ["inputs", "removals"])
def test_nutrient_event_route_denies_missing_grant_before_handler(
    monkeypatch, gateway_audit_spool, event_type
):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="f" * 64,
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

    def unexpected_events(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.nutrient_events.get_location_nutrient_events", unexpected_events
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/nutrients/{location_id}/events/{event_type}")

    assert response.status_code == 403
    assert called is False
