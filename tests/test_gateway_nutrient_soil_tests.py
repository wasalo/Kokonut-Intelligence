"""Tests for the private, tenant-scoped nutrient soil-test read."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.nutrient_soil_tests import get_location_soil_tests  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_nutrient_soil_tests_policy_is_exact_location_read():
    location_id = str(uuid4())
    path = f"/operator/api/nutrients/{location_id}/soil-tests"
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
        test_id, plot_id = uuid4(), uuid4()
        self.conn.test_id = test_id
        self.conn.plot_id = plot_id
        self.description = [(name,) for name in (
            "id", "plot_id", "test_date", "soil_ph", "organic_matter_pct",
            "nitrogen_ppm", "phosphorus_ppm", "potassium_ppm", "cec",
            "recommended_n_kg_ha", "recommended_p_kg_ha",
            "recommended_k_kg_ha", "status",
        )]
        self.rows = [
            (
                test_id, plot_id, date(2026, 10, 23), 6.2, 4.5,
                18, 12, 95, 7.1, 42, 18, 30, "verified",
            ),
            (
                uuid4(), None, date(2026, 10, 20), 5.8, None,
                None, 9, 70, None, None, None, None, "recorded",
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


def test_soil_test_read_sets_context_and_returns_bounded_scoped_projection():
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

    with patch("services.gateway.nutrient_soil_tests.set_operator_tenant_context", set_context):
        result = get_location_soil_tests(
            operator_id,
            location_id,
            limit=1,
            offset=0,
            connection_factory=lambda: conn,
        )

    reads = [(query, params) for query, params in conn.queries if "soil_test_recommendation" in query]
    assert len(reads) == 2
    assert conn.queries[:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql"]
    for query, _params in reads:
        assert "soil.location_id = %s::uuid" in query
        assert "soil.status IN ('recorded', 'verified')" in query
    assert reads[0][1] == (location_id,)
    assert reads[1][1] == (location_id, 2, 0)
    page_sql = reads[1][0]
    assert "farm.location_id = soil.location_id" in page_sql
    assert "ORDER BY soil.test_date DESC, soil.id DESC" in page_sql
    assert "notes" not in page_sql.lower()
    assert "metadata" not in page_sql.lower()
    assert result == {
        "location_id": location_id,
        "total_tests": 2,
        "limit": 1,
        "offset": 0,
        "has_more": True,
        "soil_tests": [{
            "test_id": str(conn.test_id),
            "plot_id": str(conn.plot_id),
            "test_date": "2026-10-23",
            "status": "verified",
            "measurements": {
                "soil_ph": 6.2,
                "organic_matter_pct": 4.5,
                "nitrogen_ppm": 18.0,
                "phosphorus_ppm": 12.0,
                "potassium_ppm": 95.0,
                "cec": 7.1,
            },
            "recommendations_kg_ha": {
                "nitrogen": 42.0,
                "phosphorus": 18.0,
                "potassium": 30.0,
            },
        }],
    }
    assert conn.rolled_back and conn.closed


def test_recorded_soil_test_status_is_not_promoted_to_verified():
    conn = _Connection()
    operator_id, location_id = str(uuid4()), str(uuid4())

    with patch("services.gateway.nutrient_soil_tests.set_operator_tenant_context"):
        result = get_location_soil_tests(
            operator_id,
            location_id,
            limit=2,
            connection_factory=lambda: conn,
        )

    assert [row["status"] for row in result["soil_tests"]] == ["verified", "recorded"]
    assert result["soil_tests"][1]["plot_id"] is None


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (25, -1), (25, 10_001), (True, 0)],
)
def test_soil_test_read_rejects_invalid_pagination_before_database(limit, offset):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid pagination must fail before opening PostgreSQL")

    with pytest.raises(ValueError):
        get_location_soil_tests(
            str(uuid4()), str(uuid4()), limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


def test_soil_test_read_rejects_invalid_location_before_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid UUID must fail before connecting")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_soil_tests(
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


def test_soil_test_route_returns_no_store(monkeypatch, gateway_audit_spool):
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

        def has_scope(self, op, resource, action, location):
            return (op, resource, action, location) == (
                operator_id, "nutrient_budget", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.nutrient_soil_tests.get_location_soil_tests",
        lambda op, loc, **_kwargs: {
            "location_id": loc, "total_tests": 1, "soil_tests": []
        },
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/nutrients/{location_id}/soil-tests")

    assert response.status_code == 200
    assert response.json()["location_id"] == location_id
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_soil_test_route_denies_missing_grant_before_handler(
    monkeypatch, gateway_audit_spool
):
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
    called = False

    def unexpected_soil_tests(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.nutrient_soil_tests.get_location_soil_tests",
        unexpected_soil_tests,
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/nutrients/{location_id}/soil-tests")

    assert response.status_code == 403
    assert called is False
