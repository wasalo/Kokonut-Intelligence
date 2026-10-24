"""Source and route contracts for scoped business canvas draft creation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from services.gateway import business_planning_writes as writes

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
REQUEST_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=None):
        self.connection.operations.append(("execute", query, parameters))

    def fetchone(self):
        return (
            "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "draft",
            1,
            "2026-10-19T00:00:00Z",
            False,
        )


class _Connection:
    def __init__(self):
        self.operations = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _payload(**overrides):
    return {"request_id": REQUEST_ID, **overrides}


def test_create_uses_signed_location_context_and_bounded_draft_function():
    connection = _Connection()

    def set_context(conn, **kwargs):
        assert conn is connection
        conn.operations.append(("context", kwargs))

    def factory():
        return connection

    with patch.object(writes, "set_operator_tenant_context", set_context):
        result = writes.create_location_business_model_canvas(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(
                canvas_name="  Genesis model  ",
                description="  Draft only  ",
                fiscal_year=2026,
                tags=[" planning "],
                blocks={"value_propositions": [{"statement": "soil health"}]},
            ),
            connection_factory=factory,
        )

    context_index = next(
        index for index, operation in enumerate(connection.operations)
        if operation[0] == "context"
    )
    function_index = next(
        index for index, operation in enumerate(connection.operations)
        if operation[0] == "execute"
        and "kokonut_security.create_location_business_model_canvas" in operation[1]
    )
    assert connection.operations[context_index] == (
        "context",
        {
            "operator_id": OPERATOR_ID,
            "location_id": LOCATION_ID,
            "resource": "business_planning",
            "action": "create",
        },
    )
    assert connection.operations[context_index - 1][0] == "execute"
    assert context_index < function_index
    sql_call = connection.operations[function_index]
    assert "kokonut_security.create_location_business_model_canvas" in sql_call[1]
    assert sql_call[2][2:6] == ("Genesis model", "Draft only", 2026, ["planning"])
    assert '"value_propositions":[{"statement":"soil health"}]' in sql_call[2][6]
    assert '"key_partners":[]' in sql_call[2][6]
    assert result["status"] == "draft"
    assert result["replayed"] is False
    assert connection.commits == 1
    assert connection.closed


def test_from_data_reads_suggestions_after_signed_context_on_same_connection():
    connection = _Connection()

    def set_context(conn, **kwargs):
        assert conn is connection
        conn.operations.append(("context", kwargs))

    def suggest(conn, location_id):
        assert conn is connection
        assert location_id == LOCATION_ID
        conn.operations.append(("suggest", location_id))
        return {
            "blocks": {
                "key_partners": [{"name": "Genesis Cooperative"}],
                "value_propositions": [{"type": "soil health"}],
            },
            "generated_from": ["location_cooperative/supply_agreement"],
        }

    with patch.object(writes, "set_operator_tenant_context", set_context):
        result = writes.create_location_business_model_canvas_from_data(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(description="Suggested from current location records"),
            connection_factory=lambda: connection,
            suggestion_factory=suggest,
        )

    context_index = next(i for i, operation in enumerate(connection.operations) if operation[0] == "context")
    suggest_index = next(i for i, operation in enumerate(connection.operations) if operation[0] == "suggest")
    create_index = next(
        i for i, operation in enumerate(connection.operations)
        if operation[0] == "execute" and "create_location_business_model_canvas" in operation[1]
    )
    assert context_index < suggest_index < create_index
    assert result["status"] == "draft"
    assert result["generated_from"] == ["location_cooperative/supply_agreement"]
    assert result["populated_blocks"] == ["key_partners", "value_propositions"]
    create_call = connection.operations[create_index]
    assert create_call[2][2] == "Primary Canvas (auto)"
    assert create_call[2][4] is None
    assert create_call[2][5] == [
        "auto-generated",
        "suggested-from:location_cooperative/supply_agreement",
    ]
    assert '"Genesis Cooperative"' in create_call[2][6]
    assert connection.commits == 1
    assert connection.closed


def test_from_data_rejects_caller_blocks_before_opening_database():
    def forbidden_factory():
        raise AssertionError("caller-composed blocks must not enter generated mode")

    with pytest.raises(writes.BusinessPlanningWriteInvalid, match="cannot be supplied"):
        writes.create_location_business_model_canvas_from_data(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(blocks={"key_partners": [{"name": "caller supplied"}]}),
            connection_factory=forbidden_factory,
        )


def test_from_data_reserves_source_tags_before_opening_database():
    def forbidden_factory():
        raise AssertionError("tag capacity must be validated before suggestion reads")

    with pytest.raises(writes.BusinessPlanningWriteInvalid, match="at most 10 base tags"):
        writes.create_location_business_model_canvas_from_data(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(tags=[f"caller-{index}" for index in range(11)]),
            connection_factory=forbidden_factory,
        )


def test_from_data_suggestion_failure_rolls_back_and_closes_connection():
    connection = _Connection()

    def fail_suggestion(_connection, _location_id):
        raise RuntimeError("synthetic suggestion failure")

    with patch.object(writes, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="synthetic suggestion failure"):
            writes.create_location_business_model_canvas_from_data(
                OPERATOR_ID,
                LOCATION_ID,
                _payload(),
                connection_factory=lambda: connection,
                suggestion_factory=fail_suggestion,
            )

    assert connection.commits == 0
    assert connection.rollbacks >= 1
    assert connection.closed


@pytest.mark.parametrize(
    "payload",
    [
        {},
        _payload(unexpected="field"),
        _payload(fiscal_year=True),
        _payload(tags=["duplicate", " duplicate "]),
        _payload(blocks={"unknown": []}),
        _payload(blocks={"key_partners": {"not": "an array"}}),
        _payload(blocks={"cost_structure": []}),
        _payload(blocks={"key_partners": [float("nan")]}),
        _payload(blocks={"key_partners": [{1: "not a JSON object key"}]}),
        _payload(blocks={"key_partners": ["hidden\x00value"]}),
        _payload(canvas_name="invalid\x00name"),
    ],
)
def test_invalid_draft_payload_fails_before_opening_database(payload):
    def forbidden_factory():
        raise AssertionError("invalid payload must fail before opening a connection")

    with pytest.raises(writes.BusinessPlanningWriteInvalid):
        writes.create_location_business_model_canvas(
            OPERATOR_ID,
            LOCATION_ID,
            payload,
            connection_factory=forbidden_factory,
        )


def test_database_function_failure_rolls_back_and_closes():
    connection = _Connection()

    class FailingCursor(_Cursor):
        def execute(self, query, parameters=None):
            if "create_location_business_model_canvas" in query:
                raise RuntimeError("synthetic failure")
            super().execute(query, parameters)

    connection.cursor = lambda: FailingCursor(connection)
    with patch.object(writes, "set_operator_tenant_context"):
        with pytest.raises(RuntimeError, match="synthetic failure"):
            writes.create_location_business_model_canvas(
                OPERATOR_ID, LOCATION_ID, _payload(), connection_factory=lambda: connection
            )

    assert connection.commits == 0
    assert connection.rollbacks >= 1
    assert connection.closed


@pytest.mark.parametrize(("replayed", "expected_status"), [(False, 201), (True, 200)])
def test_post_route_returns_created_or_replayed_status_and_no_store(
    monkeypatch, replayed, expected_status
):
    from services.gateway.business_planning_routes import register_business_planning_routes

    monkeypatch.setattr(
        "services.gateway.business_planning_writes.create_location_business_model_canvas",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID,
            "canvas_id": REQUEST_ID,
            "status": "draft",
            "version": 1,
            "created_at": "2026-10-19T00:00:00Z",
            "replayed": replayed,
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases",
            json=_payload(canvas_name="Genesis"),
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["status"] == "draft"


@pytest.mark.parametrize(("replayed", "expected_status"), [(False, 201), (True, 200)])
def test_from_data_post_route_returns_created_or_replayed_status_and_no_store(
    monkeypatch, replayed, expected_status
):
    from services.gateway.business_planning_routes import register_business_planning_routes

    monkeypatch.setattr(
        "services.gateway.business_planning_writes.create_location_business_model_canvas_from_data",
        lambda *_args, **_kwargs: {
            "location_id": LOCATION_ID,
            "canvas_id": REQUEST_ID,
            "status": "draft",
            "version": 1,
            "created_at": "2026-10-19T00:00:00Z",
            "replayed": replayed,
            "generated_from": ["verified_farm_activity"],
            "populated_blocks": ["key_activities"],
        },
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases/from-data",
            json=_payload(description="Create a suggested draft"),
        )

    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["generated_from"] == ["verified_farm_activity"]


def test_post_route_rejects_non_object_json_without_calling_writer(monkeypatch):
    from services.gateway.business_planning_routes import register_business_planning_routes

    def forbidden_writer(*_args, **_kwargs):
        raise AssertionError("non-object payload must fail before the writer")

    monkeypatch.setattr(
        "services.gateway.business_planning_writes.create_location_business_model_canvas",
        forbidden_writer,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases",
            json=["a", "JSON", "array"],
        )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_post_route_maps_exact_create_denial_to_forbidden(monkeypatch):
    from services.gateway.business_planning_routes import register_business_planning_routes

    class DatabaseError(Exception):
        pgcode = "42501"

    def denied_writer(*_args, **_kwargs):
        raise DatabaseError("synthetic scope denial")

    monkeypatch.setattr(
        "services.gateway.business_planning_writes.create_location_business_model_canvas",
        denied_writer,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_business_planning_routes(router, object(), run_in_threadpool, SimpleNamespace(Error=DatabaseError))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/business-planning/{LOCATION_ID}/canvases",
            json=_payload(),
        )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
