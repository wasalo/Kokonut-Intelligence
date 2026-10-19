"""Scoped, bounded governance role and tactical reads are privacy preserving."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import governance_operations as operations

pytest.importorskip("fastapi")
from starlette.testclient import TestClient  # noqa: E402

from services.gateway.app import create_app  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
ROLE_ID = str(uuid4())
ITEM_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 18, tzinfo=timezone.utc)


def test_role_registry_covers_all_governance_lifecycle_states():
    assert operations._ROLE_STATUSES == (
        "draft", "submitted", "approved", "active", "suspended", "rejected", "retired"
    )
    assert operations._CIRCLE_STATUSES == (
        "draft", "submitted", "active", "suspended", "rejected", "retired"
    )


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.query = ""

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.query = " ".join(query.split())
        self.connection.operations.append(("sql", self.query, params))
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "role_key", "name", "purpose", "status", "effective_from",
                    "effective_until", "review_due_at", "created_at", "circle_key",
                    "circle_name", "circle_status", "active_accountability_count",
                    "current_assignment_count", "applicable_authority_domain_count",
                )
            ]
        elif "FROM public.governance_role AS role" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "role_key", "name", "purpose", "status", "effective_from",
                    "effective_until", "review_due_at", "created_at", "circle_key",
                    "circle_name", "circle_status",
                )
            ]
        elif "FROM public.governance_role_accountability AS accountability" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in ("accountability", "priority", "required")
            ]
        elif "FROM public.governance_role_domain AS domain" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "domain_type", "domain_key", "scope_type", "authority_level",
                    "requires_human_approval",
                )
            ]
        elif "FROM public.governance_tactical_item AS item" in self.query and "requested_next_action" in self.query:
            self.description = [
                SimpleNamespace(name=name)
                for name in (
                    "id", "requested_next_action", "priority", "due_at", "status",
                    "created_at", "session_type", "session_title", "scheduled_at",
                    "session_status", "owner_role_key",
                )
            ]

    def fetchone(self):
        if "SELECT role.created_at" in self.query or "SELECT item.created_at" in self.query:
            return self.connection.cursor_timestamp
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" not in self.query:
            return self.connection.role_detail_row
        return None

    def fetchall(self):
        if "FROM public.governance_role AS role" in self.query and "COUNT(DISTINCT" in self.query:
            return self.connection.role_rows
        if "FROM public.governance_role_accountability AS accountability" in self.query:
            return self.connection.accountability_rows
        if "FROM public.governance_role_domain AS domain" in self.query:
            return self.connection.domain_rows
        if "FROM public.governance_tactical_item AS item" in self.query and "requested_next_action" in self.query:
            return self.connection.tactical_rows
        return []


class _Connection:
    autocommit = False

    def __init__(self):
        self.operations = []
        self.cursor_timestamp = (CREATED_AT,)
        self.role_rows = [(
            ROLE_ID, "steward", "Farm steward", "Coordinate location stewardship.",
            "active", CREATED_AT, None, None, CREATED_AT, "adelphi-stewardship",
            "Adelphi Stewardship", "active", 4, 1, 2,
        )]
        self.role_detail_row = (
            ROLE_ID, "steward", "Farm steward", "Coordinate location stewardship.",
            "active", CREATED_AT, None, None, CREATED_AT, "adelphi-stewardship",
            "Adelphi Stewardship", "active",
        )
        self.accountability_rows = [("Maintain seasonal field plans.", 2, True)]
        self.domain_rows = [("farm_operations", "field_plan", "location", "recommend", True)]
        self.tactical_rows = [(
            ITEM_ID, "Review the irrigation schedule.", 2, None, "open", CREATED_AT,
            "weekly_review", "Weekly review", CREATED_AT, "active", "steward",
        )]
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_role_registry_uses_signed_read_context_and_omits_party_and_policy_fields(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(operations, "set_operator_tenant_context", set_context)
    result = operations.list_location_governance_roles(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert result["items"][0]["role_key"] == "steward"
    assert set(result["items"][0]) == {
        "id", "role_key", "name", "purpose", "status", "effective_from",
        "effective_until", "review_due_at", "created_at", "circle_key",
        "circle_name", "circle_status", "active_accountability_count",
        "current_assignment_count", "applicable_authority_domain_count",
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    })]
    operations_list = connection.operations
    context_index = next(i for i, item in enumerate(operations_list) if item[0] == "context")
    query_index = next(
        i for i, item in enumerate(operations_list)
        if item[0] == "sql" and "COUNT(DISTINCT" in item[1]
    )
    assert context_index < query_index
    query = operations_list[query_index][1]
    assert "circle.scope_type = 'location'" in query
    assert "circle.scope_id = %s::uuid" in query
    assert "display_name" not in query
    assert "policy_text" not in query
    assert "metadata" not in query
    assert "party_id" not in query
    assert connection.rolled_back and connection.closed


def test_role_detail_returns_bounded_responsibilities_without_private_fields(monkeypatch):
    connection = _Connection()
    contexts = []

    def set_context(conn, **kwargs):
        contexts.append((conn, kwargs))
        conn.operations.append(("context", kwargs))

    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        set_context,
    )

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert result["role"]["role_key"] == "steward"
    assert result["accountabilities"] == [{
        "accountability": "Maintain seasonal field plans.",
        "priority": 2,
        "required": True,
    }]
    assert result["authority_domains"] == [{
        "domain_type": "farm_operations",
        "domain_key": "field_plan",
        "scope_type": "location",
        "authority_level": "recommend",
        "requires_human_approval": True,
    }]
    assert result["accountabilities_truncated"] is False
    assert result["authority_domains_truncated"] is False
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_roles",
        "action": "read",
    })]
    operations_log = connection.operations
    context_index = next(i for i, item in enumerate(operations_log) if item[0] == "context")
    query_indexes = [i for i, item in enumerate(operations_log) if item[0] == "sql" and item[1].startswith("SELECT")]
    assert context_index < min(query_indexes)
    sql = " ".join(item[1] for item in operations_log if item[0] == "sql")
    assert "circle.scope_id = %s::uuid" in sql
    for private_field in (
        "party_id", "policy_text", "evidence_expectation", "constraints", "metadata",
    ):
        assert private_field not in sql
    assert connection.rolled_back and connection.closed


def test_role_detail_hides_unknown_or_cross_location_role(monkeypatch):
    connection = _Connection()
    connection.role_detail_row = None
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert result is None
    assert not any(
        "governance_role_accountability" in item[1] or "governance_role_domain" in item[1]
        for item in connection.operations if item[0] == "sql"
    )
    assert connection.rolled_back and connection.closed


def test_role_detail_caps_accountability_and_authority_domain_lists(monkeypatch):
    connection = _Connection()
    connection.accountability_rows = [
        (f"Accountability {index}", 3, True) for index in range(101)
    ]
    connection.domain_rows = [
        ("farm_operations", f"domain_{index}", "location", "recommend", True)
        for index in range(101)
    ]
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    result = operations.get_location_governance_role_detail(
        OPERATOR_ID, LOCATION_ID, ROLE_ID, connection_factory=lambda: connection
    )

    assert len(result["accountabilities"]) == 100
    assert result["accountabilities_truncated"] is True
    assert len(result["authority_domains"]) == 100
    assert result["authority_domains_truncated"] is True
    assert connection.rolled_back and connection.closed


def test_tactical_queue_uses_its_own_scope_and_omits_party_and_private_disposition(monkeypatch):
    connection = _Connection()
    contexts = []
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    result = operations.list_location_governance_tactical_items(
        OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
    )

    assert result["items"][0]["requested_next_action"] == "Review the irrigation schedule."
    assert set(result["items"][0]) == {
        "id", "requested_next_action", "priority", "due_at", "status", "created_at",
        "session_type", "session_title", "scheduled_at", "session_status", "owner_role_key",
    }
    assert contexts[0][1] == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "governance_tactical",
        "action": "read",
    }
    sql = " ".join(item[1] for item in connection.operations if item[0] == "sql")
    assert "circle.scope_type = 'location'" in sql
    assert "item.status = ANY(%s::text[])" in sql
    assert "disposition_summary" not in sql
    assert "proposer_party_id" not in sql
    assert "owner_party_id" not in sql
    assert "agenda_scope" not in sql
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("reader", "kwargs", "message"),
    [
        (operations.list_location_governance_roles, {"status": "archived"}, "status is not available"),
        (operations.list_location_governance_roles, {"limit": "1e2"}, "limit must be an integer"),
        (operations.list_location_governance_tactical_items, {"limit": 101}, "limit must be an integer"),
        (operations.list_location_governance_tactical_items, {"cursor": "invalid"}, "Invalid cursor"),
        (operations.get_location_governance_role_detail, {"role_id": "invalid"}, "Invalid role identifier"),
    ],
)
def test_invalid_selectors_fail_before_connecting(reader, kwargs, message):
    opened = False

    def connection_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid selectors must be rejected before database access")

    with pytest.raises(operations.GovernanceOperationsInvalid, match=message):
        reader(OPERATOR_ID, LOCATION_ID, connection_factory=connection_factory, **kwargs)
    assert not opened


def test_role_cursor_is_location_and_status_qualified(monkeypatch):
    connection = _Connection()
    connection.cursor_timestamp = None
    monkeypatch.setattr(operations, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(operations.GovernanceOperationsInvalid, match="cursor is not available"):
        operations.list_location_governance_roles(
            OPERATOR_ID,
            LOCATION_ID,
            status="active",
            cursor=ROLE_ID,
            connection_factory=lambda: connection,
        )
    sql = [item[1] for item in connection.operations if item[0] == "sql"]
    assert "circle.scope_id = %s::uuid" in sql[-1]
    assert "role.status = ANY(%s::text[])" in sql[-1]
    assert not any("COUNT(DISTINCT" in query for query in sql)
    assert connection.rolled_back and connection.closed


def test_tenant_denial_rolls_back_role_query(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(
        operations,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TenantContextDenied("revoked")),
    )
    with pytest.raises(TenantContextDenied):
        operations.list_location_governance_roles(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
        )
    assert not any("COUNT(DISTINCT" in item[1] for item in connection.operations if item[0] == "sql")
    assert connection.rolled_back and connection.closed


def test_role_and_tactical_routes_deny_missing_exact_grants_before_service(monkeypatch):
    operator_session = SimpleNamespace(
        session_id=str(uuid4()),
        session_token_hash="a" * 64,
        operator=SimpleNamespace(operator_id=OPERATOR_ID),
    )

    class Provider:
        settings = SimpleNamespace(state_secret="synthetic-test-secret")

        def authenticate_request(self, _request):
            return operator_session

        def has_scope(self, *_scope):
            return False

    class InMemoryAudit:
        def __init__(self):
            pass

        def replay_pending(self, _limit=100):
            return 0

        def log(self, **_event):
            return None

        def capture_status(self):
            return "ok"

    monkeypatch.setattr("services.gateway.operator_auth.create_provider", lambda: Provider())
    monkeypatch.setattr("services.gateway.audit.GatewayAudit", InMemoryAudit)
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_roles",
        lambda *_args, **_kwargs: pytest.fail("missing role grant reached data service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.get_location_governance_role_detail",
        lambda *_args, **_kwargs: pytest.fail("missing role grant reached detail service"),
    )
    monkeypatch.setattr(
        "services.gateway.governance_operations.list_location_governance_tactical_items",
        lambda *_args, **_kwargs: pytest.fail("missing tactical grant reached data service"),
    )
    with TestClient(
        create_app(), cookies={"kokonut_operator_session": "synthetic-session"}
    ) as client:
        role_response = client.get(f"/operator/api/governance/{LOCATION_ID}/roles")
        role_detail_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/roles/{ROLE_ID}"
        )
        tactical_response = client.get(
            f"/operator/api/governance/{LOCATION_ID}/tactical-items"
        )

    assert role_response.status_code == role_detail_response.status_code == tactical_response.status_code == 403
    assert role_response.headers["cache-control"] == "no-store"
    assert role_detail_response.headers["cache-control"] == "no-store"
    assert tactical_response.headers["cache-control"] == "no-store"
