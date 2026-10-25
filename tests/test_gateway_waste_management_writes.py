"""Focused tests for bounded, idempotent waste-stream Gateway capture."""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import waste_management_writes as writes

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.row = connection.row or ({
            "record_id": "33333333-3333-4333-8333-333333333333",
            "location_id": _LOCATION,
            "status": "recorded",
            "record_date": date.today().isoformat(),
            "replayed": False,
        },)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.connection.operations.append((query, params))

    def fetchone(self):
        return self.row


class Connection:
    def __init__(self):
        self.operations = []
        self.rollbacks = 0
        self.closed = False
        self.row = None

    def cursor(self):
        return Cursor(self)

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "waste_type": "crop_residue",
        "waste_name": "Banana stems",
        "quantity_kg": "12.50",
        "record_date": date.today().isoformat(),
        "disposal_method": "composting",
        "notes": "Field log",
    }
    payload.update(changes)
    return payload


def _compost_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "compost_date": date.today().isoformat(),
        "feedstock_type": "crop_residue",
        "feedstock_kg": "100.00",
        "compost_method": "vermiculture",
        "temperature_c": "55.0",
        "moisture_pct": "60.0",
        "duration_days": 30,
        "output_kg": "45.00",
        "ph": "6.50",
        "notes": "Synthetic batch",
    }
    payload.update(changes)
    return payload


def _recycling_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "record_date": date.today().isoformat(),
        "material_type": "plastic",
        "quantity_kg": "8.00",
        "destination": "Recycling center",
        "revenue": "12.50",
        "notes": "Synthetic recycling entry",
    }
    payload.update(changes)
    return payload


def test_capture_sets_exact_signed_create_context_before_call_and_closes_connection(monkeypatch):
    connection = Connection()
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _payload()

    result = writes.create_location_waste_stream_record(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "waste_management",
            "action": "create",
        },
    )]
    assert "create_location_waste_stream_record" in connection.operations[0][0]
    params = connection.operations[0][1]
    assert params[0] == _LOCATION
    assert params[1] == payload["request_id"]
    assert params[2] == "crop_residue"
    assert params[3:] == (
        "Banana stems", Decimal("12.50"), date.today(), "composting", "Field log"
    )
    assert result["status"] == "recorded"
    assert connection.rollbacks == 1
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"waste_type": "chemical"},
        {"waste_name": "   "},
        {"waste_name": "x" * 201},
        {"waste_name": "bad\nname"},
        {"quantity_kg": True},
        {"quantity_kg": "NaN"},
        {"quantity_kg": "0"},
        {"quantity_kg": "0.001"},
        {"quantity_kg": "100000000"},
        {"record_date": "not-a-date"},
        {"record_date": (date.today() + timedelta(days=1)).isoformat()},
        {"disposal_method": "incineration"},
        {"notes": "x" * 1001},
        {"notes": "line\nbreak"},
        {"unexpected": "field"},
    ],
)
def test_invalid_capture_fails_before_database_access(changes):
    def unexpected_connection():
        raise AssertionError("invalid waste input opened a database connection")

    with pytest.raises(writes.WasteManagementWriteInvalid):
        writes.create_location_waste_stream_record(
            _OPERATOR, _LOCATION, _payload(**changes), connection_factory=unexpected_connection
        )


@pytest.mark.parametrize("field", ["operator", "location", "request_id"])
def test_invalid_identifiers_fail_before_database_access(field):
    def unexpected_connection():
        raise AssertionError("invalid identifier opened a database connection")

    operator_id = "invalid" if field == "operator" else _OPERATOR
    location_id = "invalid" if field == "location" else _LOCATION
    payload = _payload(request_id="invalid" if field == "request_id" else str(uuid4()))
    with pytest.raises(writes.WasteManagementWriteInvalid):
        writes.create_location_waste_stream_record(
            operator_id, location_id, payload, connection_factory=unexpected_connection
        )


