"""Crop simulation result reads stay bounded, tenant-scoped and private."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.crop_simulations import (  # noqa: E402
    get_location_crop_simulation_run_detail,
    get_location_crop_simulation_runs,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_crop_simulation_runs_policy_is_exact_location_read():
    location_id = str(uuid4())
    path = f"/operator/api/crop-simulations/{location_id}/runs"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "digital_twin",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/extra", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None

    detail_path = f"{path}/{uuid4()}"
    assert auth_route_policy("GET", detail_path, enabled=True) == {
        "resource": "digital_twin",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", detail_path, enabled=True) is None
    assert auth_route_policy("GET", f"{detail_path}/extra", enabled=True) is None


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
        self.description = [(name,) for name in (
            "twin_id", "twin_name", "run_id", "started_at", "completed_at",
            "duration_ms", "final_yield", "final_yield_unit", "total_water_mm",
            "total_nitrogen_kg", "avg_soil_carbon_pct",
        )]
        self.rows = [
            (
                str(uuid4()), "North Plot Twin", str(uuid4()),
                datetime(2026, 10, 20, 8), datetime(2026, 10, 20, 8, 1),
                60, Decimal("4200.5"), "kg/ha", Decimal("85.25"),
                Decimal("32.5"), Decimal("1.72"),
            ),
            (
                str(uuid4()), "South Plot Twin", str(uuid4()),
                datetime(2026, 10, 19, 7), datetime(2026, 10, 19, 7, 2),
                120, Decimal("3800"), "kg/ha", Decimal("90"),
                Decimal("28"), Decimal("1.61"),
            ),
        ]

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


def test_crop_simulation_runs_sets_context_before_location_scoped_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "digital_twin",
            "action": "read",
        }
        conn.events.append("tenant_context")

    with patch("services.gateway.crop_simulations.set_operator_tenant_context", set_context):
        result = get_location_crop_simulation_runs(
            operator_id,
            location_id,
            limit=1,
            connection_factory=lambda: conn,
        )

    reads = [(query, params) for query, params in conn.queries if "simulation_run" in query]
    assert len(reads) == 2
    assert conn.queries[:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql"]
    for query, _params in reads:
        assert "dt.location_id = %s::uuid" in query
        assert "dt.twin_type = 'crop_simulation'" in query
        assert "dt.status IN ('active', 'archived')" in query
        assert "sr.status = 'completed'" in query
        assert "parameters" not in query.lower()
        assert "metadata" not in query.lower()
        assert "error_message" not in query.lower()
    assert reads[0][1] == (location_id,)
    assert reads[1][1] == (location_id, 2, 0)
    assert result["total_runs"] == 2
    assert result["has_more"] is True
    assert result["runs"][0]["final_yield"] == 4200.5
    assert result["runs"][0]["total_water_mm"] == 85.25
    assert "parameters" not in result["runs"][0]
    assert "metadata" not in result["runs"][0]
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (25, -1), (25, 10_001), (True, 0)],
)
def test_crop_simulation_runs_reject_invalid_pagination_before_database(limit, offset):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid pagination must fail before opening PostgreSQL")

    with pytest.raises(ValueError):
        get_location_crop_simulation_runs(
            str(uuid4()), str(uuid4()), limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


def test_crop_simulation_runs_reject_invalid_location_before_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid UUID must fail before connecting")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_crop_simulation_runs(
            str(uuid4()), "not-a-location", connection_factory=connection_factory
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


def test_crop_simulation_runs_route_returns_no_store(monkeypatch, gateway_audit_spool):
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
                operator_id, "digital_twin", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.crop_simulations.get_location_crop_simulation_runs",
        lambda op, loc, **_kwargs: {
            "location_id": loc, "total_runs": 0, "runs": []
        },
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/crop-simulations/{location_id}/runs")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_crop_simulation_runs_route_denies_missing_grant_before_handler(
    monkeypatch, gateway_audit_spool
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

    def unexpected_runs(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.crop_simulations.get_location_crop_simulation_runs",
        unexpected_runs,
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/crop-simulations/{location_id}/runs")

    assert response.status_code == 403
    assert called is False


class _DetailCursor:
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
        if "SELECT dt.id AS twin_id" in query:
            self.description = [(name,) for name in (
                "twin_id", "twin_name", "run_id", "started_at",
                "completed_at", "duration_ms", "final_yield", "final_yield_unit",
                "total_water_mm", "total_nitrogen_kg", "avg_soil_carbon_pct",
            )]
            self.one = (
                str(uuid4()), "North Plot Twin", str(uuid4()),
                datetime(2026, 10, 20, 8), datetime(2026, 10, 20, 8, 1), 60,
                Decimal("4200.5"), "kg/ha", Decimal("85.25"), Decimal("32.5"),
                Decimal("1.72"),
            )
        elif "SELECT COUNT(*)" in query:
            self.one = (2,)
        else:
            self.description = [(name,) for name in (
                "day_number", "state_date", "soil_moisture_pct", "soil_nitrogen_ppm",
                "soil_carbon_pct", "soil_temperature_c", "gdd_accumulated",
                "crop_biomass_kg_ha", "leaf_area_index", "crop_stage", "root_depth_cm",
                "rainfall_mm", "irrigation_mm", "et_actual_mm", "drainage_mm",
                "temp_avg_c", "temp_min_c", "temp_max_c", "solar_radiation_mj",
                "humidity_pct", "wind_speed_kmh", "carbon_sequestered_kg_ha",
                "carbon_emitted_kg_ha",
            )]
            self.rows = [(
                1, datetime(2026, 10, 1).date(), Decimal("35.50"), Decimal("12.3"),
                Decimal("1.234"), Decimal("22.1"), Decimal("15"), Decimal("125.4"),
                Decimal("0.42"), "emergence", Decimal("8.5"), Decimal("2.1"),
                Decimal("0"), Decimal("3.2"), Decimal("0.1"), Decimal("24"),
                Decimal("19"), Decimal("29"), Decimal("18.6"), Decimal("70"),
                Decimal("8.4"), Decimal("1.5"), Decimal("0.1"),
            ), (
                2, datetime(2026, 10, 2).date(), *([None] * 7), "vegetative",
                *([None] * 13),
            )]

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class _DetailConnection:
    autocommit = False

    def __init__(self):
        self.queries = []
        self.events = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _DetailCursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_crop_simulation_detail_sets_context_and_returns_allowlisted_daily_states():
    operator_id, location_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    conn = _DetailConnection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "digital_twin",
            "action": "read",
        }
        conn.events.append("tenant_context")

    with patch("services.gateway.crop_simulations.set_operator_tenant_context", set_context):
        result = get_location_crop_simulation_run_detail(
            operator_id, location_id, run_id, limit=1,
            connection_factory=lambda: conn,
        )

    scoped_reads = [
        (query, params) for query, params in conn.queries
        if "simulation_run AS sr" in query or "simulation_state AS ss" in query
    ]
    assert len(scoped_reads) == 3
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql", "sql"]
    for query, _params in scoped_reads:
        assert "dt.location_id = %s::uuid" in query
        assert "dt.twin_type = 'crop_simulation'" in query
        assert "dt.status IN ('active', 'archived')" in query
        assert "sr.status = 'completed'" in query
        assert "parameters" not in query.lower()
        assert "metadata" not in query.lower()
        assert "error_message" not in query.lower()
        assert "total_cost" not in query.lower()
    assert scoped_reads[0][1] == (location_id, run_id)
    assert scoped_reads[1][1] == (location_id, run_id)
    assert scoped_reads[2][1] == (location_id, run_id, 2, 0)
    assert "ORDER BY ss.day_number, ss.state_date, ss.id" in scoped_reads[2][0]
    assert result["run"]["run_id"]
    assert result["run"]["final_yield"] == 4200.5
    assert result["total_states"] == 2
    assert result["has_more"] is True
    assert result["states"][0]["state_date"] == "2026-10-01"
    assert result["states"][0]["soil_moisture_pct"] == 35.5
    assert "metadata" not in result["run"]
    assert "parameters" not in result["run"]
    assert "total_cost_usd" not in result["run"]
    assert "run_label" not in result["run"]
    assert conn.rolled_back and conn.closed


def test_crop_simulation_detail_hides_unavailable_run_without_reading_states():
    class MissingRunCursor(_DetailCursor):
        def execute(self, query, params=None):
            super().execute(query, params)
            if "SELECT dt.id AS twin_id" in query:
                self.one = None

    class MissingRunConnection(_DetailConnection):
        def cursor(self):
            return MissingRunCursor(self)

    operator_id, location_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    conn = MissingRunConnection()
    with patch("services.gateway.crop_simulations.set_operator_tenant_context") as set_context:
        result = get_location_crop_simulation_run_detail(
            operator_id,
            location_id,
            run_id,
            connection_factory=lambda: conn,
        )

    assert result is None
    set_context.assert_called_once_with(
        conn,
        operator_id=operator_id,
        location_id=location_id,
        resource="digital_twin",
        action="read",
    )
    assert len([query for query, _params in conn.queries if "simulation_state" in query]) == 0
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    ("run_id", "limit", "offset", "message"),
    [
        ("bad-run", 25, 0, "Invalid run identifier"),
        (str(uuid4()), 0, 0, "limit must be between"),
        (str(uuid4()), 25, -1, "offset must be between"),
    ],
)
def test_crop_simulation_detail_validates_before_database(run_id, limit, offset, message):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid input must fail before connecting")

    with pytest.raises(ValueError, match=message):
        get_location_crop_simulation_run_detail(
            str(uuid4()), str(uuid4()), run_id, limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


def test_crop_simulation_detail_route_returns_private_response(monkeypatch, gateway_audit_spool):
    operator_id, location_id, run_id = str(uuid4()), str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "digital_twin", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.crop_simulations.get_location_crop_simulation_run_detail",
        lambda op, loc, run, **_kwargs: {
            "location_id": loc,
            "run": {"run_id": run},
            "states": [],
        },
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/crop-simulations/{location_id}/runs/{run_id}"
        )

    assert response.status_code == 200
    assert response.json()["run"]["run_id"] == run_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_crop_simulation_detail_route_denies_missing_grant_before_handler(
    monkeypatch, gateway_audit_spool
):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
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

    def unexpected_detail(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.crop_simulations.get_location_crop_simulation_run_detail",
        unexpected_detail,
    )
    location_id, run_id = str(uuid4()), str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/crop-simulations/{location_id}/runs/{run_id}"
        )

    assert response.status_code == 403
    assert called is False
