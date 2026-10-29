"""Focused contracts for authenticated Delphi questionnaire item creation."""

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_study_items as items

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
ITEM_ID = str(uuid4())
REQUEST_ID = str(uuid4())
CREATED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


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
        "request_id": REQUEST_ID,
        "item_type": "option",
        "label": "  Water resilience  ",
        "description": "  Compare practical options  ",
        "scale": "desirability",
        "min_value": -1,
        "max_value": 1,
    }
    result.update(overrides)
    return result


def test_item_creation_uses_draft_context_before_one_bounded_function_call():
    connection = _Connection(
        row=(
            ITEM_ID, STUDY_ID, LOCATION_ID, "option", "Water resilience",
            "Compare practical options", "desirability", Decimal("-1.0000"),
            Decimal("1.0000"), CREATED_AT, False,
        )
    )
    with patch.object(items, "set_operator_tenant_context", _set_context):
        result = items.create_location_delphi_study_item(
            **_arguments(), connection_factory=lambda: connection
        )

    call_index = next(
        index for index, event in enumerate(connection.events)
        if "create_location_delphi_study_item" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < call_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "draft",
    }
    query, params = connection.operations[-1]
    assert "create_location_delphi_study_item" in query
    assert params == (
        LOCATION_ID,
        STUDY_ID,
        "option",
        "Water resilience",
        "Compare practical options",
        "desirability",
        Decimal("-1.0000"),
        Decimal("1.0000"),
        REQUEST_ID,
    )
    assert result["item_id"] == ITEM_ID
    assert result["location_id"] == LOCATION_ID
    assert result["min_value"] == Decimal("-1.0000")
    assert result["replayed"] is False
    assert connection.committed and connection.rolled_back and connection.closed


def test_item_retry_result_is_reported_without_changing_request_identity():
    connection = _Connection(
        row=(
            ITEM_ID, STUDY_ID, LOCATION_ID, "issue", "Water resilience", None,
            "probability", Decimal("0.0000"), Decimal("100.0000"), CREATED_AT, True,
        )
    )
    with patch.object(items, "set_operator_tenant_context", _set_context):
        result = items.create_location_delphi_study_item(
            **_arguments(
                item_type="issue",
                label="Water resilience",
                description=None,
                scale="probability",
                min_value=0,
                max_value=100,
            ),
            connection_factory=lambda: connection,
        )
    assert result["replayed"] is True
    assert result["item_id"] == ITEM_ID
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("study_id", "bad"),
        ("request_id", "bad"),
        ("item_type", "unsupported"),
        ("label", "  "),
        ("label", "x" * 256),
        ("description", "x" * 4001),
        ("scale", "unsupported"),
        ("min_value", True),
        ("min_value", float("nan")),
        ("min_value", -10000),
        ("max_value", 10000),
        ("min_value", 0.00001),
        ("max_value", -1),
        ("min_value", 1),
    ],
)
def test_invalid_item_request_fails_before_database(field, value):
    with pytest.raises(items.DelphiStudyItemInvalid):
        items.create_location_delphi_study_item(
            **_arguments(**{field: value}),
            connection_factory=lambda: pytest.fail("invalid item opened a connection"),
        )


def test_database_failure_rolls_back_and_closes_item_connection():
    class _FailingCursor(_Cursor):
        def execute(self, query, params=None):
            if "create_location_delphi_study_item" in query:
                raise RuntimeError("synthetic database failure")
            super().execute(query, params)

    class _FailingConnection(_Connection):
        def cursor(self):
            return _FailingCursor(self)

    connection = _FailingConnection()
    with patch.object(items, "set_operator_tenant_context", _set_context):
        with pytest.raises(RuntimeError, match="synthetic database failure"):
            items.create_location_delphi_study_item(
                **_arguments(), connection_factory=lambda: connection
            )
    assert not connection.committed
    assert connection.rolled_back and connection.closed


def _make_app(provider, run_in_threadpool, psycopg2_errors=None):
    from services.gateway.delphi_study_item_routes import register_delphi_study_item_routes

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_study_item_routes(
        router,
        provider,
        run_in_threadpool,
        psycopg2_errors or __import__("psycopg2"),
    )
    app.include_router(router)
    return app


