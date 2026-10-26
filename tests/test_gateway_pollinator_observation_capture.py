"""Location-granted, recorded-only pollinator observation capture contract."""

import importlib
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import pollinator_health_writes as writes
from services.gateway.operator_auth import auth_route_policy

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"


class Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.connection.operations.append((query, params))

    def fetchone(self):
        return (self.connection.result,)


class Connection:
    def __init__(self):
        self.operations = []
        self.rollbacks = 0
        self.commits = 0
        self.closed = False
        self.result = {
            "observation_id": "33333333-3333-4333-8333-333333333333",
            "location_id": _LOCATION,
            "pollinator_type": "wild_bee",
            "count": 7,
            "observation_method": "transect",
            "observation_date": date.today().isoformat(),
            "duration_minutes": 20,
            "status": "recorded",
            "replayed": False,
        }

    def cursor(self):
        return Cursor(self)

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def _payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "pollinator_type": "wild_bee",
        "count": 7,
        "observation_method": "transect",
        "duration_minutes": 20,
        "plot_id": None,
        "observation_date": date.today().isoformat(),
        "species_name": "Native bee",
        "weather_conditions": {"description": "clear"},
        "temperature_c": "24.50",
        "hive_record_id": None,
        "notes": "Synthetic observation",
    }
    payload.update(changes)
    return payload


def _pesticide_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "application_date": date.today().isoformat(),
        "product_name": "Synthetic product",
        "active_ingredient": "Synthetic ingredient",
        "toxicity_class": "moderate",
        "application_rate": "1.25",
        "rate_unit": "L/ha",
        "area_treated_m2": "250.00",
        "bloom_stage_at_application": "flowering",
        "pollinator_distance_m": "20",
        "pollinator_safe_period_days": 3,
        "pollinator_mortality_observed": False,
        "mortality_pct": None,
        "notes": "Synthetic report",
    }
    payload.update(changes)
    return payload


def _habitat_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "habitat_name": "Synthetic native strip",
        "habitat_type": "wildflower_strip",
        "area_m2": "125.50",
        "plant_species": ["Native clover", "Buttonwood"],
        "bloom_start_month": 3,
        "bloom_end_month": 9,
        "water_source": True,
        "nesting_sites": "Undisturbed ground edge",
        "notes": "Synthetic habitat inventory",
    }
    payload.update(changes)
    return payload


def _hive_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "hive_id": "KOK-TEST-001",
        "hive_type": "langstroth",
        "colony_strength": "moderate",
        "colony_strength_score": None,
        "queen_status": "present",
        "frame_count": 10,
        "queen_year": 2024,
        "notes": "Synthetic managed-hive inventory",
    }
    payload.update(changes)
    return payload


def _inspection_payload(**changes):
    payload = {
        "request_id": str(uuid4()),
        "hive_id": "KOK-TEST-001",
        "inspection_date": date.today().isoformat(),
        "colony_strength": "moderate",
        "colony_strength_score": None,
        "queen_status": "present",
        "queen_seen": True,
        "varroa_count": 25,
        "brood_pattern": "solid",
        "honey_stores": "medium",
        "disease_signs": None,
        "temperament": "calm",
        "population_estimate": 15000,
        "swarm_cells": False,
        "notes": "Synthetic inspection observations",
    }
    payload.update(changes)
    return payload


