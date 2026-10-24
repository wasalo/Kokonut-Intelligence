"""Exact-location, draft-only operating-pilot Gateway writes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_writes
from services.gateway.operating_pilot_routes import register_operating_pilot_routes
from services.gateway.operator_auth import auth_route_policy

OPERATOR_ID = "a0000000-0000-4000-8000-000000000001"
LOCATION_ID = "b0000000-0000-4000-8000-000000000001"
REQUEST_ID = "c0000000-0000-4000-8000-000000000001"
PROFILE_ID = "d0000000-0000-4000-8000-000000000001"
CAPACITY_PAYLOAD = {
    "period_start": "2026-11-01",
    "period_end": "2026-11-30",
    "available_hours": "40.25",
    "committed_hours": "18.50",
    "protected_hours": "2.25",
    "notes": "Private synthetic capacity note",
}
PAYLOAD = {
    "work_type": "soil preparation",
    "period_start": "2026-11-01",
    "period_end": "2026-11-30",
    "required_hours": "18.50",
    "priority": "high",
    "description": "Private synthetic planning note",
}
RESOURCE_PAYLOAD = {
    "resource_type": "irrigation tools",
    "description": "Synthetic request for replacement drip-line connectors",
    "urgency": "medium",
    "requested_by": "2026-11-15",
}
COMPETENCY_PAYLOAD = {
    "competency_key": "Facilitation",
    "current_level": "2.50",
    "target_level": "4",
    "evidence_note": "Private synthetic self-assessment evidence",
}
LEARNING_PLAN_PAYLOAD = {
    "title": "Facilitation practice plan",
    "competency_goals": [{"key": "facilitation", "target": 4}],
    "support_requested": ["Peer mentoring"],
    "target_date": "2026-12-15",
}


def _connection_with_result(result):
    connection = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = (result,)
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False
    return connection, cursor


def test_demand_draft_sets_exact_create_context_and_commits_function_result(monkeypatch):
    connection, cursor = _connection_with_result({"signal_id": REQUEST_ID, "status": "draft", "replayed": False})
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_demand_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "signal_id": REQUEST_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "create",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "create_location_operating_pilot_demand_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "soil preparation",
        operating_pilot_writes.date(2026, 11, 1),
        operating_pilot_writes.date(2026, 11, 30),
        operating_pilot_writes.Decimal("18.50"),
        "high",
        "Private synthetic planning note",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_competency_draft_sets_exact_context_and_commits_private_function_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": PROFILE_ID, "status": "draft", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_competency_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        COMPETENCY_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "create",
    })]
    assert "create_location_operating_pilot_competency_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "facilitation",
        operating_pilot_writes.Decimal("2.50"),
        operating_pilot_writes.Decimal("4"),
        "Private synthetic self-assessment evidence",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_learning_plan_draft_sets_exact_create_context_and_commits_function_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"learning_plan_id": PROFILE_ID, "status": "draft", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_learning_plan_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        LEARNING_PLAN_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "learning_plan_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [(
        connection,
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "operating_pilot",
            "action": "create",
        },
    )]
    assert "create_location_operating_pilot_learning_plan_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "Facilitation practice plan",
        '[{"key":"facilitation","target":4}]',
        '["Peer mentoring"]',
        operating_pilot_writes.date(2026, 12, 15),
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("payload", [
    [],
    {**LEARNING_PLAN_PAYLOAD, "title": " "},
    {**LEARNING_PLAN_PAYLOAD, "title": "x" * 256},
    {**LEARNING_PLAN_PAYLOAD, "competency_goals": "not-an-array"},
    {**LEARNING_PLAN_PAYLOAD, "support_requested": ["x"] * 51},
    {**LEARNING_PLAN_PAYLOAD, "target_date": "2026-12-15T00:00:00Z"},
    {**LEARNING_PLAN_PAYLOAD, "unexpected": True},
])
def test_invalid_learning_plan_draft_fails_before_database_access(payload):
    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid):
        operating_pilot_writes.create_location_operating_pilot_learning_plan_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            payload,
            connection_factory=lambda: pytest.fail("invalid learning-plan input must fail before DB access"),
        )


def test_competency_revision_uses_edit_own_context_and_replays_function_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": REQUEST_ID, "status": "draft", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.revise_location_operating_pilot_competency_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        COMPETENCY_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": REQUEST_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "edit_own",
    })]
    assert "revise_location_operating_pilot_competency_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        "facilitation",
        operating_pilot_writes.Decimal("2.50"),
        operating_pilot_writes.Decimal("4"),
        "Private synthetic self-assessment evidence",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_competency_revision_fails_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))
    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="draft identifier"):
        operating_pilot_writes.revise_location_operating_pilot_competency_draft(
            OPERATOR_ID,
            LOCATION_ID,
            "not-a-draft-id",
            REQUEST_ID,
            COMPETENCY_PAYLOAD,
            connection_factory=factory,
        )
    factory.assert_not_called()


def test_competency_submission_uses_submit_own_context_and_commits(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.submit_location_operating_pilot_competency_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": PROFILE_ID,
        "status": "submitted",
        "replayed": False,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "submit_own",
    })]
    assert "submit_location_operating_pilot_competency_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, PROFILE_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    "payload",
    [
        {**COMPETENCY_PAYLOAD, "current_level": True},
        {**COMPETENCY_PAYLOAD, "current_level": "5.01"},
        {**COMPETENCY_PAYLOAD, "current_level": "2.001"},
        {**COMPETENCY_PAYLOAD, "target_level": "2.49"},
        {**COMPETENCY_PAYLOAD, "competency_key": "invalid key"},
        {**COMPETENCY_PAYLOAD, "evidence_note": "x" * 2001},
        {**COMPETENCY_PAYLOAD, "unsupported": "field"},
    ],
)
def test_invalid_competency_draft_fails_before_database_access(payload):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))
    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid):
        operating_pilot_writes.create_location_operating_pilot_competency_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            payload,
            connection_factory=factory,
        )
    factory.assert_not_called()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"work_type": " "}, "Work type"),
        ({"period_start": "2026-02-30"}, "period_start"),
        ({"period_start": "2026-12-01", "period_end": "2026-11-30"}, "period must be ordered"),
        ({"period_end": "2027-12-02"}, "no longer than 367 days"),
        ({"required_hours": True}, "positive decimal"),
        ({"required_hours": "NaN"}, "positive, at most 100000"),
        ({"required_hours": "1.001"}, "positive, at most 100000"),
        ({"priority": "urgent"}, "Priority"),
        ({"description": "x" * 2001}, "Description"),
        ({"actor_party_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_demand_draft_is_rejected_before_database_access(changes, message):
    payload = {**PAYLOAD, **changes}
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.create_location_operating_pilot_demand_draft(
            OPERATOR_ID, LOCATION_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def test_demand_draft_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="returned no result"):
        operating_pilot_writes.create_location_operating_pilot_demand_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_resource_draft_sets_exact_create_context_and_commits(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": REQUEST_ID, "status": "draft", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_resource_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        RESOURCE_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": REQUEST_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "create",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "create_location_operating_pilot_resource_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        "irrigation tools",
        "Synthetic request for replacement drip-line connectors",
        "medium",
        operating_pilot_writes.date(2026, 11, 15),
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"resource_type": " "}, "Resource type"),
        ({"resource_type": "<script>"}, "Resource type"),
        ({"description": " "}, "Description"),
        ({"description": "x" * 2001}, "Description"),
        ({"description": "unsafe\x00text"}, "Description"),
        ({"urgency": "immediate"}, "Urgency"),
        ({"requested_by": "2026-02-30"}, "requested_by"),
        ({"party_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_resource_draft_is_rejected_before_database_access(changes, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.create_location_operating_pilot_resource_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            {**RESOURCE_PAYLOAD, **changes},
            connection_factory=factory,
        )

    factory.assert_not_called()


def test_resource_draft_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, _ = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="returned no result"):
        operating_pilot_writes.create_location_operating_pilot_resource_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            RESOURCE_PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_resource_revision_sets_exact_edit_own_context_and_commits_result(monkeypatch):
    replacement_id = "e0000000-0000-4000-8000-000000000002"
    connection, cursor = _connection_with_result(
        {
            "draft_id": replacement_id,
            "replaced_draft_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.revise_location_operating_pilot_resource_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        {**RESOURCE_PAYLOAD, "resource_type": "irrigation pumps"},
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": replacement_id,
        "replaced_draft_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "edit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "revise_location_operating_pilot_resource_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        "irrigation pumps",
        RESOURCE_PAYLOAD["description"],
        "medium",
        operating_pilot_writes.date(2026, 11, 15),
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("draft_id", "request_id", "payload", "message"),
    [
        ("not-a-draft-id", REQUEST_ID, RESOURCE_PAYLOAD, "draft identifier"),
        (PROFILE_ID, "not-a-request-id", RESOURCE_PAYLOAD, "request identifier"),
        (PROFILE_ID, REQUEST_ID, {**RESOURCE_PAYLOAD, "description": "unsafe\x00text"}, "Description"),
        (PROFILE_ID, REQUEST_ID, {**RESOURCE_PAYLOAD, "urgency": "immediate"}, "Urgency"),
    ],
)
def test_invalid_resource_revision_fails_before_database_access(draft_id, request_id, payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.revise_location_operating_pilot_resource_draft(
            OPERATOR_ID,
            LOCATION_ID,
            draft_id,
            request_id,
            payload,
            connection_factory=factory,
        )

    factory.assert_not_called()


def test_resource_revision_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, _cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="revision returned no result"):
        operating_pilot_writes.revise_location_operating_pilot_resource_draft(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            REQUEST_ID,
            RESOURCE_PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _route_app(monkeypatch, action, operation="create_location_operating_pilot_demand_draft"):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, operation, action)
    router = APIRouter()
    register_operating_pilot_routes(router, object(), run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_demand_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(return_value={"signal_id": REQUEST_ID, "status": "draft", "replayed": False})
    client = _route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, PAYLOAD)


def test_demand_draft_http_route_returns_403_when_signed_context_is_denied(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "create access" in response.json()["error"]


def test_demand_draft_route_policy_requires_exact_location_create_grant():
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
        enabled=True,
    ) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert (
        auth_route_policy(
            "POST",
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals",
            enabled=False,
        )
        is None
    )


def test_competency_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(return_value={"draft_id": PROFILE_ID, "status": "draft", "replayed": False})
    client = _route_app(
        monkeypatch,
        action,
        "create_location_operating_pilot_competency_draft",
    )

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/competency-assessments",
        json={**COMPETENCY_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"draft_id": PROFILE_ID, "status": "draft", "replayed": False}
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, COMPETENCY_PAYLOAD)


def test_learning_plan_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(
        return_value={"learning_plan_id": PROFILE_ID, "status": "draft", "replayed": False}
    )
    client = _route_app(
        monkeypatch,
        action,
        "create_location_operating_pilot_learning_plan_draft",
    )

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plans",
        json={**LEARNING_PLAN_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "learning_plan_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, LEARNING_PLAN_PAYLOAD)


def test_learning_plan_draft_http_route_rejects_oversized_body_before_database(monkeypatch):
    action = MagicMock(side_effect=AssertionError("oversized request must not reach the write helper"))
    client = _route_app(
        monkeypatch,
        action,
        "create_location_operating_pilot_learning_plan_draft",
    )

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plans",
        content=b" " * (32 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
    action.assert_not_called()


def test_learning_plan_draft_route_policy_requires_exact_location_create_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plans"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/unexpected", enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_competency_draft_route_policy_requires_exact_location_create_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/competency-assessments"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None


def test_resource_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(return_value={"draft_id": REQUEST_ID, "status": "draft", "replayed": False})
    client = _route_app(monkeypatch, action, "create_location_operating_pilot_resource_draft")

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests",
        json={**RESOURCE_PAYLOAD, "request_id": REQUEST_ID},
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, RESOURCE_PAYLOAD)


def test_competency_revision_and_submission_routes_use_exact_own_actions(monkeypatch):
    revise = MagicMock(return_value={"draft_id": REQUEST_ID, "status": "draft"})
    client = _route_app(monkeypatch, revise, "revise_location_operating_pilot_competency_draft")
    revise_path = f"/operator/api/operating-pilot/{LOCATION_ID}/competency-assessments/{PROFILE_ID}"
    response = client.put(revise_path, json={**COMPETENCY_PAYLOAD, "request_id": REQUEST_ID})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    revise.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, COMPETENCY_PAYLOAD)
    assert auth_route_policy("PUT", revise_path, enabled=True) == {
        "resource": "operating_pilot", "action": "edit_own", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }

    submit = MagicMock(return_value={"draft_id": PROFILE_ID, "status": "submitted"})
    client = _route_app(monkeypatch, submit, "submit_location_operating_pilot_competency_draft")
    submit_path = revise_path + "/submit"
    bad = client.post(submit_path, json={"request_id": REQUEST_ID, "status": "verified"})
    assert bad.status_code == 400
    submit.assert_not_called()
    response = client.post(submit_path, json={"request_id": REQUEST_ID})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    submit.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID)
    assert auth_route_policy("POST", submit_path, enabled=True) == {
        "resource": "operating_pilot", "action": "submit_own", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


def test_resource_draft_route_policy_requires_exact_location_create_grant():
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests",
        enabled=True,
    ) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests",
        enabled=False,
    ) is None


def test_resource_revision_http_route_passes_ids_and_uses_no_store(monkeypatch):
    action = MagicMock(
        return_value={
            "draft_id": REQUEST_ID,
            "replaced_draft_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    client = _route_app(monkeypatch, action, "revise_location_operating_pilot_resource_draft")

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}",
        json={**RESOURCE_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, RESOURCE_PAYLOAD)


def test_resource_revision_route_denies_missing_edit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _route_app(monkeypatch, action, "revise_location_operating_pilot_resource_draft")

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}",
        json={**RESOURCE_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "edit-own access" in response.json()["error"]


def test_resource_revision_route_policy_requires_exact_location_edit_own_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}"
    assert auth_route_policy("PUT", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "edit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("PUT", path, enabled=False) is None


def test_capacity_draft_sets_exact_create_context_and_commits_function_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"profile_id": REQUEST_ID, "status": "draft", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.create_location_operating_pilot_capacity_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        CAPACITY_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "profile_id": REQUEST_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "create",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "create_location_operating_pilot_capacity_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        REQUEST_ID,
        operating_pilot_writes.date(2026, 11, 1),
        operating_pilot_writes.date(2026, 11, 30),
        operating_pilot_writes.Decimal("40.25"),
        operating_pilot_writes.Decimal("18.50"),
        operating_pilot_writes.Decimal("2.25"),
        "Private synthetic capacity note",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"period_start": "2026-02-30"}, "period_start"),
        ({"period_end": "2026-10-31"}, "period must be ordered"),
        ({"period_end": "2027-12-02"}, "no longer than 367 days"),
        ({"available_hours": True}, "available_hours must be a non-negative decimal"),
        ({"available_hours": "NaN"}, "at most 100000"),
        ({"available_hours": "1.001"}, "at most two decimals"),
        ({"available_hours": "-1"}, "non-negative"),
        ({"committed_hours": "40", "protected_hours": "1"}, "cannot exceed available"),
        ({"notes": "x" * 2001}, "at most 2000 characters"),
        ({"notes": "bad\x00note"}, "at most 2000 characters"),
        ({"party_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_capacity_draft_is_rejected_before_database_access(changes, message):
    payload = {**CAPACITY_PAYLOAD, **changes}
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.create_location_operating_pilot_capacity_draft(
            OPERATOR_ID, LOCATION_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def test_capacity_draft_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, _cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="returned no result"):
        operating_pilot_writes.create_location_operating_pilot_capacity_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            CAPACITY_PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _capacity_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "create_location_operating_pilot_capacity_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_capacity_draft_http_route_passes_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(return_value={"profile_id": REQUEST_ID, "status": "draft", "replayed": False})
    client = _capacity_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles",
        json={**CAPACITY_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, REQUEST_ID, CAPACITY_PAYLOAD)


def test_capacity_draft_http_route_returns_403_when_signed_context_is_denied(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _capacity_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles",
        json={**CAPACITY_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "create access" in response.json()["error"]


def test_capacity_draft_route_policy_requires_exact_location_create_grant():
    assert auth_route_policy(
        "POST",
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles",
        enabled=True,
    ) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert (
        auth_route_policy(
            "POST",
            f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles",
            enabled=False,
        )
        is None
    )


def test_capacity_revision_sets_exact_edit_own_context_and_commits_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {
            "profile_id": "e0000000-0000-4000-8000-000000000001",
            "replaced_profile_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.revise_location_operating_pilot_capacity_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        CAPACITY_PAYLOAD,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "profile_id": "e0000000-0000-4000-8000-000000000001",
        "replaced_profile_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "edit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "revise_location_operating_pilot_capacity_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        operating_pilot_writes.date(2026, 11, 1),
        operating_pilot_writes.date(2026, 11, 30),
        operating_pilot_writes.Decimal("40.25"),
        operating_pilot_writes.Decimal("18.50"),
        operating_pilot_writes.Decimal("2.25"),
        "Private synthetic capacity note",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_capacity_revision_is_rejected_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="profile identifier"):
        operating_pilot_writes.revise_location_operating_pilot_capacity_draft(
            OPERATOR_ID,
            LOCATION_ID,
            "not-a-profile-id",
            REQUEST_ID,
            CAPACITY_PAYLOAD,
            connection_factory=factory,
        )

    factory.assert_not_called()


def test_capacity_revision_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, _cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="revision returned no result"):
        operating_pilot_writes.revise_location_operating_pilot_capacity_draft(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            REQUEST_ID,
            CAPACITY_PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _capacity_revision_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "revise_location_operating_pilot_capacity_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_capacity_revision_http_route_passes_ids_and_uses_no_store(monkeypatch):
    action = MagicMock(
        return_value={
            "profile_id": REQUEST_ID,
            "replaced_profile_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    client = _capacity_revision_route_app(monkeypatch, action)

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}",
        json={**CAPACITY_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, CAPACITY_PAYLOAD)


def test_capacity_revision_http_route_denies_missing_edit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _capacity_revision_route_app(monkeypatch, action)

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}",
        json={**CAPACITY_PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "edit-own access" in response.json()["error"]


def test_capacity_revision_route_policy_requires_exact_location_edit_own_grant():
    assert auth_route_policy(
        "PUT",
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}",
        enabled=True,
    ) == {
        "resource": "operating_pilot",
        "action": "edit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy(
        "PUT",
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}",
        enabled=False,
    ) is None


def test_demand_revision_sets_exact_edit_own_context_and_commits_result(monkeypatch):
    replacement_id = "e0000000-0000-4000-8000-000000000002"
    payload = {**PAYLOAD, "work_type": "mulch application"}
    connection, cursor = _connection_with_result(
        {
            "signal_id": replacement_id,
            "replaced_signal_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.revise_location_operating_pilot_demand_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        payload,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "signal_id": replacement_id,
        "replaced_signal_id": PROFILE_ID,
        "status": "draft",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "edit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "revise_location_operating_pilot_demand_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        "mulch application",
        operating_pilot_writes.date(2026, 11, 1),
        operating_pilot_writes.date(2026, 11, 30),
        operating_pilot_writes.Decimal("18.50"),
        "high",
        "Private synthetic planning note",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_demand_revision_is_rejected_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="signal identifier"):
        operating_pilot_writes.revise_location_operating_pilot_demand_draft(
            OPERATOR_ID, LOCATION_ID, "not-a-signal-id", REQUEST_ID, PAYLOAD,
            connection_factory=factory,
        )

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="Required hours"):
        operating_pilot_writes.revise_location_operating_pilot_demand_draft(
            OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID,
            {**PAYLOAD, "required_hours": "NaN"}, connection_factory=factory,
        )
    factory.assert_not_called()


def test_demand_revision_failure_rolls_back_and_closes_connection(monkeypatch):
    connection, _cursor = _connection_with_result(None)
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="revision returned no result"):
        operating_pilot_writes.revise_location_operating_pilot_demand_draft(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            REQUEST_ID,
            PAYLOAD,
            connection_factory=lambda: connection,
        )

    connection.commit.assert_not_called()
    connection.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def _demand_revision_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "revise_location_operating_pilot_demand_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_demand_revision_http_route_passes_ids_and_uses_no_store(monkeypatch):
    action = MagicMock(
        return_value={
            "signal_id": REQUEST_ID,
            "replaced_signal_id": PROFILE_ID,
            "status": "draft",
            "replayed": False,
        }
    )
    client = _demand_revision_route_app(monkeypatch, action)

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "draft"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, PAYLOAD)


def test_demand_revision_http_route_denies_missing_edit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _demand_revision_route_app(monkeypatch, action)

    response = client.put(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}",
        json={**PAYLOAD, "request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "edit-own access" in response.json()["error"]


def test_demand_revision_route_policy_requires_exact_location_edit_own_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}"
    assert auth_route_policy("PUT", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "edit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("PUT", path, enabled=False) is None


def test_capacity_submission_sets_exact_submit_own_context_and_commits(monkeypatch):
    connection, cursor = _connection_with_result(
        {"profile_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.submit_location_operating_pilot_capacity_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "profile_id": PROFILE_ID,
        "status": "submitted",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "submit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "submit_location_operating_pilot_capacity_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, PROFILE_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_capacity_submission_is_rejected_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="profile identifier"):
        operating_pilot_writes.submit_location_operating_pilot_capacity_draft(
            OPERATOR_ID,
            LOCATION_ID,
            "not-a-profile-id",
            REQUEST_ID,
            connection_factory=factory,
        )

    factory.assert_not_called()


def _capacity_submission_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "submit_location_operating_pilot_capacity_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_capacity_submission_http_route_requires_only_request_id_and_uses_no_store(monkeypatch):
    action = MagicMock(
        return_value={"profile_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    client = _capacity_submission_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/submit"

    invalid = client.post(path, json={"request_id": REQUEST_ID, "status": "approved"})
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "submitted"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID)


def test_capacity_submission_http_route_denies_missing_submit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _capacity_submission_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/submit",
        json={"request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "submit-own access" in response.json()["error"]


def test_capacity_submission_route_policy_requires_exact_location_submit_own_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/submit"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "submit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None


def test_demand_submission_sets_exact_submit_own_context_and_commits(monkeypatch):
    connection, cursor = _connection_with_result(
        {"signal_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.submit_location_operating_pilot_demand_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "signal_id": PROFILE_ID,
        "status": "submitted",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "submit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "submit_location_operating_pilot_demand_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, PROFILE_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_demand_submission_is_rejected_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="signal identifier"):
        operating_pilot_writes.submit_location_operating_pilot_demand_draft(
            OPERATOR_ID,
            LOCATION_ID,
            "not-a-signal-id",
            REQUEST_ID,
            connection_factory=factory,
        )

    factory.assert_not_called()


def _demand_submission_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "submit_location_operating_pilot_demand_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_demand_submission_http_route_accepts_only_request_id_and_is_no_store(monkeypatch):
    action = MagicMock(
        return_value={"signal_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    client = _demand_submission_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/submit"

    invalid = client.post(path, json={"request_id": REQUEST_ID, "status": "approved"})
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "submitted"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID)


def test_demand_submission_http_route_denies_missing_submit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _demand_submission_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/submit",
        json={"request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "submit-own access" in response.json()["error"]


def test_demand_submission_route_policy_requires_exact_location_submit_own_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/submit"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "submit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_resource_submission_sets_exact_submit_own_context_and_commits(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.submit_location_operating_pilot_resource_draft(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": PROFILE_ID,
        "status": "submitted",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "submit_own",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "submit_location_operating_pilot_resource_draft" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, PROFILE_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_invalid_resource_submission_is_rejected_before_database_access():
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match="draft identifier"):
        operating_pilot_writes.submit_location_operating_pilot_resource_draft(
            OPERATOR_ID,
            LOCATION_ID,
            "not-a-draft-id",
            REQUEST_ID,
            connection_factory=factory,
        )

    factory.assert_not_called()


def _resource_submission_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "submit_location_operating_pilot_resource_draft", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_resource_submission_http_route_accepts_only_request_id_and_is_no_store(monkeypatch):
    action = MagicMock(
        return_value={"draft_id": PROFILE_ID, "status": "submitted", "replayed": False}
    )
    client = _resource_submission_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/submit"

    invalid = client.post(path, json={"request_id": REQUEST_ID, "status": "approved"})
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "submitted"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID)


def test_resource_submission_http_route_denies_missing_submit_own_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _resource_submission_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/submit",
        json={"request_id": REQUEST_ID},
    )

    assert response.status_code == 403
    assert "submit-own access" in response.json()["error"]


def test_resource_submission_route_policy_requires_exact_location_submit_own_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/submit"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "submit_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_capacity_review_sets_exact_review_context_and_commits_append_result(monkeypatch):
    connection, cursor = _connection_with_result(
        {"profile_id": PROFILE_ID, "status": "rejected", "decision": "rejected", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.review_location_operating_pilot_capacity(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        {"decision": "rejected", "reason": "Please correct the period."},
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "profile_id": PROFILE_ID,
        "status": "rejected",
        "decision": "rejected",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "review",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "review_location_operating_pilot_capacity" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        "rejected",
        "Please correct the period.",
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"decision": "rejected"}, "reason is required"),
        ({"decision": "rejected", "reason": "  "}, "reason is required"),
        ({"decision": "rejected", "reason": "\t\n"}, "reason is required"),
        ({"decision": ["approved"]}, "Decision must be"),
        ({"decision": "approved", "reason": "x" * 2001}, "at most 2000"),
        ({"decision": "approved", "actor_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_capacity_review_is_rejected_before_database_access(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.review_location_operating_pilot_capacity(
            OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def _capacity_review_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "review_location_operating_pilot_capacity", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_capacity_review_http_route_requires_request_and_returns_no_store_result(monkeypatch):
    action = MagicMock(
        return_value={"profile_id": PROFILE_ID, "status": "approved", "decision": "approved", "replayed": False}
    )
    client = _capacity_review_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/review"

    invalid = client.post(path, json={"request_id": REQUEST_ID, "decision": "approved", "status": "approved"})
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(path, json={"request_id": REQUEST_ID, "decision": "approved"})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["decision"] == "approved"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, {"decision": "approved"})


def test_capacity_review_http_route_denies_missing_review_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _capacity_review_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/review",
        json={"request_id": REQUEST_ID, "decision": "approved"},
    )

    assert response.status_code == 403
    assert "review access" in response.json()["error"]


def test_capacity_review_route_policy_requires_exact_location_review_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-profiles/{PROFILE_ID}/review"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_competency_review_sets_exact_review_context_and_commits_decision(monkeypatch):
    connection, cursor = _connection_with_result(
        {"draft_id": PROFILE_ID, "status": "verified", "decision": "verified", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.review_location_operating_pilot_competency_assessment(
        OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID,
        {"decision": "verified"}, connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "draft_id": PROFILE_ID,
        "status": "verified",
        "decision": "verified",
        "replayed": False,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    })]
    assert "review_location_operating_pilot_competency" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID, PROFILE_ID, REQUEST_ID, "verified", None,
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"decision": "rejected"}, "reason is required"),
        ({"decision": "rejected", "reason": "  "}, "reason is required"),
        ({"decision": "verified", "reason": "not allowed"}, "only accepted when rejecting"),
        ({"decision": ["verified"]}, "Decision must be"),
        ({"decision": "rejected", "reason": "x" * 2001}, "at most 2000"),
        ({"decision": "verified", "actor_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_competency_review_fails_before_database_access(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.review_location_operating_pilot_competency_assessment(
            OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, payload,
            connection_factory=factory,
        )

    factory.assert_not_called()


def _competency_review_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        operating_pilot_writes,
        "review_location_operating_pilot_competency_assessment",
        action,
    )
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return TestClient(app)


def test_competency_review_http_route_requires_request_and_returns_no_store(monkeypatch):
    action = MagicMock(return_value={
        "draft_id": PROFILE_ID, "status": "rejected", "decision": "rejected", "replayed": False,
    })
    client = _competency_review_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/competency-assessments/{PROFILE_ID}/review"

    invalid = client.post(path, json={
        "request_id": REQUEST_ID, "decision": "verified", "status": "verified",
    })
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(path, json={
        "request_id": REQUEST_ID,
        "decision": "rejected",
        "reason": "Please provide clearer evidence.",
    })

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["decision"] == "rejected"
    action.assert_called_once_with(
        OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID,
        {"decision": "rejected", "reason": "Please provide clearer evidence."},
    )


def test_competency_review_route_policy_requires_exact_location_review_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/competency-assessments/{PROFILE_ID}/review"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot", "action": "review", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_demand_review_sets_exact_review_context_and_commits_decision(monkeypatch):
    connection, cursor = _connection_with_result(
        {"signal_id": PROFILE_ID, "status": "approved", "decision": "approved", "replayed": False}
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.review_location_operating_pilot_demand(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        {"decision": "approved"},
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "signal_id": PROFILE_ID,
        "status": "approved",
        "decision": "approved",
        "replayed": False,
    }
    assert contexts == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "operating_pilot",
                "action": "review",
            },
        )
    ]
    assert "SET LOCAL statement_timeout" in cursor.execute.call_args_list[0].args[0]
    assert "review_location_operating_pilot_demand" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        "approved",
        None,
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"decision": "rejected"}, "reason is required"),
        ({"decision": "rejected", "reason": "  "}, "reason is required"),
        ({"decision": ["approved"]}, "Decision must be"),
        ({"decision": "approved", "reason": "x" * 2001}, "at most 2000"),
        ({"decision": "approved", "actor_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_demand_review_is_rejected_before_database_access(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))

    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.review_location_operating_pilot_demand(
            OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, payload, connection_factory=factory
        )

    factory.assert_not_called()


def _demand_review_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(operating_pilot_writes, "review_location_operating_pilot_demand", action)
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(operator=SimpleNamespace(operator_id=OPERATOR_ID))
        return await call_next(request)

    return TestClient(app)


def test_demand_review_http_route_requires_supported_fields_and_returns_no_store(monkeypatch):
    action = MagicMock(
        return_value={"signal_id": PROFILE_ID, "status": "rejected", "decision": "rejected", "replayed": False}
    )
    client = _demand_review_route_app(monkeypatch, action)
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/review"

    invalid = client.post(path, json={"request_id": REQUEST_ID, "decision": "approved", "status": "approved"})
    assert invalid.status_code == 400
    action.assert_not_called()

    response = client.post(
        path,
        json={"request_id": REQUEST_ID, "decision": "rejected", "reason": "Review evidence and revise."},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["decision"] == "rejected"
    action.assert_called_once_with(
        OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID,
        {"decision": "rejected", "reason": "Review evidence and revise."},
    )


def test_demand_review_http_route_denies_missing_review_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _demand_review_route_app(monkeypatch, action)

    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/review",
        json={"request_id": REQUEST_ID, "decision": "approved"},
    )

    assert response.status_code == 403
    assert "review access" in response.json()["error"]


def test_demand_review_route_policy_requires_exact_location_review_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals/{PROFILE_ID}/review"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_resource_review_route_policy_requires_exact_location_review_grant():
    path = (
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/"
        f"{PROFILE_ID}/review"
    )
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_resource_review_decision_sets_exact_context_and_commits_without_fulfillment(
    monkeypatch,
):
    connection, cursor = _connection_with_result(
        {
            "resource_request_id": PROFILE_ID,
            "status": "reviewed",
            "decision": "approved",
            "replayed": False,
        }
    )
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.review_location_operating_pilot_resource_request(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        {"decision": "approved"},
        connection_factory=lambda: connection,
    )

    assert result == {"location_id": LOCATION_ID, "resource_request_id": PROFILE_ID,
                      "status": "reviewed", "decision": "approved", "replayed": False}
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    })]
    assert "review_location_operating_pilot_resource_request" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (
        LOCATION_ID, PROFILE_ID, REQUEST_ID, "approved", None
    )
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"decision": "rejected"}, "reason is required"),
        ({"decision": "partial"}, "Decision must"),
        ({"decision": "approved", "reason": "x" * 2001}, "at most 2000"),
        ({"decision": "approved", "reason": "bad\x00reason"}, "at most 2000"),
        ({"decision": "approved", "actor_party_id": OPERATOR_ID}, "unsupported fields"),
    ],
)
def test_invalid_resource_review_decision_fails_before_database_access(payload, message):
    factory = MagicMock(side_effect=AssertionError("database opened before validation"))
    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid, match=message):
        operating_pilot_writes.review_location_operating_pilot_resource_request(
            OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID, payload,
            connection_factory=factory,
        )
    factory.assert_not_called()


def _resource_review_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        operating_pilot_writes,
        "review_location_operating_pilot_resource_request",
        action,
    )
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return TestClient(app)


def test_resource_review_http_route_is_exact_no_store_and_requires_stable_request_id(monkeypatch):
    action = MagicMock(return_value={
        "resource_request_id": PROFILE_ID,
        "status": "reviewed",
        "decision": "rejected",
        "replayed": False,
    })
    client = _resource_review_route_app(monkeypatch, action)
    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/review",
        json={"request_id": REQUEST_ID, "decision": "rejected", "reason": "No supporting quote."},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["decision"] == "rejected"
    action.assert_called_once_with(
        OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID,
        {"decision": "rejected", "reason": "No supporting quote."},
    )


def test_resource_review_http_route_denies_missing_review_context(monkeypatch):
    action = MagicMock(side_effect=TenantContextDenied("denied"))
    client = _resource_review_route_app(monkeypatch, action)
    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/review",
        json={"request_id": REQUEST_ID, "decision": "approved"},
    )
    assert response.status_code == 403
    assert "review access" in response.json()["error"]


def test_resource_fulfillment_route_policies_require_exact_fulfill_grant():
    queue_path = f"/operator/api/operating-pilot/{LOCATION_ID}/resource-fulfillment-queue"
    fulfill_path = (
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/fulfill"
    )
    expected = {
        "resource": "operating_pilot",
        "action": "fulfill",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", queue_path, enabled=True) == expected
    assert auth_route_policy("POST", fulfill_path, enabled=True) == expected
    assert auth_route_policy("GET", fulfill_path, enabled=True) is None
    assert auth_route_policy("POST", fulfill_path + "/extra", enabled=True) is None
    assert auth_route_policy("POST", fulfill_path, enabled=False) is None


def test_resource_fulfillment_sets_exact_context_and_commits_without_payment_or_inventory(
    monkeypatch,
):
    connection, cursor = _connection_with_result({
        "resource_request_id": PROFILE_ID,
        "status": "closed",
        "decision": "fulfilled",
        "replayed": False,
    })
    contexts = []
    monkeypatch.setattr(
        operating_pilot_writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = operating_pilot_writes.fulfill_location_operating_pilot_resource_request(
        OPERATOR_ID,
        LOCATION_ID,
        PROFILE_ID,
        REQUEST_ID,
        connection_factory=lambda: connection,
    )

    assert result == {
        "location_id": LOCATION_ID,
        "resource_request_id": PROFILE_ID,
        "status": "closed",
        "decision": "fulfilled",
        "replayed": False,
    }
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "fulfill",
    })]
    assert "fulfill_location_operating_pilot_resource_request" in cursor.execute.call_args_list[2].args[0]
    assert cursor.execute.call_args_list[2].args[1] == (LOCATION_ID, PROFILE_ID, REQUEST_ID)
    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("location_id", "resource_request_id", "request_id"),
    [
        ("bad", PROFILE_ID, REQUEST_ID),
        (LOCATION_ID, "bad", REQUEST_ID),
        (LOCATION_ID, PROFILE_ID, "bad"),
    ],
)
def test_invalid_resource_fulfillment_ids_fail_before_database_access(
    location_id, resource_request_id, request_id
):
    factory = MagicMock(side_effect=AssertionError("database opened before UUID validation"))
    with pytest.raises(operating_pilot_writes.OperatingPilotWriteInvalid):
        operating_pilot_writes.fulfill_location_operating_pilot_resource_request(
            OPERATOR_ID,
            location_id,
            resource_request_id,
            request_id,
            connection_factory=factory,
        )
    factory.assert_not_called()


def _resource_fulfillment_route_app(monkeypatch, action, provider=object()):
    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        operating_pilot_writes,
        "fulfill_location_operating_pilot_resource_request",
        action,
    )
    router = APIRouter()
    register_operating_pilot_routes(router, provider, run_inline, __import__("psycopg2"))
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def attach_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    return TestClient(app)


def test_resource_fulfillment_http_route_is_exact_and_no_store(monkeypatch):
    action = MagicMock(return_value={
        "resource_request_id": PROFILE_ID,
        "status": "closed",
        "decision": "fulfilled",
        "replayed": False,
    })
    client = _resource_fulfillment_route_app(monkeypatch, action)
    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/fulfill",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["decision"] == "fulfilled"
    action.assert_called_once_with(OPERATOR_ID, LOCATION_ID, PROFILE_ID, REQUEST_ID)


def test_resource_fulfillment_http_route_rejects_extra_payload_fields(monkeypatch):
    action = MagicMock()
    client = _resource_fulfillment_route_app(monkeypatch, action)
    response = client.post(
        f"/operator/api/operating-pilot/{LOCATION_ID}/resource-requests/{PROFILE_ID}/fulfill",
        json={"request_id": REQUEST_ID, "decision": "fulfilled"},
    )
    assert response.status_code == 400
    action.assert_not_called()
