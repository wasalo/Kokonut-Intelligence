"""Focused tenant and privacy contract for Delphi consultation reads."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_consultation as consultation

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())


class _Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.operations = []
        self.events = []
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return _Cursor(self)

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

    def fetchall(self):
        return self.connection.rows


def test_listing_sets_signed_location_context_before_projection_and_cleans_up():
    item = {"item_id": str(uuid4()), "results_available": False, "median": None}
    row = (STUDY_ID, "Soil priorities", None, "real_time", "open", None, None, None, [item])
    connection = _Connection([row])
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)
        conn.events.append("SIGNED_CONTEXT")

    with patch.object(consultation, "set_operator_tenant_context", set_context):
        result = consultation.list_location_delphi_consultations(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    projection_event_index = next(
        index for index, event in enumerate(connection.events)
        if "list_location_delphi_consultations" in event
    )
    projection_operation_index = next(
        index for index, (query, _params) in enumerate(connection.operations)
        if "list_location_delphi_consultations" in query
    )
    assert connection.events.index("SIGNED_CONTEXT") < projection_event_index
    assert connection.operations[projection_operation_index][1] == (LOCATION_ID, 51, 0)
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "read",
    }]
    assert result == {
        "location_id": LOCATION_ID,
        "offset": 0,
        "studies": [{
            "study_id": STUDY_ID,
            "title": "Soil priorities",
            "description": None,
            "variation": "real_time",
            "status": "open",
            "opened_at": None,
            "closed_at": None,
            "created_at": None,
            "items": [item],
        }],
        "has_more": False,
    }
    assert connection.rolled_back and connection.closed
    assert not any("READ ONLY" in query for query, _params in connection.operations)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad-operator"),
        ("location_id", "bad-location"),
        ("limit", 0),
        ("limit", 51),
        ("limit", "1.5"),
        ("limit", True),
        ("offset", -1),
        ("offset", 10001),
        ("offset", "1.5"),
        ("offset", False),
    ],
)
def test_invalid_request_fails_before_database_connection(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "offset": 0,
        "limit": 50,
    }
    arguments[field] = value
    with pytest.raises(consultation.DelphiConsultationInvalid):
        consultation.list_location_delphi_consultations(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a database connection"),
        )


def test_listing_returns_only_requested_page_and_has_more_flag():
    connection = _Connection([
        (str(uuid4()), f"Study {index}", None, "real_time", "open", None, None, None, [])
        for index in range(3)
    ])
    with patch.object(consultation, "set_operator_tenant_context"):
        result = consultation.list_location_delphi_consultations(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=2,
            connection_factory=lambda: connection,
        )
    assert len(result["studies"]) == 2
    assert result["has_more"] is True
    assert result["offset"] == 2
    projection = next(
        params for query, params in connection.operations
        if "list_location_delphi_consultations" in query
    )
    assert projection == (LOCATION_ID, 3, 2)


def test_database_tenant_denial_rolls_back_and_closes_connection():
    connection = _Connection()
    with patch.object(
        consultation,
        "set_operator_tenant_context",
        side_effect=TenantContextDenied("no matching grant"),
    ):
        with pytest.raises(TenantContextDenied):
            consultation.list_location_delphi_consultations(
                OPERATOR_ID,
                LOCATION_ID,
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any(
        "list_location_delphi_consultations" in query
        for query, _params in connection.operations
    )


def _make_app(provider, list_func, run_in_threadpool):
    from services.gateway.delphi_consultation_routes import register_delphi_consultation_routes

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_consultation_routes(router, provider, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router)
    return app


def test_route_returns_no_store_scoped_projection():
    async def run_in_threadpool(func, *args, **kwargs):
        return list_func(*args, **kwargs)

    expected = {
        "location_id": LOCATION_ID,
        "offset": 0,
        "studies": [{"study_id": STUDY_ID, "items": []}],
        "has_more": False,
    }
    def list_func(*_args, **_kwargs):
        return expected

    client = TestClient(_make_app(object(), list_func, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/studies")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_route_fails_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("disabled OIDC must not invoke the data service")

    client = TestClient(_make_app(None, lambda *_args, **_kwargs: None, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/studies")
    assert response.status_code == 404


def test_route_openapi_publishes_service_page_bounds():
    async def run_in_threadpool(func, *args, **kwargs):
        return list_func(*args, **kwargs)

    def list_func(*_args, **_kwargs):
        return {"location_id": LOCATION_ID, "offset": 0, "studies": [], "has_more": False}

    app = _make_app(object(), list_func, run_in_threadpool)
    parameters = {
        parameter["name"]: parameter["schema"]
        for parameter in app.openapi()["paths"]["/operator/api/delphi/{location_id}/studies"]["get"]["parameters"]
    }

    assert parameters["limit"] == {"type": "integer", "minimum": 1, "maximum": 50, "default": 50, "title": "Limit"}
    assert parameters["offset"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 10000,
        "default": 0,
        "title": "Offset",
    }


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=10001"])
def test_route_rejects_out_of_bounds_paging_before_service(query):
    service_calls = []

    async def run_in_threadpool(func, *args, **kwargs):
        service_calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, "offset": kwargs["offset"], "studies": [], "has_more": False}

    client = TestClient(
        _make_app(object(), lambda *_args, **_kwargs: None, run_in_threadpool)
    )
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/studies?{query}")

    assert response.status_code == 422
    assert service_calls == []


def test_route_forwards_validated_page_values_to_service():
    service_calls = []

    async def run_in_threadpool(func, *args, **kwargs):
        service_calls.append((args, kwargs))
        return {"location_id": LOCATION_ID, "offset": kwargs["offset"], "studies": [], "has_more": False}

    client = TestClient(
        _make_app(object(), lambda *_args, **_kwargs: None, run_in_threadpool)
    )
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/studies?limit=30&offset=400")

    assert response.status_code == 200
    assert service_calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 30, "offset": 400})]
