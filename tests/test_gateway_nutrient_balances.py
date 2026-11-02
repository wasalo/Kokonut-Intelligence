"""Nutrient Kernel reads expose only governed, scoped balance aggregates."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402
from services.gateway.nutrient_balances import (  # noqa: E402
    get_location_nutrient_balances,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def _nutrient_balances_payload(
    location_id, *, limit=25, offset=0, total_summaries=1
):
    nutrient = {"input_kg": 120.0, "removal_kg": 96.0, "surplus_kg": 24.0}
    return {
        "location_id": location_id,
        "total_summaries": total_summaries,
        "limit": limit,
        "offset": offset,
        "has_more": False,
        "balances": [{
            "season": "2026-wet",
            "crop_name": "maize",
            "budget_count": 3,
            "area_ha": 8.5,
            "nitrogen": nutrient,
            "phosphorus": {"input_kg": 45.0, "removal_kg": 30.0, "surplus_kg": 15.0},
            "potassium": {"input_kg": 70.0, "removal_kg": 63.0, "surplus_kg": 7.0},
        }],
    }


def test_nutrient_balances_policy_is_exact_location_read():
    location_id = str(uuid4())
    path = f"/operator/api/nutrients/{location_id}/balances"
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
            self.one = (self.conn.total,)
            return
        self.description = [(name,) for name in (
            "season", "crop_name", "budget_count", "area_ha",
            "nitrogen_input_kg", "nitrogen_removal_kg", "nitrogen_surplus_kg",
            "phosphorus_input_kg", "phosphorus_removal_kg", "phosphorus_surplus_kg",
            "potassium_input_kg", "potassium_removal_kg", "potassium_surplus_kg",
        )]
        self.rows = self.conn.result_rows

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class _Connection:
    autocommit = False

    def __init__(self, *, total=2, result_rows=None):
        self.queries = []
        self.events = []
        self.rolled_back = False
        self.closed = False
        self.total = total
        self.result_rows = result_rows if result_rows is not None else [
            (
                "2026-wet", "maize", 3, 8.5,
                120, 96, 24, 45, 30, 15, 70, 63, 7,
            ),
            (
                "2026-dry", "beans", 1, 2.0,
                25, 27, -2, 12, 8, 4, 18, 20, -2,
            ),
        ]

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_nutrient_balance_read_sets_context_and_returns_only_grouped_verified_balances():
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

    with patch("services.gateway.nutrient_balances.set_operator_tenant_context", set_context):
        result = get_location_nutrient_balances(
            operator_id,
            location_id,
            limit=1,
            offset=0,
            connection_factory=lambda: conn,
        )

    reads = [(query, params) for query, params in conn.queries if "v_nutrient_balance" in query]
    assert len(reads) == 2
    assert conn.queries[:3] == [
        ("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    assert conn.events == ["sql", "sql", "sql", "tenant_context", "sql", "sql"]
    for query, _params in reads:
        assert "location_id = %s::uuid" in query
    assert reads[0][1] == (location_id,)
    assert reads[1][1] == (location_id, 2, 0)
    assert "GROUP BY season, crop_name" in reads[1][0]
    assert result["total_summaries"] == 2
    assert result["has_more"] is True
    assert result["balances"] == [{
        "season": "2026-wet",
        "crop_name": "maize",
        "budget_count": 3,
        "area_ha": 8.5,
        "nitrogen": {"input_kg": 120.0, "removal_kg": 96.0, "surplus_kg": 24.0},
        "phosphorus": {"input_kg": 45.0, "removal_kg": 30.0, "surplus_kg": 15.0},
        "potassium": {"input_kg": 70.0, "removal_kg": 63.0, "surplus_kg": 7.0},
    }]
    assert "notes" not in result["balances"][0]
    assert "total_cost" not in result["balances"][0]
    assert conn.rolled_back and conn.closed


def test_nutrient_balance_read_stops_pagination_at_maximum_offset():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection(total=10_002)

    with patch("services.gateway.nutrient_balances.set_operator_tenant_context"):
        result = get_location_nutrient_balances(
            operator_id,
            location_id,
            limit=1,
            offset=10_000,
            connection_factory=lambda: conn,
        )

    assert result["total_summaries"] == 10_002
    assert result["offset"] == 10_000
    assert len(result["balances"]) == 1
    assert result["has_more"] is False


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(0, 0), (51, 0), (25, -1), (25, 10_001), (True, 0)],
)
def test_nutrient_balance_read_rejects_invalid_pagination_before_database(limit, offset):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid pagination must fail before opening PostgreSQL")

    with pytest.raises(ValueError):
        get_location_nutrient_balances(
            str(uuid4()), str(uuid4()), limit=limit, offset=offset,
            connection_factory=connection_factory,
        )
    assert opened is False


def test_nutrient_balance_read_rejects_invalid_location_before_database():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid UUID must fail before connecting")

    with pytest.raises(ValueError, match="Invalid location identifier"):
        get_location_nutrient_balances(
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


@pytest.mark.parametrize("limit,offset", [(25, 0), (25, 10_000)])
def test_nutrient_balances_route_returns_no_store(
    monkeypatch, gateway_audit_spool, limit, offset
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
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

    total_summaries = 10_002 if offset == 10_000 else 1
    monkeypatch.setattr(
        "services.gateway.nutrient_balances.get_location_nutrient_balances",
        lambda _op, loc, **_kwargs: _nutrient_balances_payload(
            loc, limit=limit, offset=offset, total_summaries=total_summaries
        ),
    )
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(
            f"/operator/api/nutrients/{location_id}/balances?limit={limit}&offset={offset}"
        )

    assert response.status_code == 200
    assert response.json() == _nutrient_balances_payload(
        location_id, limit=limit, offset=offset, total_summaries=total_summaries
    )
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}


def test_nutrient_balances_openapi_publishes_strict_aggregate_projection(
    gateway_audit_spool,
):
    app = create_app()
    openapi = app.openapi()
    response_schema = openapi["paths"][
        "/operator/api/nutrients/{location_id}/balances"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/NutrientBalancesResponse"}
    schemas = openapi["components"]["schemas"]
    for name in (
        "NutrientBalancesResponse",
        "NutrientBalanceGroupResponse",
        "NutrientQuantitiesResponse",
    ):
        assert schemas[name]["additionalProperties"] is False
    assert schemas["NutrientBalancesResponse"]["properties"]["balances"]["maxItems"] == 50
    assert schemas["NutrientBalanceGroupResponse"]["properties"]["budget_count"]["minimum"] == 1
    assert schemas["NutrientBalanceGroupResponse"]["properties"]["season"]["maxLength"] == 100


@pytest.mark.parametrize(
    "invalid_field",
    [
        "top_level_extra",
        "nested_extra",
        "negative_count",
        "non_finite",
        "location_mismatch",
        "limit_mismatch",
        "offset_mismatch",
        "too_many_for_limit",
        "inconsistent_has_more",
        "impossible_page_total",
        "coercive_has_more",
    ],
)
def test_nutrient_balances_route_rejects_invalid_success_projection(
    monkeypatch, gateway_audit_spool, invalid_field
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    payload = _nutrient_balances_payload(location_id)
    if invalid_field == "top_level_extra":
        payload["budget_ids"] = [str(uuid4())]
    elif invalid_field == "nested_extra":
        payload["balances"][0]["notes"] = "private"
    elif invalid_field == "negative_count":
        payload["total_summaries"] = -1
    elif invalid_field == "non_finite":
        payload["balances"][0]["nitrogen"]["input_kg"] = float("inf")
    elif invalid_field == "location_mismatch":
        payload["location_id"] = str(uuid4())
    elif invalid_field == "limit_mismatch":
        payload["limit"] = 24
    elif invalid_field == "offset_mismatch":
        payload["offset"] = 1
    elif invalid_field == "too_many_for_limit":
        payload["total_summaries"] = 26
        payload["balances"] = [dict(payload["balances"][0]) for _ in range(26)]
    elif invalid_field == "impossible_page_total":
        payload["total_summaries"] = 0
        payload["has_more"] = False
    elif invalid_field == "coercive_has_more":
        payload["has_more"] = "false"
    else:
        payload["has_more"] = True

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
                operator_id, "nutrient_budget", "read", location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.nutrient_balances.get_location_nutrient_balances",
        lambda *_args, **_kwargs: payload,
    )
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(
            f"/operator/api/nutrients/{location_id}/balances?limit=25&offset=0"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Nutrient balances unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def test_nutrient_balances_route_denies_missing_grant_before_handler(
    monkeypatch, gateway_audit_spool
):
    session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
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

    def unexpected_balances(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing tenant grant must deny before data access")

    monkeypatch.setattr(
        "services.gateway.nutrient_balances.get_location_nutrient_balances",
        unexpected_balances,
    )
    location_id = str(uuid4())
    with TestClient(create_app(), cookies={"kokonut_operator_session": "synthetic-session"}) as client:
        response = client.get(f"/operator/api/nutrients/{location_id}/balances")

    assert response.status_code == 403
    assert called is False