def test_observation_sets_signed_create_context_before_function_and_cleans_connection(monkeypatch):
    connection = Connection()
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _payload()

    result = writes.create_location_pollinator_observation(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "pollinator_health",
            "action": "create",
        },
    )]
    query, params = connection.operations[0]
    assert "create_location_pollinator_observation" in query
    assert params[:5] == (
        _LOCATION, payload["request_id"], "wild_bee", 7, "transect"
    )
    assert params[5:9] == (
        20, None, date.today(), "Native bee"
    )
    assert params[9] == '{"description": "clear"}'
    assert str(params[10]) == "24.50"
    assert params[11:] == (None, "Synthetic observation")
    assert result["status"] == "recorded"
    assert result["replayed"] is False
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_pesticide_report_sets_create_context_and_commits_recorded_result(monkeypatch):
    connection = Connection()
    connection.result = {
        "record_id": "33333333-3333-4333-8333-333333333333",
        "location_id": _LOCATION,
        "toxicity_class": "moderate",
        "application_date": date.today().isoformat(),
        "status": "recorded",
        "replayed": False,
    }
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )

    payload = _pesticide_payload()
    result = writes.create_location_pesticide_impact(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "pollinator_health",
            "action": "create",
        },
    )]
    query, params = connection.operations[0]
    assert "create_location_pesticide_impact" in query
    assert params[:6] == (
        _LOCATION, payload["request_id"], date.today(),
        "Synthetic product", "Synthetic ingredient", "moderate",
    )
    assert str(params[6]) == "1.25"
    assert params[7:12] == ("L/ha", 250, "flowering", 20, 3)
    assert params[12:] == (False, None, "Synthetic report")
    assert result["status"] == "recorded"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_habitat_capture_sets_create_context_and_commits_self_reported_inventory(monkeypatch):
    connection = Connection()
    connection.result = {
        "habitat_id": "33333333-3333-4333-8333-333333333333",
        "location_id": _LOCATION,
        "habitat_type": "wildflower_strip",
        "area_m2": 125.5,
        "status": "active",
        "replayed": False,
    }
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _habitat_payload()

    result = writes.create_location_pollinator_habitat(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "pollinator_health",
            "action": "create",
        },
    )]
    query, params = connection.operations[0]
    assert "create_location_pollinator_habitat" in query
    assert params == (
        _LOCATION, payload["request_id"], "Synthetic native strip", "wildflower_strip",
        Decimal("125.50"), '["Native clover", "Buttonwood"]', 3, 9, True,
        "Undisturbed ground edge", "Synthetic habitat inventory",
    )
    assert result["status"] == "active"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_hive_capture_sets_create_context_and_commits_active_inventory(monkeypatch):
    connection = Connection()
    connection.result = {
        "hive_record_id": "33333333-3333-4333-8333-333333333333",
        "location_id": _LOCATION,
        "hive_id": "KOK-TEST-001",
        "hive_type": "langstroth",
        "colony_strength": "moderate",
        "colony_strength_score": None,
        "queen_status": "present",
        "frame_count": 10,
        "status": "active",
        "replayed": False,
    }
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _hive_payload()

    result = writes.create_location_pollinator_hive(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "pollinator_health",
            "action": "create",
        },
    )]
    query, params = connection.operations[0]
    assert "create_location_pollinator_hive" in query
    assert params == (
        _LOCATION, payload["request_id"], "KOK-TEST-001", "langstroth",
        "moderate", None, "present", 10, 2024, "Synthetic managed-hive inventory",
    )
    assert result["status"] == "active"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