def test_item_route_uses_session_identity_bounded_defaults_and_private_response():
    calls = []
    expected = {
        "item_id": ITEM_ID,
        "study_id": STUDY_ID,
        "location_id": LOCATION_ID,
        "item_type": "option",
        "label": "Water resilience",
        "description": None,
        "scale": "desirability",
        "min_value": -1,
        "max_value": 1,
        "created_at": CREATED_AT.isoformat(),
        "replayed": False,
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )
    assert response.status_code == 201 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
    assert calls[0][2] == {
        "request_id": REQUEST_ID,
        "item_type": "option",
        "label": "Water resilience",
        "description": None,
        "scale": "desirability",
        "min_value": -1,
        "max_value": 1,
    }


def test_item_route_reports_exact_retry_as_replay():
    async def run_in_threadpool(*_args, **_kwargs):
        return {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "issue",
            "label": "Water resilience",
            "description": None,
            "scale": "probability",
            "min_value": Decimal("0.0000"),
            "max_value": Decimal("100.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": True,
        }

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {
        "item_id", "study_id", "location_id", "item_type", "label",
        "description", "scale", "min_value", "max_value", "created_at", "replayed",
    }
    assert response.json()["replayed"] is True
    assert response.json()["study_id"] == STUDY_ID
    assert response.json()["location_id"] == LOCATION_ID


@pytest.mark.parametrize(
    "service_result",
    [
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
            "private_debug": "private-secret-marker",
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": str(uuid4()),
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": str(uuid4()),
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "unsupported",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": datetime(2026, 10, 25, 12, 0).isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-10000.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": False,
        },
        {
            "item_id": ITEM_ID,
            "study_id": STUDY_ID,
            "location_id": LOCATION_ID,
            "item_type": "option",
            "label": "Water resilience",
            "description": None,
            "scale": "desirability",
            "min_value": Decimal("-1.0000"),
            "max_value": Decimal("1.0000"),
            "created_at": CREATED_AT.isoformat(),
            "replayed": "false",
        },
    ],
)
def test_item_route_rejects_malformed_response_with_sanitized_no_store_error(
    caplog, service_result
):
    async def run_in_threadpool(*_args, **_kwargs):
        return service_result

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi study item unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private-secret-marker" not in response.text
    assert "private-secret-marker" not in caplog.text


def test_item_route_openapi_declares_strict_create_and_replay_success_models():
    schema = _make_app(object(), lambda *_args, **_kwargs: None).openapi()
    operation = schema["paths"][
        "/operator/api/delphi/{location_id}/studies/{study_id}/items"
    ]["post"]

    assert operation["responses"]["201"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/DelphiStudyItemCreateResponse")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/DelphiStudyItemCreateResponse")
    model = schema["components"]["schemas"]["DelphiStudyItemCreateResponse"]
    assert model["additionalProperties"] is False
    assert set(model["properties"]) == {
        "item_id", "study_id", "location_id", "item_type", "label",
        "description", "scale", "min_value", "max_value", "created_at", "replayed",
    }
    assert set(model["required"]) == set(model["properties"])


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": REQUEST_ID},
        {"label": "Water resilience"},
        {"request_id": REQUEST_ID, "label": "Water resilience", "target_entity_id": STUDY_ID},
    ],
)
def test_item_route_rejects_missing_or_unsupported_fields_before_service(payload):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke item service")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items", json=payload
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_item_route_fails_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach item service")

    response = TestClient(_make_app(None, run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )
    assert response.status_code == 404


def test_item_route_maps_scope_denial_to_private_forbidden():
    async def run_in_threadpool(*_args, **_kwargs):
        raise TenantContextDenied("private tenant details")

    response = TestClient(_make_app(object(), run_in_threadpool)).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )
    assert response.status_code == 403
    assert "private tenant details" not in response.text


@pytest.mark.parametrize(("pgcode", "status"), [("42501", 403), ("22023", 409)])
def test_item_route_maps_database_errors_without_exposing_details(pgcode, status):
    class _DatabaseError(Exception):
        pass

    async def run_in_threadpool(*_args, **_kwargs):
        error = _DatabaseError("private database text")
        error.pgcode = pgcode
        raise error

    response = TestClient(
        _make_app(object(), run_in_threadpool, SimpleNamespace(Error=_DatabaseError))
    ).post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/items",
        json={"request_id": REQUEST_ID, "label": "Water resilience"},
    )
    assert response.status_code == status
    assert "private database text" not in response.text
    assert response.headers["cache-control"] == "no-store"
