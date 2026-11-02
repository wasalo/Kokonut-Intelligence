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
                getattr(self.connection, "landscape_habitat_rows", [("riparian", "active", "high", 2, Decimal("1.25"))]),
            )
        elif "FROM wildlife_corridor" in query:
            columns, rows = (
                ("condition", "status", "record_count", "total_length_m", "mean_width_m", "total_width_m", "width_value_count"),
                getattr(self.connection, "landscape_corridor_rows", [("good", "active", 1, Decimal("120"), Decimal("4.5"), Decimal("4.5"), 1)]),
            )
        elif "FROM hedgerow_record" in query:
            columns, rows = (
                ("condition", "status", "record_count", "total_length_m", "mean_height_m"),
                [("fair", "active", 3, Decimal("90"), Decimal("1.8"))],
            )
        elif "FROM buffer_zone_monitoring" in query:
            columns, rows = (
                ("compliant", "erosion_observed", "record_count", "first_check_date", "last_check_date"),
                getattr(self.connection, "landscape_buffer_rows", [(True, False, 2, date(2026, 2, 1), date(2026, 3, 1))]),
            )
        elif "FROM landscape_biodiversity_score" in query:
            columns, rows = (
                ("assessment_count", "mean_species_richness", "mean_shannon_index", "mean_habitat_diversity_index", "mean_connectivity_score", "mean_overall_score", "first_assessment_date", "last_assessment_date"),
                [(2, Decimal("18.5"), Decimal("1.2"), Decimal("1.5"), Decimal("6.5"), Decimal("7.0"), date(2026, 1, 1), date(2026, 4, 1))],
            )
        elif "FROM pollinator_observation" in query and "AS observation_count" in query:
            columns, rows = (
                ("pollinator_type", "observation_count", "avg_count", "max_count", "first_observation_date", "last_observation_date", "first_half_avg", "second_half_avg", "total_count"),
                getattr(self.connection, "trend_rows", [("wild_bee", 4, Decimal("12"), 20, date(2026, 3, 1), date(2026, 3, 20), Decimal("10"), Decimal("12"), Decimal("48"))]),
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
                ("toxicity_class", "pollinator_mortality_observed", "record_count", "mean_mortality_pct", "recent_record_count", "recent_mortality_events", "first_application_date", "last_application_date"),
                getattr(self.connection, "pesticide_rows", [("moderate", False, 1, Decimal("0"), 1, 0, date(2026, 3, 2), date(2026, 3, 2))]),
            )
        elif "FROM hive_record" in query:
            columns, rows = (
                ("colony_strength", "queen_status", "hive_count", "total_honey_yield_kg", "mean_varroa_count", "strength_score_count", "mean_strength_score", "last_inspection_date"),
                [("strong", "present", 2, Decimal("12"), Decimal("3"), 1, Decimal("8.5"), date(2026, 4, 1))],
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


def _landscape_summary_payload(location_id):
    return {
        "location_id": location_id,
        "habitats": [{
            "habitat_type": "riparian",
            "status": "active",
            "biodiversity_value": "high",
            "record_count": 2,
            "total_area_ha": 1.25,
        }],
        "corridors": [{
            "condition": "good",
            "status": "active",
            "record_count": 1,
            "total_length_m": 120.0,
            "mean_width_m": 4.5,
        }],
        "hedgerows": [{
            "condition": "fair",
            "status": "active",
            "record_count": 3,
            "total_length_m": 90.0,
            "mean_height_m": 1.8,
        }],
        "verified_buffer_checks": [{
            "compliant": True,
            "erosion_observed": False,
            "record_count": 2,
            "first_check_date": "2026-02-01",
            "last_check_date": "2026-03-01",
        }],
        "verified_assessments": {
            "assessment_count": 2,
            "mean_species_richness": 18.5,
            "mean_shannon_index": 1.2,
            "mean_habitat_diversity_index": 1.5,
            "mean_connectivity_score": 6.5,
            "mean_overall_score": 7.0,
            "first_assessment_date": "2026-01-01",
            "last_assessment_date": "2026-04-01",
        },
        "dashboard_calculations": {
            "active_habitats": {
                "zone_count": 2,
                "total_area_ha": 1.25,
                "critical_habitats": 0,
                "high_value_habitats": 2,
            },
            "active_corridors": {
                "corridor_count": 1,
                "healthy_corridors": 1,
                "total_length_m": 120.0,
                "mean_width_m": 4.5,
            },
            "verified_buffer_checks": {
                "total_checks": 2,
                "compliant_checks": 2,
                "compliance_pct": 100.0,
                "erosion_incidents": 0,
            },
            "legacy_connectivity_ratio_pct": 50.0,
        },
    }


def _pollinator_summary_payload(location_id):
    return {
        "location_id": location_id,
        "verified_observations": [{
            "pollinator_type": "wild_bee",
            "observation_method": "transect",
            "status": "verified",
            "record_count": 2,
            "total_observed": 42.0,
            "mean_duration_minutes": 15.0,
            "first_observation_date": "2026-03-01",
            "last_observation_date": "2026-03-20",
        }],
        "observation_trends": [{
            "pollinator_type": "wild_bee",
            "observation_count": 2,
            "avg_count": 21.0,
            "max_count": 30,
            "first_observation_date": "2026-03-01",
            "last_observation_date": "2026-03-20",
            "total_count": 42.0,
            "trend": "increasing",
            "change_pct": 20.0,
        }],
        "habitat_inventory": [{
            "habitat_type": "wildflower_strip",
            "condition": "good",
            "status": "active",
            "record_count": 1,
            "total_area_m2": 240.0,
        }],
        "verified_pesticide_impacts": [{
            "toxicity_class": "moderate",
            "pollinator_mortality_observed": False,
            "record_count": 1,
            "mean_mortality_pct": 0.0,
            "first_application_date": "2026-03-04",
            "last_application_date": "2026-03-04",
        }],
        "pesticide_risk_summary": {
            "period_days": 90,
            "total_applications": 1,
            "overall_risk": "low",
            "risk_distribution": {
                "low": 0,
                "moderate": 1,
                "high": 0,
                "very_high": 0,
                "unknown": 0,
            },
            "mortality_events": 0,
        },
        "active_hives": [{
            "colony_strength": "strong",
            "queen_status": "present",
            "hive_count": 2,
            "total_honey_yield_kg": 12.0,
            "mean_varroa_count": 0.5,
            "last_inspection_date": "2026-03-19",
        }],
        "active_hive_summary": {
            "total_hives": 2,
            "avg_colony_strength_score": 8.5,
        },
    }


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
    conn.landscape_habitat_rows = [
        ("riparian", "active", "high", 2, Decimal("1.25")),
        ("wetland", "active", "critical", 1, Decimal("0.75")),
        ("forest_patch", "inactive", "critical", 4, Decimal("8.0")),
    ]
    conn.landscape_corridor_rows = [
        ("good", "active", 2, Decimal("120"), Decimal("4.5"), Decimal("4.5"), 1),
        ("fair", "active", 2, Decimal("50"), Decimal("2.5"), Decimal("5.0"), 2),
        ("excellent", "inactive", 7, Decimal("900"), Decimal("3.0"), Decimal("21.0"), 7),
    ]
    conn.landscape_buffer_rows = [
        (True, False, 2, date(2026, 2, 1), date(2026, 3, 1)),
        (False, True, 1, date(2026, 1, 1), date(2026, 1, 1)),
    ]
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
    assert result["dashboard_calculations"] == {
        "active_habitats": {
            "zone_count": 3,
            "total_area_ha": 2.0,
            "critical_habitats": 1,
            "high_value_habitats": 2,
        },
        "active_corridors": {
            "corridor_count": 4,
            "healthy_corridors": 2,
            "total_length_m": 170.0,
            "mean_width_m": 3.17,
        },
        "verified_buffer_checks": {
            "total_checks": 3,
            "compliant_checks": 2,
            "compliance_pct": 66.7,
            "erosion_incidents": 1,
        },
        "legacy_connectivity_ratio_pct": 66.7,
    }
    assert "total_width_m" not in result["corridors"][0]
    assert "width_value_count" not in result["corridors"][0]
    assert conn.rolled_back and conn.closed


def test_landscape_dashboard_calculations_are_zero_safe_for_empty_location():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    conn.landscape_habitat_rows = []
    conn.landscape_corridor_rows = []
    conn.landscape_buffer_rows = []

    with patch("services.gateway.landscape_conservation_reads.set_operator_tenant_context"):
        result = get_location_landscape_summary(operator_id, location_id, connection_factory=lambda: conn)

    assert result["dashboard_calculations"] == {
        "active_habitats": {
            "zone_count": 0,
            "total_area_ha": 0,
            "critical_habitats": 0,
            "high_value_habitats": 0,
        },
        "active_corridors": {
            "corridor_count": 0,
            "healthy_corridors": 0,
            "total_length_m": 0,
            "mean_width_m": 0,
        },
        "verified_buffer_checks": {
            "total_checks": 0,
            "compliant_checks": 0,
            "compliance_pct": 0,
            "erosion_incidents": 0,
        },
        "legacy_connectivity_ratio_pct": 0,
    }
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
    assert len(queries) == 5
    assert all("location_id = %s::uuid" in query and params == (location_id,) for query, params in queries)
    assert "status IN ('verified', 'reviewed')" in queries[0][0]
    assert "status IN ('verified', 'reviewed')" in queries[3][0]
    assert "CURRENT_DATE - INTERVAL '15 days'" in queries[1][0]
    assert "CURRENT_DATE - INTERVAL '30 days'" in queries[1][0]
    assert "CURRENT_DATE - INTERVAL '90 days'" in queries[3][0]
    assert "AVG(colony_strength_score)" in queries[4][0]
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
    assert result["observation_trends"][0]["trend"] == "increasing"
    assert result["observation_trends"][0]["change_pct"] == 20.0
    assert result["observation_trends"][0]["last_observation_date"] == "2026-03-20"
    assert result["habitat_inventory"][0]["total_area_m2"] == 240.0
    assert result["verified_pesticide_impacts"][0]["mean_mortality_pct"] == 0.0
    assert result["pesticide_risk_summary"] == {
        "period_days": 90,
        "total_applications": 1,
        "overall_risk": "low",
        "risk_distribution": {"low": 0, "moderate": 1, "high": 0, "very_high": 0, "unknown": 0},
        "mortality_events": 0,
    }
    assert result["active_hives"][0]["total_honey_yield_kg"] == 12.0
    assert result["active_hive_summary"] == {"total_hives": 2, "avg_colony_strength_score": 8.5}
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    "toxicity_class,record_count,mortality_events,expected_risk",
    [("high", 3, 0, "critical"), ("high", 1, 0, "elevated"), ("moderate", 4, 0, "low"), ("low", 1, 1, "critical")],
)
def test_pollinator_advisory_risk_preserves_legacy_thresholds(
    toxicity_class, record_count, mortality_events, expected_risk,
):
    location_id = str(uuid4())
    conn = _Connection()
    conn.pesticide_rows = [(
        toxicity_class, mortality_events > 0, record_count, Decimal("1.5"),
        record_count, mortality_events, date(2026, 3, 2), date(2026, 3, 2),
    )]

    with patch("services.gateway.pollinator_health_reads.set_operator_tenant_context"):
        result = get_location_pollinator_summary(
            str(uuid4()), location_id, connection_factory=lambda: conn,
        )

    assert result["pesticide_risk_summary"]["overall_risk"] == expected_risk
    assert result["pesticide_risk_summary"]["total_applications"] == record_count
    assert result["pesticide_risk_summary"]["mortality_events"] == mortality_events


