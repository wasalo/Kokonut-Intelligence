"""Scoped pollinator-habitat detail and lifecycle contracts."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import pollinator_health_reads, pollinator_health_writes
from services.gateway.pollinator_health_writes import PollinatorObservationInvalid

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"
_HABITAT = "33333333-3333-4333-8333-333333333333"
_UPDATED_AT = "2026-10-25T12:34:56.123456+00:00"


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "update_location_pollinator_habitat" in query:
            self.connection.one = (self.connection.result,)
        elif "FROM public.pollinator_habitat" in query:
            self.description = [
                ("id",), ("habitat_name",), ("habitat_type",), ("area_m2",),
                ("condition",), ("status",), ("last_maintenance",), ("updated_at",),
            ]

    def fetchone(self):
        return self.connection.one

    def fetchall(self):
        return self.connection.rows


class Connection:
    def __init__(self, *, result=None, rows=()):
        self.result = result
        self.one = None
        self.rows = rows
        self.queries = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return Cursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def update_payload(**changes):
    return {
        "request_id": str(uuid4()),
        "expected_updated_at": _UPDATED_AT,
        "reason": "Routine habitat maintenance completed",
        **changes,
    }


def test_habitat_update_sets_exact_edit_context_and_commits(monkeypatch):
    connection = Connection(result={
        "event_id": str(uuid4()),
        "location_id": _LOCATION,
        "habitat_id": _HABITAT,
        "status": "degraded",
        "condition": "fair",
        "last_maintenance": "2026-10-24",
        "updated_at": _UPDATED_AT,
        "replayed": False,
    })
    context = {}
    monkeypatch.setattr(pollinator_health_writes, "set_operator_tenant_context", lambda *_a, **kw: context.update(kw))

    result = pollinator_health_writes.update_location_pollinator_habitat(
        _OPERATOR,
        _LOCATION,
        _HABITAT,
        update_payload(status="degraded", condition="fair", last_maintenance="2026-10-24"),
        connection_factory=lambda: connection,
    )

    assert context == {
        "operator_id": _OPERATOR,
        "location_id": _LOCATION,
        "resource": "pollinator_health",
        "action": "edit",
    }
    assert result["status"] == "degraded"
    assert result["replayed"] is False
    assert connection.queries[-1][0].startswith("SELECT kokonut_security.update_location_pollinator_habitat(")
    assert connection.queries[-1][1][3] == datetime(2026, 10, 25, 12, 34, 56, 123456, tzinfo=timezone.utc)
    assert connection.commits == 1 and connection.rollbacks == 0 and connection.closed


@pytest.mark.parametrize("changes", [
    {},
    {"status": "published"},
    {"status": None},
    {"condition": "unknown"},
    {"last_maintenance": "2026-02-30"},
    {"last_maintenance": (date.today() + timedelta(days=1)).isoformat()},
    {"status": {"invalid": True}},
    {"unexpected": True},
])
def test_habitat_update_rejects_malformed_input_before_connecting(monkeypatch, changes):
    connect_calls = []
    monkeypatch.setattr(
        pollinator_health_writes,
        "_connection_factory",
        lambda: lambda: connect_calls.append(True),
    )
    with pytest.raises(PollinatorObservationInvalid):
        pollinator_health_writes.update_location_pollinator_habitat(
            _OPERATOR,
            _LOCATION,
            _HABITAT,
            update_payload(**changes),
        )
    assert connect_calls == []


def test_habitat_update_rejects_timezone_naive_expected_timestamp():
    payload = update_payload(status="inactive")
    payload["expected_updated_at"] = "2026-10-25T12:34:56"
    with pytest.raises(PollinatorObservationInvalid, match="include a timezone"):
        pollinator_health_writes._normalize_habitat_lifecycle_payload(payload)


def test_habitat_update_rolls_back_database_error(monkeypatch):
    class FailingCursor(Cursor):
        def execute(self, query, params=None):
            raise RuntimeError("synthetic database error")

    class FailingConnection(Connection):
        def cursor(self):
            return FailingCursor(self)

    connection = FailingConnection()
    monkeypatch.setattr(pollinator_health_writes, "set_operator_tenant_context", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="synthetic database error"):
        pollinator_health_writes.update_location_pollinator_habitat(
            _OPERATOR,
            _LOCATION,
            _HABITAT,
            update_payload(status="inactive"),
            connection_factory=lambda: connection,
        )
    assert connection.commits == 0 and connection.rollbacks == 1 and connection.closed


def test_habitat_detail_read_sets_separate_context_and_limits_fields(monkeypatch):
    updated_at = datetime(2026, 10, 25, 12, 34, tzinfo=timezone.utc)
    connection = Connection(rows=[(
        _HABITAT, "North buffer", "hedgerow", 123.5, "good", "active", date(2026, 10, 20), updated_at
    )])
    context = {}
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **kw: context.update(kw))

    result = pollinator_health_reads.get_location_pollinator_habitat_details(
        _OPERATOR,
        _LOCATION,
        limit=10,
        offset=0,
        connection_factory=lambda: connection,
    )

    assert context == {
        "operator_id": _OPERATOR,
        "location_id": _LOCATION,
        "resource": "pollinator_health",
        "action": "read_detail",
    }
    assert result["habitats"] == [{
        "id": _HABITAT,
        "habitat_name": "North buffer",
        "habitat_type": "hedgerow",
        "area_m2": 123.5,
        "condition": "good",
        "status": "active",
        "last_maintenance": "2026-10-20",
        "updated_at": updated_at.isoformat(),
    }]
    assert "plant_species" not in result["habitats"][0]
    assert connection.queries[-1][1] == (_LOCATION, 11, 0)
    assert connection.rollbacks == 1 and connection.closed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (1, -1), (1, 10001), (True, 0)])
def test_habitat_detail_page_bounds_fail_before_database(limit, offset):
    with pytest.raises(ValueError):
        pollinator_health_reads.get_location_pollinator_habitat_details(
            _OPERATOR, _LOCATION, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must not connect"),
        )


def _route_test_client(monkeypatch, *, details, update):
    import psycopg2

    from services.gateway import pollinator_health_routes

    monkeypatch.setattr(pollinator_health_reads, "get_location_pollinator_habitat_details", details)
    monkeypatch.setattr(pollinator_health_writes, "update_location_pollinator_habitat", update)
    app = FastAPI()

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    router = APIRouter()
    pollinator_health_routes.register_pollinator_health_routes(
        router, provider=object(), run_in_threadpool=run_in_threadpool, psycopg2=psycopg2
    )
    app.include_router(router)
    return TestClient(app)


def test_habitat_detail_route_returns_private_no_store_page(monkeypatch):
    called = {}

    def details(operator_id, location_id, *, limit, offset):
        called.update(operator_id=operator_id, location_id=location_id, limit=limit, offset=offset)
        return {"location_id": location_id, "limit": limit, "offset": offset, "habitats": [], "has_more": False, "next_offset": None}

    client = _route_test_client(monkeypatch, details=details, update=lambda *_a, **_kw: {})
    response = client.get(f"/operator/api/pollinators/{_LOCATION}/habitats?limit=5&offset=10")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert called == {"operator_id": _OPERATOR, "location_id": _LOCATION, "limit": 5, "offset": 10}
    assert response.json()["habitats"] == []


def test_habitat_update_route_maps_stale_conflict(monkeypatch):
    import psycopg2

    class SyntheticStaleUpdate(psycopg2.Error):
        @property
        def pgcode(self):
            return "40001"

    def update(*_args, **_kwargs):
        raise SyntheticStaleUpdate("stale update")

    client = _route_test_client(monkeypatch, details=lambda *_a, **_kw: {}, update=update)
    response = client.patch(
        f"/operator/api/pollinators/{_LOCATION}/habitats/{_HABITAT}",
        json=update_payload(status="inactive"),
    )

    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert "changed" in response.json()["error"]
