"""Signed, location-scoped environmental-baseline capture contracts."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import environmental_baseline_writes as writes  # noqa: E402
from services.gateway.environmental_baseline_contracts import (  # noqa: E402
    EnvironmentalBaselineCaptureRequest,
)
from services.gateway.operator_auth import auth_route_policy  # noqa: E402
from services.migration import runtime_role  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OPERATOR_ID = "11111111-1111-4111-8111-111111111111"
LOCATION_ID = "22222222-2222-4222-8222-222222222222"
PLOT_ID = "33333333-3333-4333-8333-333333333333"
BASELINE_ID = "44444444-4444-4444-8444-444444444444"


class Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return (self.connection.result,)


class Connection:
    autocommit = False

    def __init__(self, result):
        self.result = result
        self.operations = []
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


def _payload(**changes):
    result = {
        "request_id": str(uuid4()),
        "plot_id": PLOT_ID,
        "metric_name": "soil_carbon_tonnes_per_ha",
        "baseline_value": 24.97,
        "unit": "tonnes/ha",
        "measurement_date": "2026-10-31",
        "measurement_method": "lab_analysis",
        "source": "soil_carbon_measurement",
        "evidence_urls": ["https://evidence.example/soil-report"],
        "notes": "Synthetic baseline capture",
    }
    result.update(changes)
    return result


def _receipt(payload=None, *, replayed=False):
    payload = payload or _payload()
    return {
        "baseline_id": BASELINE_ID,
        "location_id": LOCATION_ID,
        "plot_id": payload["plot_id"],
        "metric_name": payload["metric_name"],
        "baseline_value": payload["baseline_value"],
        "unit": payload["unit"],
        "measurement_date": payload["measurement_date"],
        "measurement_method": payload["measurement_method"],
        "source": payload["source"],
        "status": "recorded",
        "replayed": replayed,
    }


def test_capture_uses_signed_context_and_bounded_rpc_on_one_transaction(monkeypatch):
    payload = _payload(metric_name=" SOIL_CARBON_TONNES_PER_HA ")
    receipt = _receipt(payload)
    receipt["metric_name"] = "soil_carbon_tonnes_per_ha"
    connection = Connection(receipt)
    context_calls = []
    monkeypatch.setattr(
        writes,
        "set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )

    result = writes.capture_location_environmental_baseline(
        OPERATOR_ID, LOCATION_ID, payload, connection_factory=lambda: connection
    )

    assert context_calls == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "environmental_baseline",
                "action": "create",
            },
        )
    ]
    assert len(connection.operations) == 3
    query, params = connection.operations[-1]
    assert "capture_location_environmental_baseline" in query
    assert params == (
        LOCATION_ID,
        payload["request_id"],
        PLOT_ID,
        "soil_carbon_tonnes_per_ha",
        Decimal("24.97"),
        "tonnes/ha",
        date(2026, 10, 31),
        "lab_analysis",
        "soil_carbon_measurement",
        payload["evidence_urls"],
        payload["notes"],
    )
    assert result["status"] == "recorded"
    assert result["baseline_value"] == Decimal("24.97")
    assert result["replayed"] is False
    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert connection.closed


@pytest.mark.parametrize(
    "changes",
    [
        {"metric_name": "not-a-metric"},
        {"baseline_value": True},
        {"baseline_value": 100000000},
        {"baseline_value": 1.23456},
        {"measurement_date": "2026-02-30"},
        {"measurement_method": "\ninvalid"},
        {"evidence_urls": ["file:///private/data"]},
        {"evidence_urls": ["https://user:pass@example.invalid/private"]},
        {"evidence_urls": ["https://evidence.example/" + "x" * 2048]},
        {"unknown": "field"},
    ],
)
def test_capture_contract_rejects_invalid_fields_before_database_access(changes):
    payload = _payload(**changes)
    with pytest.raises((ValueError, TypeError)):
        EnvironmentalBaselineCaptureRequest.model_validate(payload)


def test_capture_writer_rolls_back_if_database_receipt_is_misbound(monkeypatch):
    connection = Connection(_receipt())
    monkeypatch.setattr(writes, "set_operator_tenant_context", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="does not match the request"):
        writes.capture_location_environmental_baseline(
            OPERATOR_ID,
            LOCATION_ID,
            _payload(baseline_value=999),
            connection_factory=lambda: connection,
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.closed


def test_environmental_baseline_route_has_explicit_private_create_policy():
    path = f"/operator/api/environmental-baselines/{LOCATION_ID}/captures"
    assert auth_route_policy("POST", path, enabled=True) == {
        "resource": "environmental_baseline",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", path, enabled=True) is None
    assert auth_route_policy("POST", path, enabled=False) is None
    assert auth_route_policy("POST", path + "/extra", enabled=True) is None


def test_registered_capture_route_validates_and_returns_recorded_receipt(monkeypatch):
    from services.gateway.environmental_baseline_routes import (
        register_environmental_baseline_routes,
    )

    payload = _payload()
    result = _receipt(payload)
    app = FastAPI()
    router = APIRouter()

    async def dispatch(_function, *_args, **_kwargs):
        return result

    register_environmental_baseline_routes(
        router, object(), dispatch, SimpleNamespace(Error=RuntimeError)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.post(
            f"/operator/api/environmental-baselines/{LOCATION_ID}/captures",
            json=payload,
        )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["baseline_id"] == BASELINE_ID
    assert response.json()["status"] == "recorded"
    assert response.json()["replayed"] is False


def test_migration_is_transactional_and_runtime_reprovisioning_keeps_the_dml_denial():
    migration = (ROOT / "schemas/postgres/733_environmental_baseline_gateway_capture.sql").read_text()
    seed = (ROOT / "schemas/seeds/009_pilot_carbon_biodiversity.sql").read_text()
    services = list((ROOT / "services").rglob("*.py"))
    direct_writers = []
    for source in services:
        text = source.read_text(encoding="utf-8")
        if re.search(r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?environmental_baseline\b", text, re.I):
            direct_writers.append(source.relative_to(ROOT).as_posix())

    assert migration.count("BEGIN;") == 1
    assert migration.count("COMMIT;") == 1
    assert "kokonut_security.current_tenant_context()" in migration
    assert "'environmental_baseline',\n        'create'" in migration
    assert "environmental_baseline_capture_owner_insert" in migration
    assert "environmental_baseline_capture_receipt" in migration
    assert "pg_advisory_xact_lock" in migration
    assert "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER" in migration
    assert "FROM kokonut_runtime" in migration
    assert "kokonut_directus_runtime" not in migration
    assert "INSERT INTO environmental_baseline" in seed
    assert direct_writers == []
    assert "environmental_baseline" in runtime_role._RUNTIME_MUTATION_TABLES