def test_capture_rolls_back_and_closes_on_database_failure(monkeypatch):
    class BrokenCursor(Cursor):
        def execute(self, _query, _params):
            raise RuntimeError("synthetic database failure")

    class BrokenConnection(Connection):
        def cursor(self):
            return BrokenCursor(self)

    connection = BrokenConnection()
    monkeypatch.setattr(writes, "set_operator_tenant_context", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="synthetic database failure"):
        writes.create_location_waste_stream_record(
            _OPERATOR, _LOCATION, _payload(), connection_factory=lambda: connection
        )
    assert connection.rollbacks == 2
    assert connection.closed


def test_capture_accepts_fractional_trailing_zeroes_as_schema_precision(monkeypatch):
    connection = Connection()
    monkeypatch.setattr(writes, "set_operator_tenant_context", lambda *_args, **_kwargs: None)
    writes.create_location_waste_stream_record(
        _OPERATOR,
        _LOCATION,
        _payload(quantity_kg="12.5000"),
        connection_factory=lambda: connection,
    )
    assert connection.operations[0][1][4] == Decimal("12.50")


def test_capture_rejects_non_object_payload_before_opening_database():
    def unexpected_connection():
        raise AssertionError("invalid waste input opened a database connection")

    with pytest.raises(writes.WasteManagementWriteInvalid):
        writes.create_location_waste_stream_record(
            _OPERATOR, _LOCATION, [], connection_factory=unexpected_connection
        )


def test_composting_capture_sets_signed_context_and_calls_bounded_function(monkeypatch):
    connection = Connection()
    connection.row = ({
        "record_id": "44444444-4444-4444-8444-444444444444",
        "location_id": _LOCATION,
        "compost_date": date.today().isoformat(),
        "status": "recorded",
        "replayed": False,
    },)
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _compost_payload()

    result = writes.create_location_composting_record(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "waste_management",
            "action": "create",
        },
    )]
    assert "create_location_composting_record" in connection.operations[0][0]
    assert connection.operations[0][1] == (
        _LOCATION,
        payload["request_id"],
        date.today(),
        "crop_residue",
        None,
        Decimal("100.00"),
        "vermiculture",
        None,
        Decimal("55.0"),
        Decimal("60.0"),
        30,
        Decimal("45.00"),
        Decimal("6.50"),
        "Synthetic batch",
    )
    assert result["status"] == "recorded"
    assert connection.rollbacks == 1
    assert connection.closed


def test_compost_capture_maps_and_preserves_legacy_freeform_labels(monkeypatch):
    connection = Connection()
    connection.row = ({
        "record_id": "44444444-4444-4444-8444-444444444444",
        "location_id": _LOCATION,
        "compost_date": date.today().isoformat(),
        "status": "recorded",
        "replayed": False,
    },)
    monkeypatch.setattr(writes, "set_operator_tenant_context", lambda *args, **kwargs: None)
    payload = _compost_payload(
        feedstock_type="Banana stems",
        compost_method="Vermicomposting",
    )

    writes.create_location_composting_record(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    params = connection.operations[0][1]
    assert params[3:8] == (
        "other", "Banana stems", Decimal("100.00"),
        "vermiculture", "Vermicomposting",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"feedstock_type": ""},
        {"feedstock_type": "x" * 201},
        {"feedstock_type": "invalid\nlabel"},
        {"feedstock_type": 42},
        {"compost_method": "x" * 101},
        {"compost_method": "invalid\nmethod"},
        {"compost_method": 42},
        {"feedstock_kg": True},
        {"feedstock_kg": "0"},
        {"feedstock_kg": "1.001"},
        {"compost_date": (date.today() + timedelta(days=1)).isoformat()},
        {"temperature_c": "200.1"},
        {"moisture_pct": "100.1"},
        {"duration_days": True},
        {"duration_days": -1},
        {"output_kg": "-0.01"},
        {"ph": "14.01"},
        {"notes": "bad\nnotes"},
        {"extra": "field"},
    ],
)
def test_invalid_composting_capture_fails_before_database_access(changes):
    def unexpected_connection():
        raise AssertionError("invalid composting input opened a database connection")

    with pytest.raises(writes.WasteManagementWriteInvalid):
        writes.create_location_composting_record(
            _OPERATOR, _LOCATION, _compost_payload(**changes),
            connection_factory=unexpected_connection,
        )


