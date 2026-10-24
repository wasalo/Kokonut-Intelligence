"""Energy Kernel reads are private, bounded, and location-scoped."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.energy_monitoring import get_location_energy_summary  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.conn.queries.append((query, params))
        self.one = None
        if "GROUP BY er.reading_type" in query:
            self.description = [(name,) for name in (
                "reading_type", "source_type", "activity_type", "reading_count",
                "total_kwh", "first_reading_date", "last_reading_date",
            )]
            self.rows = getattr(self.conn, "energy_group_rows", [
                ("consumption", "solar", "irrigation", 2, Decimal("10.50"), date(2026, 1, 2), date(2026, 1, 3)),
                ("production", "solar", "unspecified", 1, Decimal("8"), date(2026, 1, 4), date(2026, 1, 4)),
            ])
        elif "FROM energy_source AS es" in query:
            self.description = [(name,) for name in (
                "source_type", "source_count", "capacity_kw",
            )]
            self.rows = getattr(self.conn, "active_source_rows", [
                ("grid", 2, Decimal("80")),
                ("solar", 1, Decimal("15.5")),
            ])
        elif "GROUP BY es.source_type" in query:
            self.description = [(name,) for name in ("source_type", "consumption_kwh", "production_kwh")]
            self.rows = getattr(self.conn, "energy_calculation_rows", [
                ("biogas", Decimal("10"), Decimal("0")),
                ("diesel_generator", Decimal("10"), Decimal("0")),
                ("grid", Decimal("100"), Decimal("0")),
                ("solar", Decimal("20"), Decimal("40")),
            ])
        elif "GROUP BY er.reading_date" in query:
            self.description = [(name,) for name in ("reading_date", "consumption_kwh", "production_kwh")]
            self.rows = getattr(self.conn, "energy_trend_rows", [
                (date(2026, 10, 17), Decimal("10"), Decimal("0")),
                (date(2026, 10, 18), Decimal("0"), Decimal("2")),
            ])
        elif "GROUP BY res.renewable_type" in query:
            self.description = [(name,) for name in (
                "renewable_type", "source_count", "capacity_kw",
                "annual_generation_kwh", "registered_carbon_offset_kg",
            )]
            self.rows = getattr(self.conn, "renewable_asset_rows", [
                ("solar_pv", 1, Decimal("15"), Decimal("22500"), Decimal("9000")),
                ("wind", 2, Decimal("5.5"), Decimal("3000"), Decimal("1000")),
            ])
        elif "AS annual_consumption_kwh" in query:
            self.description = [("annual_consumption_kwh",)]
            self.one = getattr(self.conn, "annual_energy_row", (Decimal("20000"),))
        elif "GROUP BY er.cost_currency_code" in query:
            self.description = [(name,) for name in (
                "cost_currency_code", "total_cost", "costed_kwh", "reading_count",
            )]
            self.rows = getattr(self.conn, "energy_cost_rows", [
                ("USD", Decimal("15"), Decimal("100"), 1),
            ])
        elif "AS unclassified_cost_reading_count" in query:
            self.description = [("unclassified_cost_reading_count",)]
            self.one = getattr(self.conn, "unclassified_energy_cost_row", (0,))
        elif "FROM energy_efficiency_log AS eel" in query:
            self.description = [(name,) for name in (
                "log_date", "period", "total_consumption_kwh",
                "total_production_kwh", "net_energy_kwh", "renewable_pct",
                "carbon_intensity_kg_kwh",
            )]
            self.rows = getattr(self.conn, "daily_efficiency_rows", [
                (
                    date(2026, 10, 20), "daily", Decimal("42.25"),
                    Decimal("12.5"), Decimal("-29.75"), Decimal("18.4"),
                    Decimal("0.0312"),
                ),
            ])

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.one


class _Connection:
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


def test_energy_summary_requires_exact_policy_and_rejects_near_misses():
    location_id = str(uuid4())
    expected = {
        "resource": "energy_monitoring",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", f"/operator/api/energy/{location_id}/summary", enabled=True) == expected
    assert auth_route_policy("POST", f"/operator/api/energy/{location_id}/summary", enabled=True) is None
    assert auth_route_policy("GET", f"/operator/api/energy/{location_id}/summary/extra", enabled=True) is None


def test_energy_summary_uses_signed_context_and_verified_aggregates_only():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "energy_monitoring",
            "action": "read",
        }
        conn.events.append("tenant_context")

    def record_execute(self, query, params=None):
        conn.events.append("query")
        original_execute(self, query, params)

    original_execute = _Cursor.execute
    with patch("services.gateway.energy_monitoring.set_operator_tenant_context", set_context), patch.object(
        _Cursor, "execute", record_execute
    ):
        result = get_location_energy_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    queries = [(query, params) for query, params in conn.queries if "FROM energy_reading AS er" in query]
    assert len(queries) == 6
    renewable_query = next(query for query, _ in conn.queries if "FROM renewable_energy_source AS res" in query)
    query, params = queries[0]
    assert "er.location_id = %s::uuid" in query
    assert "er.status IN ('verified', 'approved')" in query
    assert "es.location_id = er.location_id" in query
    for private_field in ("cost_per_kwh", "total_cost", "source_name", "equipment_id", "notes", "metadata"):
        assert private_field not in query
    assert params == (location_id,)
    assert all("er.location_id = %s::uuid" in item and item_params == (location_id,) for item, item_params in queries)
    assert all("er.status IN ('verified', 'approved')" in item for item, _ in queries)
    assert "CURRENT_DATE - INTERVAL '30 days'" in queries[1][0]
    assert "CURRENT_DATE - INTERVAL '7 days'" in queries[2][0]
    assert "CURRENT_DATE - INTERVAL '365 days'" in queries[3][0]
    assert "er.reading_type = 'consumption'" in queries[3][0]
    assert "GROUP BY er.cost_currency_code" in queries[4][0]
    assert "er.cost_currency_code IS NOT NULL" in queries[4][0]
    assert "er.cost_currency_code IS NULL" in queries[5][0]
    assert "res.location_id = %s::uuid" in renewable_query
    assert "es.location_id = res.location_id" in renewable_query
    assert "res.status = 'active'" in renewable_query
    assert "SELECT res.renewable_type," in renewable_query
    assert "source_name" not in renewable_query and "metadata" not in renewable_query
    assert "res.source_id," not in renewable_query
    assert conn.events == ["query", "query", "query", "tenant_context"] + ["query"] * 9
    source_query, source_params = next(
        (query, params) for query, params in conn.queries
        if "FROM energy_source AS es" in query
    )
    assert "es.location_id = %s::uuid" in source_query
    assert "es.status = 'active'" in source_query
    assert "GROUP BY es.source_type" in source_query
    assert "source_name" not in source_query and "metadata" not in source_query
    assert source_params == (location_id,)
    efficiency_query, efficiency_params = next(
        (query, params) for query, params in conn.queries
        if "FROM energy_efficiency_log AS eel" in query
    )
    assert "eel.location_id = %s::uuid" in efficiency_query
    assert "eel.period = 'daily'" in efficiency_query
    assert "eel.status IN ('verified', 'approved')" in efficiency_query
    assert "ORDER BY eel.log_date DESC" in efficiency_query
    assert "LIMIT 12" in efficiency_query
    assert "eel.notes" not in efficiency_query and "eel.metadata" not in efficiency_query
    assert "eel.cost_per_unit_output" not in efficiency_query
    assert efficiency_params == (location_id,)
    assert result == {
        "location_id": location_id,
        "unit": "kWh",
        "verified_reading_count": 3,
        "groups": [
            {
                "reading_type": "consumption", "source_type": "solar",
                "activity_type": "irrigation", "reading_count": 2,
                "total_kwh": 10.5, "first_reading_date": "2026-01-02",
                "last_reading_date": "2026-01-03",
            },
            {
                "reading_type": "production", "source_type": "solar",
                "activity_type": "unspecified", "reading_count": 1,
                "total_kwh": 8.0, "first_reading_date": "2026-01-04",
                "last_reading_date": "2026-01-04",
            },
        ],
        "dashboard_calculations": {
            "period_days": 30,
            "total_consumption_kwh": 140.0,
            "total_production_kwh": 40.0,
            "net_energy_kwh": -100.0,
            "renewable_consumption_kwh": 30.0,
            "renewable_share_pct": 21.43,
            "legacy_carbon_estimate": {
                "model": "legacy_source_type_factors_v1",
                "total_emissions_kg_co2e": 52.5,
                "intensity_kg_co2e_per_kwh": 0.375,
                "by_source_type": [
                    {"source_type": "biogas", "consumption_kwh": 10.0, "emission_factor_kg_co2e_per_kwh": 0.05, "estimated_emissions_kg_co2e": 0.5},
                    {"source_type": "diesel_generator", "consumption_kwh": 10.0, "emission_factor_kg_co2e_per_kwh": 0.7, "estimated_emissions_kg_co2e": 7.0},
                    {"source_type": "grid", "consumption_kwh": 100.0, "emission_factor_kg_co2e_per_kwh": 0.45, "estimated_emissions_kg_co2e": 45.0},
                    {"source_type": "solar", "consumption_kwh": 20.0, "emission_factor_kg_co2e_per_kwh": 0.0, "estimated_emissions_kg_co2e": 0.0},
                ],
            },
            "registered_renewables": {
                "period_days": 365,
                "active_sources": 3,
                "total_capacity_kw": 20.5,
                "annual_generation_kwh": 25500.0,
                "registered_carbon_offset_kg": 10000.0,
                "annual_verified_consumption_kwh": 20000.0,
                "legacy_generation_coverage_pct": 100.0,
                "by_type": [
                    {
                        "renewable_type": "solar_pv", "source_count": 1,
                        "capacity_kw": 15.0, "annual_generation_kwh": 22500.0,
                        "registered_carbon_offset_kg": 9000.0,
                    },
                    {
                        "renewable_type": "wind", "source_count": 2,
                        "capacity_kw": 5.5, "annual_generation_kwh": 3000.0,
                        "registered_carbon_offset_kg": 1000.0,
                    },
                ],
            },
            "trend_7d": [
                {"reading_date": "2026-10-17", "consumption_kwh": 10.0, "production_kwh": 0.0},
                {"reading_date": "2026-10-18", "consumption_kwh": 0.0, "production_kwh": 2.0},
            ],
            "reviewed_efficiency_history": [
                {
                    "log_date": "2026-10-20", "period": "daily",
                    "total_consumption_kwh": 42.25,
                    "total_production_kwh": 12.5,
                    "net_energy_kwh": -29.75,
                    "renewable_pct": 18.4,
                    "carbon_intensity_kg_kwh": 0.0312,
                },
            ],
            "active_sources_by_type": [
                {"source_type": "grid", "source_count": 2, "capacity_kw": 80.0},
                {"source_type": "solar", "source_count": 1, "capacity_kw": 15.5},
            ],
            "energy_costs": {
                "period_days": 30,
                "by_currency": [{
                    "currency_code": "USD", "total_cost": 15.0,
                    "costed_kwh": 100.0, "effective_cost_per_kwh": 0.15,
                    "reading_count": 1,
                }],
                "unclassified_cost_reading_count": 0,
                "comparable_total": {
                    "currency_code": "USD", "total_cost": 15.0,
                    "effective_cost_per_kwh": 0.15,
                },
            },
        },
    }
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize("bad_operator,bad_location", [("bad", str(uuid4())), (str(uuid4()), "bad")])
def test_invalid_energy_scope_fails_before_database_connection(bad_operator, bad_location):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before connecting")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_location_energy_summary(bad_operator, bad_location, connection_factory=connection_factory)
    assert not opened


def test_energy_dashboard_calculations_handle_empty_verified_readings():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    conn.energy_group_rows = []
    conn.energy_calculation_rows = []
    conn.energy_trend_rows = []
    conn.renewable_asset_rows = []
    conn.annual_energy_row = (Decimal("0"),)
    conn.daily_efficiency_rows = []
    conn.active_source_rows = []
    conn.energy_cost_rows = []
    conn.unclassified_energy_cost_row = (0,)

    with patch("services.gateway.energy_monitoring.set_operator_tenant_context"):
        result = get_location_energy_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert result["verified_reading_count"] == 0
    assert result["groups"] == []
    assert result["dashboard_calculations"] == {
        "period_days": 30,
        "total_consumption_kwh": 0,
        "total_production_kwh": 0,
        "net_energy_kwh": 0,
        "renewable_consumption_kwh": 0,
        "renewable_share_pct": 0,
        "legacy_carbon_estimate": {
            "model": "legacy_source_type_factors_v1",
            "total_emissions_kg_co2e": 0,
            "intensity_kg_co2e_per_kwh": 0,
            "by_source_type": [],
        },
        "registered_renewables": {
            "period_days": 365,
            "active_sources": 0,
            "total_capacity_kw": 0,
            "annual_generation_kwh": 0,
            "registered_carbon_offset_kg": 0,
            "annual_verified_consumption_kwh": 0,
            "legacy_generation_coverage_pct": 0,
            "by_type": [],
        },
        "trend_7d": [],
        "reviewed_efficiency_history": [],
        "active_sources_by_type": [],
        "energy_costs": {
            "period_days": 30,
            "by_currency": [],
            "unclassified_cost_reading_count": 0,
            "comparable_total": None,
        },
    }
    assert conn.rolled_back and conn.closed


def test_energy_cost_summary_keeps_currencies_separate_and_counts_unknown_rows():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    conn.energy_cost_rows = [
        ("DOP", Decimal("600"), Decimal("1000"), 5),
        ("USD", Decimal("150"), Decimal("1000"), 4),
    ]
    conn.unclassified_energy_cost_row = (2,)

    with patch("services.gateway.energy_monitoring.set_operator_tenant_context"):
        result = get_location_energy_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    costs = result["dashboard_calculations"]["energy_costs"]
    assert [row["currency_code"] for row in costs["by_currency"]] == ["DOP", "USD"]
    assert costs["unclassified_cost_reading_count"] == 2
    assert costs["comparable_total"] is None
    assert conn.rolled_back and conn.closed


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


def test_energy_route_requires_grant_and_returns_no_store_summary(monkeypatch, gateway_audit_spool):
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
                operator_id, "energy_monitoring", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    expected = {
        "location_id": location_id,
        "unit": "kWh",
        "verified_reading_count": 0,
        "groups": [],
        "dashboard_calculations": {
            "period_days": 30,
            "total_consumption_kwh": 0,
            "total_production_kwh": 0,
            "net_energy_kwh": 0,
            "renewable_consumption_kwh": 0,
            "renewable_share_pct": 0,
            "legacy_carbon_estimate": {
                "model": "legacy_source_type_factors_v1",
                "total_emissions_kg_co2e": 0,
                "intensity_kg_co2e_per_kwh": 0,
                "by_source_type": [],
            },
            "registered_renewables": {
                "period_days": 365,
                "active_sources": 0,
                "total_capacity_kw": 0,
                "annual_generation_kwh": 0,
                "registered_carbon_offset_kg": 0,
                "annual_verified_consumption_kwh": 0,
                "legacy_generation_coverage_pct": 0,
                "by_type": [],
            },
            "trend_7d": [],
            "reviewed_efficiency_history": [],
            "active_sources_by_type": [],
        },
    }
    monkeypatch.setattr(
        "services.gateway.energy_monitoring.get_location_energy_summary",
        lambda op, loc: expected if (op, loc) == (operator_id, location_id) else None,
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/energy/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_energy_route_denies_missing_location_grant_before_query(monkeypatch, gateway_audit_spool):
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
        "services.gateway.energy_monitoring.get_location_energy_summary", unexpected_summary
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/energy/{location_id}/summary")

    assert response.status_code == 403
    assert called is False
