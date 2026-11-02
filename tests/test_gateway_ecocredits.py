"""Scoped ecocredit Gateway read tests use synthetic identity and DB boundaries."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.common.tenant_context import TenantContextDenied  # noqa: E402
from services.gateway.app import create_app  # noqa: E402
from services.gateway.ecocredits import list_location_ecocredit_batches  # noqa: E402
from services.gateway.operator_auth import auth_route_policy  # noqa: E402


def test_ecocredit_batch_policy_requires_exact_location_read_scope():
    location_id = str(uuid4())
    path = f"/operator/api/ecocredits/{location_id}/batches"

    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "ecocredit",
        "action": "read",
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", f"{path}/wallets", enabled=True) is None
    assert auth_route_policy("GET", path, enabled=False) is None


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "WITH location_batches" in query:
            self.connection.events.append("batch_query")
            self.description = [SimpleNamespace(name=name) for name in self.connection.columns]

    def fetchall(self):
        return self.connection.rows


class _Connection:
    autocommit = False

    def __init__(self, rows=(), columns=()):
        self.rows = list(rows)
        self.columns = list(columns)
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


def test_ecocredit_read_sets_signed_context_before_location_query_and_hides_wallets():
    operator_id, location_id = str(uuid4()), str(uuid4())
    columns = [
        "id", "credit_class_id", "class_name", "credit_type", "class_status",
        "batch_code", "vintage_year", "unit", "batch_status", "total_quantity",
        "issued_quantity", "retired_quantity", "cancelled_quantity", "available_quantity",
        "ledger_tradable_supply", "ledger_retired_supply", "ledger_escrowed_supply",
        "created_at",
    ]
    row = (
        uuid4(), uuid4(), "Kokonut Carbon", "carbon", "published", "CC-IPCC-2026-ADEL-0001",
        2026, "tonneCO2e", "published", Decimal("100.0000"), Decimal("80.0000"),
        Decimal("5.0000"), Decimal("0.0000"), Decimal("75.0000"), Decimal("70.0000"),
        Decimal("5.0000"), Decimal("0.0000"), datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    conn = _Connection([row], columns)

    def set_context(connection, **kwargs):
        assert connection is conn
        assert kwargs == {
            "operator_id": operator_id,
            "location_id": location_id,
            "resource": "ecocredit",
            "action": "read",
        }
        connection.events.append("tenant_context")

    with patch("services.gateway.ecocredits.set_operator_tenant_context", set_context):
        result = list_location_ecocredit_batches(
            operator_id, location_id, connection_factory=lambda: conn
        )

    assert conn.events == ["tenant_context", "batch_query"]
    assert conn.queries[:3] == [
        ("SET TRANSACTION READ ONLY", None),
        ("SET LOCAL statement_timeout = '5s'", None),
        ("SET LOCAL lock_timeout = '2s'", None),
    ]
    query, params = conn.queries[3]
    assert "WHERE location_id = %s::uuid" in query
    assert "JOIN location_batches AS batch" in query
    assert "account_address" not in query
    assert params == (location_id, 50)
    assert result == [
        {
            "id": str(row[0]),
            "credit_class_id": str(row[1]),
            "class_name": "Kokonut Carbon",
            "credit_type": "carbon",
            "class_status": "published",
            "batch_code": "CC-IPCC-2026-ADEL-0001",
            "vintage_year": 2026,
            "unit": "tonneCO2e",
            "batch_status": "published",
            "total_quantity": "100.0000",
            "issued_quantity": "80.0000",
            "retired_quantity": "5.0000",
            "cancelled_quantity": "0.0000",
            "available_quantity": "75.0000",
            "ledger_tradable_supply": "70.0000",
            "ledger_retired_supply": "5.0000",
            "ledger_escrowed_supply": "0.0000",
            "created_at": "2026-10-18T00:00:00+00:00",
        }
    ]
    assert "account_address" not in result[0]
    assert conn.rolled_back and conn.closed


def test_invalid_scope_or_limit_fails_before_connection():
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid scope must not connect")

    with pytest.raises(ValueError, match="Invalid operator or location"):
        list_location_ecocredit_batches("bad", str(uuid4()), connection_factory=connection_factory)
    with pytest.raises(ValueError, match="limit must be between"):
        list_location_ecocredit_batches(str(uuid4()), str(uuid4()), 0, connection_factory=connection_factory)
    assert not opened


def test_ecocredit_tenant_denial_rolls_back_without_running_batch_query():
    conn = _Connection()
    with patch(
        "services.gateway.ecocredits.set_operator_tenant_context",
        side_effect=TenantContextDenied("synthetic revoked grant"),
    ):
        with pytest.raises(TenantContextDenied):
            list_location_ecocredit_batches(
                str(uuid4()), str(uuid4()), connection_factory=lambda: conn
            )
    assert len(conn.queries) == 3
    assert conn.rolled_back and conn.closed


@pytest.fixture
def isolated_audit(monkeypatch):
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


def test_ecocredit_http_route_authenticates_then_returns_no_store_summary(isolated_audit):
    operator_id, location_id = str(uuid4()), str(uuid4())
    batch_id, credit_class_id = str(uuid4()), str(uuid4())
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
                and resource == "ecocredit"
                and action == "read"
                and scoped_location == location_id
            )

    with patch("services.gateway.operator_auth.create_provider", return_value=Provider()), patch(
        "services.gateway.ecocredits.list_location_ecocredit_batches",
        return_value=[
            {
                "id": batch_id,
                "credit_class_id": credit_class_id,
                "class_name": "Synthetic class",
                "credit_type": "carbon",
                "class_status": "published",
                "batch_code": "SYNTHETIC",
                "vintage_year": 2026,
                "unit": "tonneCO2e",
                "batch_status": "published",
                "total_quantity": "3.0000",
                "issued_quantity": "3.0000",
                "retired_quantity": "0.0000",
                "cancelled_quantity": "0.0000",
                "available_quantity": "3.0000",
                "ledger_tradable_supply": "3.0000",
                "ledger_retired_supply": "0.0000",
                "ledger_escrowed_supply": "0.0000",
                "created_at": "2026-10-28T00:00:00+00:00",
                # A future/internal field must not escape through the API.
                "wallet_address": "0xprivate",
            }
        ],
    ) as list_batches:
        with TestClient(
            create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
        ) as client:
            response = client.get(f"/operator/api/ecocredits/{location_id}/batches")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "cookie" in {value.strip().lower() for value in response.headers["vary"].split(",")}
    body = response.json()
    assert body["location_id"] == location_id
    assert body["data"][0]["id"] == batch_id
    assert body["data"][0]["credit_class_id"] == credit_class_id
    assert body["data"][0]["available_quantity"] == "3.0000"
    assert "wallet_address" not in body["data"][0]
    list_batches.assert_called_once_with(operator_id, location_id, 50)


def test_ecocredit_openapi_declares_only_the_projected_batch_fields(isolated_audit):
    schema = create_app().openapi()

    response = schema["paths"][
        "/operator/api/ecocredits/{location_id}/batches"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    response_model = schema["components"]["schemas"]["LocationEcocreditBatchesResponse"]
    item_model = schema["components"]["schemas"]["LocationEcocreditBatch"]
    assert response["$ref"].endswith("/LocationEcocreditBatchesResponse")
    assert set(response_model["properties"]) == {"data", "location_id"}
    assert "wallet_address" not in item_model["properties"]
    assert set(item_model["properties"]) == {
        "id",
        "credit_class_id",
        "class_name",
        "credit_type",
        "class_status",
        "batch_code",
        "vintage_year",
        "unit",
        "batch_status",
        "total_quantity",
        "issued_quantity",
        "retired_quantity",
        "cancelled_quantity",
        "available_quantity",
        "ledger_tradable_supply",
        "ledger_retired_supply",
        "ledger_escrowed_supply",
        "created_at",
    }


def test_ecocredit_http_route_denies_missing_location_grant_before_service(
    monkeypatch, isolated_audit
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
    service_called = False

    def unexpected_service(*_args):
        nonlocal service_called
        service_called = True
        raise AssertionError("location scope denial must precede database access")

    monkeypatch.setattr("services.gateway.ecocredits.list_location_ecocredit_batches", unexpected_service)
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        response = client.get(f"/operator/api/ecocredits/{uuid4()}/batches")

    assert response.status_code == 403
    assert service_called is False
