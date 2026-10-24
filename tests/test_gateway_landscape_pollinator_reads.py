"""CAP-006 landscape and pollinator summaries are scoped, aggregate-only reads."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.landscape_conservation_reads import (  # noqa: E402
    get_location_landscape_summary,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.pollinator_health_reads import (  # noqa: E402
    get_location_pollinator_summary,
)


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "FROM habitat_zone" in query:
            columns, rows = (
                ("habitat_type", "status", "biodiversity_value", "record_count", "total_area_ha"),
                [("riparian", "active", "high", 2, Decimal("1.25"))],
            )
        elif "FROM wildlife_corridor" in query:
            columns, rows = (
                ("condition", "status", "record_count", "total_length_m", "mean_width_m"),
                [("good", "active", 1, Decimal("120"), Decimal("4.5"))],
            )
        elif "FROM hedgerow_record" in query:
            columns, rows = (
                ("condition", "status", "record_count", "total_length_m", "mean_height_m"),
                [("fair", "active", 3, Decimal("90"), Decimal("1.8"))],
            )
        elif "FROM buffer_zone_monitoring" in query:
            columns, rows = (
                ("compliant", "erosion_observed", "record_count", "first_check_date", "last_check_date"),
                [(True, False, 2, date(2026, 2, 1), date(2026, 3, 1))],
            )
        elif "FROM landscape_biodiversity_score" in query:
            columns, rows = (
                ("assessment_count", "mean_species_richness", "mean_shannon_index", "mean_habitat_diversity_index", "mean_connectivity_score", "mean_overall_score", "first_assessment_date", "last_assessment_date"),
                [(2, Decimal("18.5"), Decimal("1.2"), Decimal("1.5"), Decimal("6.5"), Decimal("7.0"), date(2026, 1, 1), date(2026, 4, 1))],
            )
        elif "FROM pollinator_observation" in query:
            columns, rows = (
                ("pollinator_type", "observation_method", "status", "record_count", "total_observed", "mean_duration_minutes", "first_observation_date", "last_observation_date"),
                [("wild_bee", "transect", "verified", 4, Decimal("42"), Decimal("15"), date(2026, 3, 1), date(2026, 3, 5))],
            )
        elif "FROM pollinator_habitat" in query:
            columns, rows = (
                ("habitat_type", "condition", "status", "record_count", "total_area_m2"),
                [("wildflower_strip", "good", "active", 2, Decimal("240"))],
            )
        elif "FROM pesticide_impact_log" in query:
            columns, rows = (
                ("toxicity_class", "pollinator_mortality_observed", "record_count", "mean_mortality_pct", "first_application_date", "last_application_date"),
                [("moderate", False, 1, Decimal("0"), date(2026, 3, 2), date(2026, 3, 2))],
            )
        elif "FROM hive_record" in query:
            columns, rows = (
                ("colony_strength", "queen_status", "hive_count", "total_honey_yield_kg", "mean_varroa_count", "last_inspection_date"),
                [("strong", "present", 2, Decimal("12"), Decimal("3"), date(2026, 4, 1))],
            )
        else:
            columns, rows = (), []
        self.description = [(column,) for column in columns]
        self.rows = rows

    def fetchall(self):
        return self.rows


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


@pytest.mark.parametrize(
    "path,resource",
    [
        ("/operator/api/landscape/{}/summary", "landscape_conservation"),
        ("/operator/api/pollinators/{}/summary", "pollinator_health"),
    ],
)
def test_landscape_and_pollinator_policies_are_exact_location_reads(path, resource):
    location_id = str(uuid4())
    assert auth_route_policy("GET", path.format(location_id), enabled=True) == {
        "resource": resource,
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path.format(location_id), enabled=True) is None
    assert auth_route_policy("GET", path.format(location_id) + "/extra", enabled=True) is None


def test_landscape_summary_sets_context_before_location_bound_aggregate_queries():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    events = []

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "landscape_conservation",
            "action": "read",
        }
        events.append("context")

    execute = _Cursor.execute

    def observe(self, query, params=None):
        if "FROM " in query:
            events.append("aggregate")
        execute(self, query, params)

    with patch("services.gateway.landscape_conservation_reads.set_operator_tenant_context", set_context), patch.object(
        _Cursor, "execute", observe
    ):
        result = get_location_landscape_summary(operator_id, location_id, connection_factory=lambda: conn)

    queries = [(query, params) for query, params in conn.queries if "FROM " in query]
    assert len(queries) == 5
    assert all("location_id = %s::uuid" in query and params == (location_id,) for query, params in queries)
    assert "status = 'verified'" in queries[3][0]
    assert "status IN ('verified', 'published')" in queries[4][0]
    for query, _ in queries:
        for private_field in ("zone_name", "corridor_name", "hedgerow_name", "gps_boundary", "description", "notes", "assessor", "metadata"):
            assert private_field not in query
    assert events[-6:] == ["context", "aggregate", "aggregate", "aggregate", "aggregate", "aggregate"]
    assert result["location_id"] == location_id
    assert result["habitats"][0]["total_area_ha"] == 1.25
    assert result["corridors"][0]["total_length_m"] == 120.0
    assert result["hedgerows"][0]["mean_height_m"] == 1.8
    assert result["verified_buffer_checks"][0]["last_check_date"] == "2026-03-01"
    assert result["verified_assessments"]["assessment_count"] == 2
    assert result["verified_assessments"]["mean_overall_score"] == 7.0
    assert conn.rolled_back and conn.closed


def test_pollinator_summary_uses_installed_schema_and_omits_identifying_fields():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    captured = {}

    def set_context(connection, **kwargs):
        assert connection is conn
        captured.update(kwargs)

    with patch("services.gateway.pollinator_health_reads.set_operator_tenant_context", set_context):
        result = get_location_pollinator_summary(operator_id, location_id, connection_factory=lambda: conn)

    queries = [(query, params) for query, params in conn.queries if "FROM " in query]
    assert len(queries) == 4
    assert all("location_id = %s::uuid" in query and params == (location_id,) for query, params in queries)
    assert "status IN ('verified', 'reviewed')" in queries[0][0]
    assert "status IN ('verified', 'reviewed')" in queries[2][0]
    assert captured == {
        "operator_id": operator_id,
        "location_id": location_id,
        "resource": "pollinator_health",
        "action": "read",
    }
    combined_sql = "\n".join(query for query, _ in queries)
    for private_field in (
        "species_name", "flower_species", "plot_id", "weather_conditions", "notes", "metadata",
        "habitat_name", "plant_species", "nesting_features", "product_name", "active_ingredient",
        "hive_id",
    ):
        assert private_field not in combined_sql
    assert "FROM pollinator_pesticide_impact" not in combined_sql
    assert "FROM pollinator_hive" not in combined_sql
    assert result["verified_observations"][0]["total_observed"] == 42.0
    assert result["habitat_inventory"][0]["total_area_m2"] == 240.0
    assert result["verified_pesticide_impacts"][0]["mean_mortality_pct"] == 0.0
    assert result["active_hives"][0]["total_honey_yield_kg"] == 12.0
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    "reader",
    [get_location_landscape_summary, get_location_pollinator_summary],
)
@pytest.mark.parametrize("operator_id,location_id", [("bad", str(uuid4())), (str(uuid4()), "bad")])
def test_invalid_scope_fails_before_connecting(reader, operator_id, location_id):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid identifiers must fail before connecting")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        reader(operator_id, location_id, connection_factory=connection_factory)
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


@pytest.mark.parametrize(
    "path,resource,module,payload",
    [
        (
            "/operator/api/landscape/{}/summary",
            "landscape_conservation",
            "services.gateway.landscape_conservation_reads.get_location_landscape_summary",
            {"location_id": "{location}", "habitats": [], "corridors": [], "hedgerows": [], "verified_buffer_checks": [], "verified_assessments": {"assessment_count": 0}},
        ),
        (
            "/operator/api/pollinators/{}/summary",
            "pollinator_health",
            "services.gateway.pollinator_health_reads.get_location_pollinator_summary",
            {"location_id": "{location}", "verified_observations": [], "habitat_inventory": [], "verified_pesticide_impacts": [], "active_hives": []},
        ),
    ],
)
def test_summary_routes_require_exact_scope_and_are_no_store(
    monkeypatch, gateway_audit_spool, path, resource, module, payload
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, granted_resource, action, granted_location):
            return (op, granted_resource, action, granted_location) == (
                operator_id, resource, "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    expected = {key: (location_id if value == "{location}" else value) for key, value in payload.items()}
    monkeypatch.setattr(module, lambda op, loc: expected if (op, loc) == (operator_id, location_id) else None)
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(path.format(location_id))
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


@pytest.mark.parametrize(
    "path,module",
    [
        ("/operator/api/landscape/{}/summary", "services.gateway.landscape_conservation_reads.get_location_landscape_summary"),
        ("/operator/api/pollinators/{}/summary", "services.gateway.pollinator_health_reads.get_location_pollinator_summary"),
    ],
)
def test_summary_routes_deny_without_matching_grant_before_reader_call(
    monkeypatch, gateway_audit_spool, path, module
):
    location_id = str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="d" * 64,
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

    def unexpected(*_args):
        nonlocal called
        called = True
        raise AssertionError("missing grant must deny before the reader")

    monkeypatch.setattr(module, unexpected)
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(path.format(location_id))
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert called is False