def test_hive_inspection_sets_create_context_and_commits_recorded_only_result(monkeypatch):
    connection = Connection()
    connection.result = {
        "inspection_id": "33333333-3333-4333-8333-333333333333",
        "location_id": _LOCATION,
        "status": "recorded",
        "replayed": False,
    }
    contexts = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    )
    payload = _inspection_payload()

    result = writes.record_location_pollinator_hive_inspection(
        _OPERATOR, _LOCATION, payload, connection_factory=lambda: connection
    )

    assert contexts == [(
        connection,
        {
            "operator_id": _OPERATOR,
            "location_id": _LOCATION,
            "resource": "pollinator_health",
            "action": "create",
        },
    )]
    query, params = connection.operations[0]
    assert "record_location_pollinator_hive_inspection" in query
    assert params == (
        _LOCATION, payload["request_id"], "KOK-TEST-001", date.today(),
        "moderate", None, "present", True, 25, "solid", "medium", None,
        "calm", 15000, False, "Synthetic inspection observations",
    )
    assert result["status"] == "recorded"
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"application_date": (date.today().replace(day=1)).isoformat() + "T00:00:00"},
        {"application_date": "2999-01-01"},
        {"toxicity_class": "unknown"},
        {"toxicity_class": []},
        {"application_rate": "NaN"},
        {"application_rate": "-0.1"},
        {"rate_unit": "L/ha" , "application_rate": None},
        {"pollinator_safe_period_days": True},
        {"pollinator_mortality_observed": "false"},
        {"mortality_pct": "100.01"},
        {"notes": "bad\nnote"},
        {"unexpected": "field"},
    ],
)
def test_invalid_pesticide_report_is_rejected_before_database_access(changes):
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid):
        writes.create_location_pesticide_impact(
            _OPERATOR,
            _LOCATION,
            _pesticide_payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "changes",
    [
        {"habitat_name": "  "},
        {"habitat_type": "citrus_orchard"},
        {"area_m2": "NaN"},
        {"area_m2": "100000000"},
        {"plant_species": ["x" * 101]},
        {"plant_species": ["bee balm", 1]},
        {"plant_species": ["clover"] * 51},
        {"bloom_start_month": True},
        {"bloom_end_month": 13},
        {"water_source": "yes"},
        {"nesting_sites": "bad\nnote"},
        {"unexpected": "field"},
    ],
)
def test_invalid_habitat_report_is_rejected_before_database_access(changes):
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid):
        writes.create_location_pollinator_habitat(
            _OPERATOR,
            _LOCATION,
            _habitat_payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "changes",
    [
        {"hive_id": " "},
        {"hive_id": "bad\nidentifier"},
        {"hive_type": "x" * 51},
        {"colony_strength": "excellent"},
        {"colony_strength_score": 11},
        {"colony_strength_score": True},
        {"colony_strength": None},
        {"colony_strength_score": 5},
        {"queen_status": "healthy"},
        {"frame_count": 501},
        {"frame_count": True},
        {"queen_year": date.today().year + 1},
        {"notes": "bad\nnote"},
        {"unexpected": "field"},
    ],
)
def test_invalid_hive_capture_is_rejected_before_database_access(changes):
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid):
        writes.create_location_pollinator_hive(
            _OPERATOR,
            _LOCATION,
            _hive_payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "changes",
    [
        {"hive_id": " "},
        {"inspection_date": "2999-01-01"},
        {"inspection_date": "2026-02-30"},
        {"colony_strength": "excellent"},
        {"colony_strength_score": 11},
        {"colony_strength": "strong", "colony_strength_score": 5},
        {"queen_status": "healthy"},
        {"queen_seen": "yes"},
        {"varroa_count": 100001},
        {"brood_pattern": "x" * 101},
        {"honey_stores": "x" * 501},
        {"disease_signs": "x" * 2001},
        {"temperament": "bad\ntext"},
        {"population_estimate": 100000001},
        {"swarm_cells": 0},
        {"notes": "bad\nnote"},
        {"unexpected": "field"},
    ],
)
def test_invalid_hive_inspection_is_rejected_before_database_access(changes):
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid):
        writes.record_location_pollinator_hive_inspection(
            _OPERATOR,
            _LOCATION,
            _inspection_payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


def test_empty_hive_inspection_is_rejected_before_database_access():
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid, match="At least one inspection observation"):
        writes.record_location_pollinator_hive_inspection(
            _OPERATOR,
            _LOCATION,
            _inspection_payload(
                colony_strength=None,
                queen_status=None,
                queen_seen=None,
                varroa_count=None,
                brood_pattern=None,
                honey_stores=None,
                disease_signs=None,
                temperament=None,
                population_estimate=None,
                swarm_cells=False,
                notes=None,
            ),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "changes",
    [
        {"pollinator_type": "bumblebee"},
        {"observation_method": "directus"},
        {"count": True},
        {"count": -1},
        {"duration_minutes": 1.5},
        {"observation_date": "2026-02-30"},
        {"species_name": "x" * 201},
        {"weather_conditions": ["unexpected"]},
        {"temperature_c": "NaN"},
        {"temperature_c": 101},
        {"notes": "bad\nnote"},
        {"unexpected": "field"},
    ],
)
def test_invalid_capture_is_rejected_before_database_access(changes):
    opened = []
    with pytest.raises(writes.PollinatorObservationInvalid):
        writes.create_location_pollinator_observation(
            _OPERATOR,
            _LOCATION,
            _payload(**changes),
            connection_factory=lambda: opened.append(True),
        )
    assert opened == []


