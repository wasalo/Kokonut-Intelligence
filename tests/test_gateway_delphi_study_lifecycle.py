"""Focused contracts for authenticated Delphi study lifecycle transitions."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_study_lifecycle as lifecycle

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
REQUEST_ID = str(uuid4())
OPENED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
CLOSED_AT = datetime(2026, 10, 25, 13, 0, tzinfo=timezone.utc)


class _Connection:
    def __init__(self, row=None):
        self.row = row
        self.operations = []
        self.events = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)

    def fetchone(self):
        return self.connection.row


def _set_context(connection, **kwargs):
    connection.events.append("SIGNED_CONTEXT")
    connection.context = kwargs


def _arguments(**overrides):
    result = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "action": "open",
        "request_id": REQUEST_ID,
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize("action", ["open", "close"])
def test_transition_uses_exact_action_context_then_bounded_sql(action):
    status = "open" if action == "open" else "closed"
    row = (STUDY_ID, LOCATION_ID, status, OPENED_AT, CLOSED_AT if action == "close" else None, False)
    connection = _Connection(row=row)
    with patch.object(lifecycle, "set_operator_tenant_context", _set_context):
        result = lifecycle.transition_location_delphi_study(
            **_arguments(action=action), connection_factory=lambda: connection
        )

    call_index = next(
        index for index, event in enumerate(connection.events)
        if "transition_location_delphi_study" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < call_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": action,
    }
    query, params = connection.operations[-1]
    assert "transition_location_delphi_study" in query
    assert params == (LOCATION_ID, STUDY_ID, action, REQUEST_ID)
    assert result == {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "status": status,
        "opened_at": OPENED_AT,
        "closed_at": CLOSED_AT if action == "close" else None,
        "replayed": False,
    }
    assert connection.committed and connection.rolled_back and connection.closed


def test_exact_transition_retry_is_reported_as_replayed():
    connection = _Connection(
        row=(STUDY_ID, LOCATION_ID, "open", OPENED_AT, None, True)
    )
    with patch.object(lifecycle, "set_operator_tenant_context", _set_context):
        result = lifecycle.transition_location_delphi_study(
            **_arguments(), connection_factory=lambda: connection
        )
    assert result["replayed"] is True
    assert result["status"] == "open"
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("study_id", "bad"),
        ("request_id", "bad"),
        ("action", "publish"),
        ("action", []),
    ],
)
def test_invalid_transition_fails_before_database(field, value):
    with pytest.raises(lifecycle.DelphiStudyLifecycleInvalid):
        lifecycle.transition_location_delphi_study(
            **_arguments(**{field: value}),
            connection_factory=lambda: pytest.fail("invalid lifecycle opened a connection"),
        )


def test_database_failure_rolls_back_and_closes_connection():
    class _FailingCursor(_Cursor):
        def execute(self, query, params=None):
            if "transition_location_delphi_study" in query:
                raise RuntimeError("synthetic database failure")
            super().execute(query, params)

    class _FailingConnection(_Connection):
        def cursor(self):
            return _FailingCursor(self)

    connection = _FailingConnection()
    with patch.object(lifecycle, "set_operator_tenant_context", _set_context):
        with pytest.raises(RuntimeError, match="synthetic database failure"):
            lifecycle.transition_location_delphi_study(
                **_arguments(), connection_factory=lambda: connection
            )
    assert not connection.committed
    assert connection.rolled_back and connection.closed


def test_open_readiness_sets_signed_open_context_and_returns_only_safe_projection():
    connection = _Connection(
        row=(STUDY_ID, LOCATION_ID, "draft", True, True, False, False,
             ["consented_panel_below_minimum"])
    )
    with patch.object(lifecycle, "set_operator_tenant_context", _set_context):
        result = lifecycle.get_location_delphi_study_open_readiness(
            OPERATOR_ID, LOCATION_ID, STUDY_ID, connection_factory=lambda: connection
        )

    query, params = connection.operations[-1]
    assert "get_location_delphi_study_open_readiness" in query
    assert params == (LOCATION_ID, STUDY_ID)
    assert connection.events.index("SIGNED_CONTEXT") < len(connection.events) - 1
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "open",
    }
    assert result == {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "status": "draft",
        "has_question": True,
        "minimum_policy_valid": True,
        "consent_minimum_met": False,
        "eligible_to_open": False,
        "blocker_codes": ["consented_panel_below_minimum"],
    }
    assert "participant_count" not in result and "consented_count" not in result
    assert connection.committed and connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("operator_id", "location_id", "study_id"),
    [("bad", LOCATION_ID, STUDY_ID), (OPERATOR_ID, "bad", STUDY_ID),
     (OPERATOR_ID, LOCATION_ID, "bad")],
)
def test_open_readiness_invalid_ids_fail_before_database(operator_id, location_id, study_id):
    with pytest.raises(lifecycle.DelphiStudyLifecycleInvalid):
        lifecycle.get_location_delphi_study_open_readiness(
            operator_id, location_id, study_id,
            connection_factory=lambda: pytest.fail("invalid scope opened a connection"),
        )


def test_stopping_evaluation_sets_exact_context_and_returns_bounded_result():
    expected = {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "should_stop": False,
        "outcome": "insufficient_participation",
        "items": [{"item_id": str(uuid4()), "should_stop": False,
                   "outcome": "insufficient_participation"}],
        "evaluated_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
    }
    connection = _Connection(row=(expected,))
    with patch.object(lifecycle, "set_operator_tenant_context", _set_context):
        result = lifecycle.evaluate_location_delphi_stopping(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            request_id=REQUEST_ID,
            connection_factory=lambda: connection,
        )
    query, params = connection.operations[-1]
    assert "evaluate_location_delphi_stopping" in query
    assert params == (LOCATION_ID, STUDY_ID, REQUEST_ID)
    assert connection.events.index("SIGNED_CONTEXT") < len(connection.events) - 1
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "evaluate_stopping",
    }
    assert result == expected
    assert connection.committed and connection.rolled_back and connection.closed
    assert "participant_count" not in result


@pytest.mark.parametrize(
    ("operator_id", "location_id", "study_id", "request_id"),
    [("bad", LOCATION_ID, STUDY_ID, REQUEST_ID),
     (OPERATOR_ID, "bad", STUDY_ID, REQUEST_ID),
     (OPERATOR_ID, LOCATION_ID, "bad", REQUEST_ID),
     (OPERATOR_ID, LOCATION_ID, STUDY_ID, "bad")],
)
def test_stopping_evaluation_invalid_ids_fail_before_database(
    operator_id, location_id, study_id, request_id
):
    with pytest.raises(lifecycle.DelphiStudyLifecycleInvalid):
        lifecycle.evaluate_location_delphi_stopping(
            operator_id,
            location_id,
            study_id,
            request_id=request_id,
            connection_factory=lambda: pytest.fail("invalid IDs opened a database connection"),
        )


def _make_app(provider, run_in_threadpool, psycopg2_errors=None):
    from services.gateway.delphi_study_lifecycle_routes import (
        register_delphi_study_lifecycle_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_study_lifecycle_routes(
        router,
        provider,
        run_in_threadpool,
        psycopg2_errors or __import__("psycopg2"),
    )
    app.include_router(router)
    return app


@pytest.mark.parametrize(
    ("action", "status"),
    [("open", "open"), ("close", "closed")],
)
def test_route_uses_session_identity_exact_action_and_private_response(action, status):
    calls = []
    expected = {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "status": status,
        "opened_at": OPENED_AT.isoformat(),
        "closed_at": CLOSED_AT.isoformat() if action == "close" else None,
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/{action}",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID, action)
    assert calls[0][2] == {"request_id": REQUEST_ID}


@pytest.mark.parametrize(
    "payload",
    [{}, {"request_id": REQUEST_ID, "status": "open"}],
)
def test_route_rejects_missing_or_extra_fields_before_database(payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke the lifecycle service")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open", json=payload
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_route_fails_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    response = TestClient(_make_app(None, run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 404


def test_route_maps_scope_denial_to_private_forbidden():
    async def run_in_threadpool(*_args, **_kwargs):
        raise TenantContextDenied("private tenant details")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 403
    assert "private tenant details" not in response.text


def test_open_readiness_route_uses_session_identity_and_no_store():
    calls = []
    expected = {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "status": "draft",
        "has_question": True,
        "minimum_policy_valid": True,
        "consent_minimum_met": True,
        "eligible_to_open": True,
        "blocker_codes": [],
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_make_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open-readiness"
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID)


def test_open_readiness_route_publishes_a_strict_success_contract():
    operation = _make_app(object(), lambda *_args, **_kwargs: None).openapi()["paths"][
        "/operator/api/delphi/{location_id}/studies/{study_id}/open-readiness"
    ]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DelphiStudyOpenReadinessResponse"
    }
    schema = _make_app(object(), lambda *_args, **_kwargs: None).openapi()["components"][
        "schemas"
    ]["DelphiStudyOpenReadinessResponse"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "study_id",
        "location_id",
        "status",
        "has_question",
        "minimum_policy_valid",
        "consent_minimum_met",
        "eligible_to_open",
        "blocker_codes",
    }


@pytest.mark.parametrize(
    "invalid_result",
    [
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "status": "draft",
            "has_question": True,
            "minimum_policy_valid": True,
            "consent_minimum_met": True,
            "eligible_to_open": True,
            "blocker_codes": [],
            "private_internal_field": "must not escape",
        },
        {
            "study_id": STUDY_ID,
            "location_id": str(uuid4()),
            "status": "draft",
            "has_question": True,
            "minimum_policy_valid": True,
            "consent_minimum_met": True,
            "eligible_to_open": True,
            "blocker_codes": [],
        },
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "status": "submitted",
            "has_question": True,
            "minimum_policy_valid": True,
            "consent_minimum_met": True,
            "eligible_to_open": True,
            "blocker_codes": [],
        },
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "status": "draft",
            "has_question": True,
            "minimum_policy_valid": True,
            "consent_minimum_met": True,
            "eligible_to_open": True,
            "blocker_codes": ["question_required"],
        },
        {
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "status": "draft",
            "has_question": False,
            "minimum_policy_valid": True,
            "consent_minimum_met": True,
            "eligible_to_open": True,
            "blocker_codes": [],
        },
    ],
)
def test_open_readiness_route_sanitizes_invalid_service_projection(invalid_result):
    async def run_in_threadpool(*_args, **_kwargs):
        return invalid_result

    response = TestClient(_make_app(object(), run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open-readiness"
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi study readiness is unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private_internal_field" not in response.text
    assert "must not escape" not in response.text


def test_open_readiness_route_fails_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled readiness must not reach the service")

    response = TestClient(_make_app(None, run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open-readiness"
    )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_stopping_route_uses_session_identity_and_no_store():
    calls = []
    expected = {
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "should_stop": True,
        "outcome": "consensus_reached",
        "items": [{"item_id": str(uuid4()), "should_stop": True,
                   "outcome": "consensus_reached"}],
        "evaluated_at": "2026-10-25T12:00:00+00:00",
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/stopping-evaluation",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
    assert calls[0][2] == {"request_id": REQUEST_ID}


@pytest.mark.parametrize(
    "payload",
    [{}, {"request_id": REQUEST_ID, "should_stop": True}],
)
def test_stopping_route_rejects_missing_or_extra_fields(payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid stopping request must not reach the service")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/stopping-evaluation",
        json=payload,
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("pgcode", "status"), [("42501", 403), ("22023", 409)])
def test_route_maps_database_errors_without_exposing_details(pgcode, status):
    class _DatabaseError(Exception):
        pass

    async def run_in_threadpool(*_args, **_kwargs):
        error = _DatabaseError("private database text")
        error.pgcode = pgcode
        raise error

    response = TestClient(
        _make_app(object(), run_in_threadpool, SimpleNamespace(Error=_DatabaseError))
    ).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/open",
        json={"request_id": REQUEST_ID},
    )
    assert response.status_code == status
    assert "private database text" not in response.text
    assert response.headers["cache-control"] == "no-store"