@pytest.mark.parametrize(
    "first_avg,second_avg,expected_trend,expected_change",
    [(10, 11, "stable", 10.0), (10, 9, "stable", -10.0), (10, 8, "decreasing", -20.0), (0, 5, "insufficient_data", 0)],
)
def test_observation_trend_preserves_legacy_thresholds_and_zero_baseline(
    first_avg, second_avg, expected_trend, expected_change,
):
    location_id = str(uuid4())
    conn = _Connection()
    conn.trend_rows = [(
        "wild_bee", 2, Decimal("10"), 12, date(2026, 3, 1), date(2026, 3, 20),
        Decimal(str(first_avg)), Decimal(str(second_avg)), Decimal("20"),
    )]

    with patch("services.gateway.pollinator_health_reads.set_operator_tenant_context"):
        result = get_location_pollinator_summary(
            str(uuid4()), location_id, connection_factory=lambda: conn,
        )

    trend = result["observation_trends"][0]
    assert trend["trend"] == expected_trend
    assert trend["change_pct"] == expected_change


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
            _landscape_summary_payload("{location}"),
        ),
        (
            "/operator/api/pollinators/{}/summary",
            "pollinator_health",
            "services.gateway.pollinator_health_reads.get_location_pollinator_summary",
            _pollinator_summary_payload("{location}"),
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


def test_landscape_summary_response_schema_is_published_and_strict(
    monkeypatch, gateway_audit_spool
):
    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: None)
    app = create_app()
    operation = app.openapi()["paths"][
        "/operator/api/landscape/{location_id}/summary"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LandscapeSummaryResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    for name in (
        "LandscapeSummaryResponse",
        "LandscapeHabitatAggregate",
        "LandscapeCorridorAggregate",
        "LandscapeHedgerowAggregate",
        "LandscapeBufferCheckAggregate",
        "VerifiedLandscapeAssessments",
        "LandscapeDashboardCalculations",
    ):
        assert schemas[name]["additionalProperties"] is False
    summary = schemas["LandscapeSummaryResponse"]["properties"]
    assert summary["habitats"]["maxItems"] == 200
    assert summary["corridors"]["maxItems"] == 30
    assert summary["hedgerows"]["maxItems"] == 25
    assert summary["verified_buffer_checks"]["maxItems"] == 9
    assert schemas["LandscapeHabitatAggregate"]["properties"]["habitat_type"]["enum"] == [
        "wetland", "riparian", "forest_patch", "grassland", "hedgerow",
        "orchard", "agroforestry", "other",
    ]


@pytest.mark.parametrize(
    "invalid_field",
    [
        "top_level_extra",
        "nested_extra",
        "unknown_habitat_type",
        "negative_count",
        "non_finite",
        "percentage",
        "location_mismatch",
    ],
)
def test_landscape_summary_rejects_invalid_projection_with_private_error(
    monkeypatch, gateway_audit_spool, invalid_field
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    payload = _landscape_summary_payload(location_id)
    if invalid_field == "top_level_extra":
        payload["source_ids"] = [str(uuid4())]
    elif invalid_field == "nested_extra":
        payload["habitats"][0]["private_note"] = "must not be returned"
    elif invalid_field == "unknown_habitat_type":
        payload["habitats"][0]["habitat_type"] = "unknown"
    elif invalid_field == "negative_count":
        payload["habitats"][0]["record_count"] = -1
    elif invalid_field == "non_finite":
        payload["verified_assessments"]["mean_overall_score"] = float("nan")
    elif invalid_field == "percentage":
        payload["dashboard_calculations"]["verified_buffer_checks"]["compliance_pct"] = 101
    else:
        payload["location_id"] = str(uuid4())

    session = SimpleNamespace(
        session_id=str(uuid4()), session_token_hash="f" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return session

        def has_scope(self, op, resource, action, scoped_location):
            return (op, resource, action, scoped_location) == (
                operator_id, "landscape_conservation", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.landscape_conservation_reads.get_location_landscape_summary",
        lambda *_args: payload,
    )
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/landscape/{location_id}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "Landscape summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


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