@pytest.mark.parametrize(
    "path,method,action",
    [
        ("/operator/api/pollinators/{}/summary", "GET", "read"),
        ("/operator/api/pollinators/{}/observations", "POST", "create"),
        ("/operator/api/pollinators/{}/pesticide-impacts", "POST", "create"),
        ("/operator/api/pollinators/{}/habitats", "POST", "create"),
        ("/operator/api/pollinators/{}/hives", "POST", "create"),
        ("/operator/api/pollinators/{}/hives/inspections", "POST", "create"),
    ],
)
def test_pollinator_routes_have_exact_location_grants(path, method, action):
    location_id = str(uuid4())
    assert auth_route_policy(method, path.format(location_id), enabled=True) == {
        "resource": "pollinator_health",
        "action": action,
        "public": False,
        "location_id": location_id,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("DELETE", path.format(location_id), enabled=True) is None


def test_http_capture_is_bounded_csrf_ready_and_no_store(monkeypatch):
    routes = importlib.import_module("services.gateway.pollinator_health_routes")
    posted = []

    def create(operator_id, location_id, payload):
        posted.append((operator_id, location_id, payload))
        return {
            "observation_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location_id,
            "pollinator_type": payload["pollinator_type"],
            "count": payload["count"],
            "observation_method": payload["observation_method"],
            "observation_date": payload["observation_date"],
            "duration_minutes": payload["duration_minutes"],
            "status": "recorded",
            "replayed": False,
        }

    monkeypatch.setattr(writes, "create_location_pollinator_observation", create)
    router = APIRouter()

    async def run_inline(function, *args):
        return function(*args)

    import psycopg2

    routes.register_pollinator_health_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/pollinators/{_LOCATION}/observations",
            json=_payload(),
            headers={"X-CSRF-Token": "synthetic"},
        )
        assert response.status_code == 201
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["vary"] == "Cookie"
        assert posted[0][0:2] == (_OPERATOR, _LOCATION)

        oversized = client.post(
            f"/operator/api/pollinators/{_LOCATION}/observations",
            content=b" " * (12 * 1024 + 1),
        )
        assert oversized.status_code == 413
        assert len(posted) == 1


def test_pesticide_report_http_capture_is_create_gated_recorded_and_no_store(monkeypatch):
    routes = importlib.import_module("services.gateway.pollinator_health_routes")
    posted = []

    def create(operator_id, location_id, payload):
        posted.append((operator_id, location_id, payload))
        return {
            "record_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location_id,
            "toxicity_class": payload["toxicity_class"],
            "application_date": payload["application_date"],
            "status": "recorded",
            "replayed": False,
        }

    monkeypatch.setattr(writes, "create_location_pesticide_impact", create)
    router = APIRouter()

    async def run_inline(function, *args):
        return function(*args)

    import psycopg2

    routes.register_pollinator_health_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/pollinators/{_LOCATION}/pesticide-impacts",
            json=_pesticide_payload(),
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert posted[0][0:2] == (_OPERATOR, _LOCATION)


def test_habitat_http_capture_is_create_gated_self_reported_and_no_store(monkeypatch):
    routes = importlib.import_module("services.gateway.pollinator_health_routes")
    posted = []

    def create(operator_id, location_id, payload):
        posted.append((operator_id, location_id, payload))
        return {
            "habitat_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location_id,
            "habitat_type": payload["habitat_type"],
            "area_m2": payload["area_m2"],
            "status": "active",
            "replayed": False,
        }

    monkeypatch.setattr(writes, "create_location_pollinator_habitat", create)
    router = APIRouter()

    async def run_inline(function, *args):
        return function(*args)

    import psycopg2

    routes.register_pollinator_health_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/pollinators/{_LOCATION}/habitats",
            json=_habitat_payload(),
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert posted[0][0:2] == (_OPERATOR, _LOCATION)


def test_hive_http_capture_is_create_gated_and_no_store(monkeypatch):
    routes = importlib.import_module("services.gateway.pollinator_health_routes")
    posted = []

    def create(operator_id, location_id, payload):
        posted.append((operator_id, location_id, payload))
        return {
            "hive_record_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location_id,
            "hive_id": payload["hive_id"],
            "hive_type": payload["hive_type"],
            "queen_status": payload["queen_status"],
            "frame_count": payload["frame_count"],
            "status": "active",
            "replayed": False,
        }

    monkeypatch.setattr(writes, "create_location_pollinator_hive", create)
    router = APIRouter()

    async def run_inline(function, *args):
        return function(*args)

    import psycopg2

    routes.register_pollinator_health_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/pollinators/{_LOCATION}/hives",
            json=_hive_payload(),
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert posted[0][0:2] == (_OPERATOR, _LOCATION)


