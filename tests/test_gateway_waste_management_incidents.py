"""Focused contract tests for tenant-scoped pollution incident operations."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import waste_management_incidents as incidents
from services.gateway import waste_management_routes

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"
_INCIDENT = "33333333-3333-4333-8333-333333333333"


class Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((query, params))

    def fetchone(self):
        return self.connection.row

    def fetchall(self):
        return self.connection.rows


class Connection:
    def __init__(self, row=None, rows=None):
        self.row = row or ({
            "incident_id": _INCIDENT,
            "location_id": _LOCATION,
            "incident_date": date.today().isoformat(),
            "resolution_date": date.today().isoformat(),
            "status": "open",
            "replayed": False,
        },)
        self.rows = rows or []
        self.operations = []
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return Cursor(self)

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def _capture_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "incident_date": date.today().isoformat(),
        "incident_type": "air_pollution",
        "severity": "high",
        "description": "Synthetic plume report\nSecond line",
        "affected_area": "North plot",
        "reported_by": "Field reporter",
        "notes": "Synthetic test",
    }
    payload.update(changes)
    return payload


def _resolution_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "resolution_date": date.today().isoformat(),
        "remedial_action": "Synthetic cleanup",
    }
    payload.update(changes)
    return payload


def test_capture_sets_exact_create_context_and_preserves_legacy_type(monkeypatch):
    connection = Connection()
    contexts = []
    monkeypatch.setattr(
        incidents,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = incidents.create_location_pollution_incident(
        _OPERATOR, _LOCATION, _capture_payload(), connection_factory=lambda: connection
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
    assert "create_location_pollution_incident" in connection.operations[0][0]
    assert connection.operations[0][1][3:6] == ("air_emission", "air_pollution", "high")
    assert connection.operations[0][1][5] == "high"
    assert result["status"] == "open"
    assert connection.rollbacks == 1
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"incident_date": (date.today() + timedelta(days=1)).isoformat()},
        {"incident_type": ""},
        {"incident_type": "x" * 101},
        {"severity": "urgent"},
        {"description": ""},
        {"description": "x" * 2501},
        {"affected_area": "x" * 201},
        {"reported_by": "x" * 201},
        {"notes": "x" * 1001},
        {"notes": "bad\x01note"},
        {"unknown": "field"},
    ],
)
def test_invalid_capture_fails_before_database_access(changes):
    def unexpected_connection():
        raise AssertionError("invalid report opened PostgreSQL")

    with pytest.raises(incidents.PollutionIncidentInvalid):
        incidents.create_location_pollution_incident(
            _OPERATOR, _LOCATION, _capture_payload(**changes),
            connection_factory=unexpected_connection,
        )


def test_review_queue_uses_exact_review_context_and_returns_bounded_projection(monkeypatch):
    connection = Connection(rows=[(
        _INCIDENT, date.today().isoformat(), "air_emission", "high",
        "Synthetic report", "North plot", "open",
    )])
    contexts = []
    monkeypatch.setattr(
        incidents,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = incidents.list_location_pollution_incidents(
        _OPERATOR, _LOCATION, connection_factory=lambda: connection
    )

    assert contexts[-1][1]["action"] == "review"
    assert "WHERE location_id = %s::uuid" in connection.operations[-1][0]
    assert "LIMIT 101 OFFSET %s" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (_LOCATION, 0)
    assert result["incidents"][0]["incident_id"] == _INCIDENT
    assert "reported_by" not in result["incidents"][0]
    assert result["has_more"] is False
    assert result["offset"] == 0
    assert connection.closed


def test_resolve_uses_separate_review_grant_and_validates_location(monkeypatch):
    connection = Connection(row=({
        "incident_id": _INCIDENT,
        "location_id": _LOCATION,
        "resolution_date": date.today().isoformat(),
        "status": "resolved",
        "replayed": False,
    },))
    contexts = []
    monkeypatch.setattr(
        incidents,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    result = incidents.resolve_location_pollution_incident(
        _OPERATOR, _LOCATION, _INCIDENT, _resolution_payload(),
        connection_factory=lambda: connection,
    )

    assert contexts[0][1]["action"] == "review"
    assert "resolve_location_pollution_incident" in connection.operations[0][0]
    assert connection.operations[0][1][0:2] == (_LOCATION, _INCIDENT)
    assert connection.operations[0][1][3:] == (date.today(), "Synthetic cleanup")
    assert result["status"] == "resolved"
    assert connection.closed


def test_invalid_resolution_fails_before_database_access():
    def unexpected_connection():
        raise AssertionError("invalid resolution opened PostgreSQL")

    with pytest.raises(incidents.PollutionIncidentInvalid):
        incidents.resolve_location_pollution_incident(
            _OPERATOR, _LOCATION, _INCIDENT,
            _resolution_payload(remedial_action=""),
            connection_factory=unexpected_connection,
        )


@pytest.mark.parametrize("offset", [-1, True, 1.5, 1_000_001])
def test_invalid_review_queue_offset_fails_before_database_access(offset):
    def unexpected_connection():
        raise AssertionError("invalid review offset opened PostgreSQL")

    with pytest.raises(incidents.PollutionIncidentInvalid):
        incidents.list_location_pollution_incidents(
            _OPERATOR, _LOCATION, offset=offset,
            connection_factory=unexpected_connection,
        )


def _app(monkeypatch):
    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

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

    return TestClient(app)


def test_http_incident_capture_is_no_store_and_returns_open_only(monkeypatch):
    monkeypatch.setattr(
        incidents,
        "create_location_pollution_incident",
        lambda operator, location, payload: {
            "incident_id": _INCIDENT,
            "location_id": location,
            "status": "open",
            "replayed": False,
        },
    )
    response = _app(monkeypatch).post(
        f"/operator/api/waste/{_LOCATION}/incidents",
        json=_capture_payload(),
    )
    assert response.status_code == 201
    assert response.json() == {
        "incident_id": _INCIDENT,
        "location_id": _LOCATION,
        "status": "open",
        "replayed": False,
    }
    assert response.headers["cache-control"] == "no-store"


def test_http_incident_review_and_resolution_routes(monkeypatch):
    monkeypatch.setattr(
        incidents,
        "list_location_pollution_incidents",
        lambda operator, location, offset=0: {
            "location_id": location, "offset": offset, "incidents": [], "has_more": False,
        },
    )
    monkeypatch.setattr(
        incidents,
        "resolve_location_pollution_incident",
        lambda operator, location, incident, payload: {
            "incident_id": incident,
            "location_id": location,
            "status": "resolved",
            "replayed": False,
        },
    )
    client = _app(monkeypatch)
    queue = client.get(f"/operator/api/waste/{_LOCATION}/incidents")
    resolved = client.post(
        f"/operator/api/waste/{_LOCATION}/incidents/{_INCIDENT}/resolve",
        json=_resolution_payload(),
    )
    assert queue.status_code == 200
    assert queue.json()["location_id"] == _LOCATION
    assert queue.headers["cache-control"] == "no-store"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.headers["cache-control"] == "no-store"