def test_recycling_capture_sets_exact_context_and_preserves_freeform_material(monkeypatch):
    connection = Connection()
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _recycling_payload(material_type="Steel scrap")

    result = writes.create_location_recycling_record(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "waste_management",
            "action": "create",
        },
    )]
    assert "create_location_recycling_record" in connection.operations[0][0]
    assert connection.operations[0][1] == (
        _LOCATION,
        payload["request_id"],
        date.today(),
        "other",
        "Steel scrap",
        Decimal("8.00"),
        "Recycling center",
        Decimal("12.50"),
        "Synthetic recycling entry",
    )
    assert result["status"] == "recorded"
    assert connection.rollbacks == 1
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"record_date": (date.today() + timedelta(days=1)).isoformat()},
        {"material_type": ""},
        {"material_type": "x" * 101},
        {"material_type": "steel\nscrap"},
        {"material_type": 3},
        {"quantity_kg": True},
        {"quantity_kg": "0"},
        {"quantity_kg": "1.001"},
        {"destination": ""},
        {"destination": "x" * 201},
        {"revenue": "100000000"},
        {"revenue": "1.001"},
        {"notes": "bad\nnotes"},
        {"extra": "field"},
    ],
)
def test_invalid_recycling_capture_fails_before_database_access(changes):
    def unexpected_connection():
        raise AssertionError("invalid recycling input opened a database connection")

    with pytest.raises(writes.WasteManagementWriteInvalid):
        writes.create_location_recycling_record(
            _OPERATOR, _LOCATION, _recycling_payload(**changes),
            connection_factory=unexpected_connection,
        )


def test_http_capture_is_location_scoped_created_and_no_store(monkeypatch):
    from services.gateway import waste_management_routes

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        writes,
        "create_location_waste_stream_record",
        lambda operator, location, payload: {
            "record_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location,
            "status": "recorded",
            "replayed": False,
        },
        raising=False,
    )
    app = FastAPI()
    router = APIRouter()
    waste_management_routes.register_waste_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/waste/{_LOCATION}/records",
        json=_payload(),
    )
    assert response.status_code == 201
    assert response.json()["location_id"] == _LOCATION
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_http_composting_capture_is_location_scoped_created_and_no_store(monkeypatch):
    from services.gateway import waste_management_routes

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        writes,
        "create_location_composting_record",
        lambda operator, location, payload: {
            "record_id": "44444444-4444-4444-8444-444444444444",
            "location_id": location,
            "compost_date": date.today().isoformat(),
            "status": "recorded",
            "replayed": False,
        },
        raising=False,
    )
    app = FastAPI()
    router = APIRouter()
    waste_management_routes.register_waste_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/waste/{_LOCATION}/composting",
        json=_compost_payload(),
    )
    assert response.status_code == 201
    assert response.json()["location_id"] == _LOCATION
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_http_recycling_capture_is_location_scoped_created_and_no_store(monkeypatch):
    from services.gateway import waste_management_routes

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(
        writes,
        "create_location_recycling_record",
        lambda operator, location, payload: {
            "record_id": "55555555-5555-4555-8555-555555555555",
            "location_id": location,
            "record_date": date.today().isoformat(),
            "status": "recorded",
            "replayed": False,
        },
        raising=False,
    )
    app = FastAPI()
    router = APIRouter()
    waste_management_routes.register_waste_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/waste/{_LOCATION}/recycling",
        json=_recycling_payload(),
    )
    assert response.status_code == 201
    assert response.json()["location_id"] == _LOCATION
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_http_capture_rejects_oversized_body_before_writer(monkeypatch):
    from services.gateway import waste_management_routes

    async def run_in_threadpool(*_args, **_kwargs):
        raise AssertionError("oversized body reached the writer")

    app = FastAPI()
    router = APIRouter()
    waste_management_routes.register_waste_management_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    response = TestClient(app).post(
        f"/operator/api/waste/{_LOCATION}/records",
        content=b" " * 4097,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