def test_hive_inspection_http_capture_is_create_gated_recorded_and_no_store(monkeypatch):
    routes = importlib.import_module("services.gateway.pollinator_health_routes")
    posted = []

    def create(operator_id, location_id, payload):
        posted.append((operator_id, location_id, payload))
        return {
            "inspection_id": "33333333-3333-4333-8333-333333333333",
            "location_id": location_id,
            "status": "recorded",
            "replayed": False,
        }

    monkeypatch.setattr(writes, "record_location_pollinator_hive_inspection", create)
    router = APIRouter()

    async def run_inline(function, *args):
        return function(*args)

    import psycopg2

    routes.register_pollinator_health_routes(router, object(), run_inline, psycopg2)
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=_OPERATOR)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/pollinators/{_LOCATION}/hives/inspections",
            json=_inspection_payload(),
        )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert posted[0][0:2] == (_OPERATOR, _LOCATION)


def test_legacy_pollinator_observation_cli_fails_before_database_access(monkeypatch):
    cli = importlib.import_module("services.analytics.cli_pollinator_health").cli
    command = next(item for item in cli._commands if item.name == "record-observation")
    assert command.needs_db is False
    monkeypatch.setattr(
        cli,
        "_connection_factory",
        lambda: pytest.fail("retired observation writer must not open the database"),
    )
    with pytest.raises(RuntimeError, match="Unscoped pollinator observation writes are retired"):
        cli.main([
            "record-observation", "--location-id", _LOCATION, "--type", "wild_bee", "--count", "1",
        ])


def test_legacy_pesticide_cli_fails_before_database_access(monkeypatch):
    cli = importlib.import_module("services.analytics.cli_pollinator_health").cli
    command = next(item for item in cli._commands if item.name == "record-pesticide")
    assert command.needs_db is False
    monkeypatch.setattr(
        cli,
        "_connection_factory",
        lambda: pytest.fail("retired pesticide writer must not open the database"),
    )
    with pytest.raises(RuntimeError, match="Unscoped pesticide-impact writes are retired"):
        cli.main([
            "record-pesticide", "--location-id", _LOCATION, "--date", date.today().isoformat(),
            "--product", "synthetic", "--ingredient", "synthetic", "--toxicity", "moderate",
        ])


def test_legacy_habitat_cli_fails_before_database_access(monkeypatch):
    cli = importlib.import_module("services.analytics.cli_pollinator_health").cli
    command = next(item for item in cli._commands if item.name == "create-habitat")
    assert command.needs_db is False
    monkeypatch.setattr(
        cli,
        "_connection_factory",
        lambda: pytest.fail("retired habitat writer must not open the database"),
    )
    with pytest.raises(RuntimeError, match="Unscoped pollinator habitat writes are retired"):
        cli.main([
            "create-habitat", "--location-id", _LOCATION, "--name", "Synthetic",
            "--type", "wildflower_strip", "--area", "10",
        ])


def test_legacy_hive_cli_fails_before_database_access(monkeypatch):
    cli = importlib.import_module("services.analytics.cli_pollinator_health").cli
    command = next(item for item in cli._commands if item.name == "add-hive")
    assert command.needs_db is False
    monkeypatch.setattr(
        cli,
        "_connection_factory",
        lambda: pytest.fail("retired hive writer must not open the database"),
    )
    with pytest.raises(RuntimeError, match="Unscoped managed-hive writes are retired"):
        cli.main([
            "add-hive", "--location-id", _LOCATION, "--hive-id", "KOK-TEST-001",
        ])


def test_legacy_hive_inspection_cli_fails_before_database_access(monkeypatch):
    cli = importlib.import_module("services.analytics.cli_pollinator_health").cli
    command = next(item for item in cli._commands if item.name == "record-inspection")
    assert command.needs_db is False
    monkeypatch.setattr(
        cli,
        "_connection_factory",
        lambda: pytest.fail("retired hive inspection writer must not open the database"),
    )
    with pytest.raises(RuntimeError, match="Unscoped hive inspection writes are retired"):
        cli.main([
            "record-inspection", "--location-id", _LOCATION, "--hive-id", "KOK-TEST-001",
        ])
