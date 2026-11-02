"""True-cost Gateway access stays location-scoped and read-only."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.gateway.true_cost import get_true_cost_summary  # noqa: E402


def _true_cost_payload(location_id):
    statement = {
        "location_id": location_id,
        "market_costs_usd": 500.0,
        "market_revenue_usd": 1000.0,
        "market_profit_usd": 500.0,
        "hidden_costs_usd": 20.0,
        "natural_capital_value_usd": 30.0,
        "social_capital_value_usd": 40.0,
        "true_profit_usd": 550.0,
        "true_profit_margin_pct": 55.0,
        "hidden_cost_ratio_pct": 4.0,
    }
    hidden_costs = {
        "location_id": location_id,
        "total_hidden_costs_usd": 20.0,
        "total_observations": 1,
        "by_category": [{"category": "pollution", "total_usd": 20.0}],
        "details": [{
            "category": "pollution",
            "subcategory": "water_pollution",
            "count": 1,
            "total_usd": 20.0,
            "avg_usd": 20.0,
        }],
    }
    natural_capital = {
        "location_id": location_id,
        "total_natural_capital_value_usd": 30.0,
        "by_type": [{
            "capital_type": "water",
            "count": 1,
            "total_quantity": 10.0,
            "avg_price_per_unit": 3.0,
            "total_value_usd": 30.0,
        }],
    }
    social_impact = {
        "location_id": location_id,
        "total_social_impact_value_usd": 40.0,
        "total_beneficiaries": 2,
        "by_category": [{
            "category": "training",
            "count": 1,
            "total_beneficiaries": 2,
            "total_value_usd": 40.0,
            "avg_value_per_intervention": 40.0,
        }],
    }
    capital_flows = {
        "location_id": location_id,
        "total_flows": 1,
        "total_flow_value_usd": 15.0,
        "flows": [{
            "from_capital": "financial",
            "to_capital": "natural",
            "flow_type": "investment",
            "count": 1,
            "total_value_usd": 15.0,
        }],
        "investments_by_capital": {"financial": 15.0},
        "returns_by_capital": {"natural": 15.0},
    }
    cross_capital_dependencies = {
        "location_id": location_id,
        "dependency_matrix": {
            "natural": {"natural": 0, "human": 0, "social": 0, "produced": 0, "financial": 0},
            "human": {"natural": 0, "human": 0, "social": 0, "produced": 0, "financial": 0},
            "social": {"natural": 0, "human": 0, "social": 0, "produced": 0, "financial": 0},
            "produced": {"natural": 0, "human": 0, "social": 0, "produced": 0, "financial": 0},
            "financial": {"natural": 15.0, "human": 0, "social": 0, "produced": 0, "financial": 0},
        },
        "cross_capital_value_usd": 15.0,
        "interdependency_ratio": 1.0,
        "key_dependencies": [{"from": "financial", "to": "natural", "value_usd": 15.0}],
        "interdependency_score": 100.0,
    }
    return {
        "location_id": location_id,
        "true_cost_statement": statement,
        "hidden_costs": hidden_costs,
        "natural_capital": natural_capital,
        "social_impact": social_impact,
        "capital_flows": capital_flows,
        "cross_capital_dependencies": cross_capital_dependencies,
    }


def test_true_cost_operator_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())

    policy = auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary", enabled=True
    )

    assert policy == {
        "resource": "true_cost_accounting",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "POST", f"/operator/api/true-cost/{location_id}/summary", enabled=True
    ) is None
    assert auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary/extra", enabled=True
    ) is None
    assert auth_route_policy(
        "GET", f"/operator/api/true-cost/{location_id}/summary", enabled=False
    ) is None


class _Cursor:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))


class _Connection:
    autocommit = False

    def __init__(self):
        self.statements = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self.statements)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_true_cost_summary_sets_context_before_all_analytics_on_same_read_only_connection():
    operator_id, location_id = str(uuid4()), str(uuid4())
    conn = _Connection()
    calls = []
    labels = (
        "statement",
        "hidden",
        "natural",
        "social",
        "flows",
        "dependencies",
    )

    def analytics(label):
        def call(connection, scoped_location_id):
            assert connection is conn
            assert scoped_location_id == location_id
            calls.append(label)
            return {"section": label}

        return call

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "true_cost_accounting",
            "action": "read",
        }
        calls.append("tenant_context")

    with (
        patch("services.gateway.true_cost.set_operator_tenant_context", set_context),
        patch(
            "services.gateway.true_cost.compute_true_cost_statement", analytics("statement")
        ),
        patch(
            "services.gateway.true_cost.compute_hidden_cost_summary", analytics("hidden")
        ),
        patch(
            "services.gateway.true_cost.compute_natural_capital_valuation", analytics("natural")
        ),
        patch(
            "services.gateway.true_cost.compute_social_impact_valuation", analytics("social")
        ),
        patch(
            "services.gateway.true_cost.compute_capital_flow_summary", analytics("flows")
        ),
        patch(
            "services.gateway.true_cost.compute_cross_capital_dependencies",
            analytics("dependencies"),
        ),
    ):
        result = get_true_cost_summary(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert calls == ["tenant_context", *labels]
    assert [query for query, _params in conn.statements] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert result == {
        "location_id": location_id,
        "true_cost_statement": {"section": "statement"},
        "hidden_costs": {"section": "hidden"},
        "natural_capital": {"section": "natural"},
        "social_impact": {"section": "social"},
        "capital_flows": {"section": "flows"},
        "cross_capital_dependencies": {"section": "dependencies"},
    }
    assert conn.rolled_back and conn.closed


def test_invalid_true_cost_scope_fails_before_database_connection():
    connection_requested = False

    def connection_factory():
        nonlocal connection_requested
        connection_requested = True
        raise AssertionError("invalid input must fail before opening PostgreSQL")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        get_true_cost_summary("not-an-operator", str(uuid4()), connection_factory=connection_factory)

    assert connection_requested is False


@pytest.fixture
def gateway_audit_spool(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "KOKONUT_GATEWAY_AUDIT_SPOOL_PATH", str(tmp_path / "gateway-audit.sqlite3")
    )
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


def test_true_cost_route_uses_operator_auth_and_returns_no_store_summary(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, scoped_operator, resource, action, scoped_location):
            return (
                scoped_operator == operator_id
                and resource == "true_cost_accounting"
                and action == "read"
                and scoped_location == location_id
            )

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary",
        lambda _scoped_operator, scoped_location: _true_cost_payload(scoped_location),
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 200
    assert response.json() == _true_cost_payload(location_id)
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def test_true_cost_response_contract_is_published_and_forbids_extra_fields(
    monkeypatch, gateway_audit_spool
):
    app = create_app()
    response = app.openapi()["paths"][
        "/operator/api/true-cost/{location_id}/summary"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert response == {"$ref": "#/components/schemas/TrueCostSummaryResponse"}
    schemas = app.openapi()["components"]["schemas"]
    for name in (
        "TrueCostSummaryResponse",
        "TrueCostStatementResponse",
        "HiddenCostSummaryResponse",
        "HiddenCostDetailResponse",
        "NaturalCapitalSummaryResponse",
        "SocialImpactSummaryResponse",
        "CapitalFlowSummaryResponse",
        "CrossCapitalDependenciesResponse",
    ):
        assert schemas[name]["additionalProperties"] is False


@pytest.mark.parametrize(
    "invalid_field",
    ["top_level_extra", "nested_extra", "invalid_category", "negative_count", "location_mismatch"],
)
def test_true_cost_route_rejects_invalid_success_projection(
    monkeypatch, gateway_audit_spool, invalid_field
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    payload = _true_cost_payload(location_id)
    if invalid_field == "top_level_extra":
        payload["source_record_id"] = str(uuid4())
    elif invalid_field == "nested_extra":
        payload["true_cost_statement"]["private_note"] = "must not be returned"
    elif invalid_field == "invalid_category":
        payload["hidden_costs"]["details"][0]["category"] = "private"
    elif invalid_field == "negative_count":
        payload["hidden_costs"]["total_observations"] = -1
    else:
        payload["location_id"] = str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="d" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary",
        lambda *_args: payload,
    )
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 500
    assert response.json() == {"error": "True-cost summary unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {
        value.strip().lower() for value in response.headers["vary"].split(",")
    }


def test_true_cost_route_denies_operator_without_location_scope(
    monkeypatch, gateway_audit_spool
):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="b" * 64,
        operator=SimpleNamespace(operator_id=str(uuid4())),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    summary_called = False

    def unexpected_summary(*_args):
        nonlocal summary_called
        summary_called = True
        raise AssertionError("authorization denial must happen before the handler")

    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary", unexpected_summary
    )
    location_id = str(uuid4())

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 403
    assert summary_called is False


def test_true_cost_route_fails_closed_when_database_context_rejects_revoked_grant(
    monkeypatch, gateway_audit_spool
):
    operator_id, location_id = str(uuid4()), str(uuid4())
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="c" * 64,
        operator=SimpleNamespace(operator_id=operator_id),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="test-only-state-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return True

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())

    def reject_stale_scope(*_args):
        raise TenantContextDenied("synthetic revoked database grant")

    monkeypatch.setattr(
        "services.gateway.true_cost.get_true_cost_summary", reject_stale_scope
    )

    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/true-cost/{location_id}/summary")

    assert response.status_code == 403
    assert response.json() == {
        "error": "Tenant-qualified operator access is required"
    }
