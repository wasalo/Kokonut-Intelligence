"""Focused tests for scoped resolution of approved farmer identities."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import stakeholder_identity_resolution as resolution

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PROFILE_ID = str(uuid4())
PARTY_ID = str(uuid4())
RESOLVED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


class _Connection:
    def __init__(self, row=None):
        self.row = row
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

    def fetchone(self):
        return self.connection.row


def test_resolution_sets_separate_signed_action_before_bounded_function():
    conn = _Connection((PARTY_ID, RESOLVED_AT))
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)
        connection.events.append("SIGNED_CONTEXT")

    with patch.object(resolution, "set_operator_tenant_context", set_context):
        result = resolution.resolve_location_farmer_party_identity(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            connection_factory=lambda: conn,
        )

    call_index = next(
        index for index, (query, _params) in enumerate(conn.operations)
        if "resolve_location_farmer_party_identity" in query
    )
    assert conn.events.index("SIGNED_CONTEXT") < next(
        index for index, event in enumerate(conn.events)
        if "resolve_location_farmer_party_identity" in event
    )
    assert conn.operations[call_index][1] == (LOCATION_ID, PROFILE_ID)
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "stakeholder_identity",
        "action": "resolve",
    }]
    assert result == {"party_id": PARTY_ID, "resolved_at": RESOLVED_AT}
    assert conn.rolled_back and conn.closed
    assert not any("READ ONLY" in query for query, _params in conn.operations)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operator_id", "invalid"),
        ("location_id", "invalid"),
        ("source_profile_id", "invalid"),
    ],
)
def test_invalid_resolution_identifier_fails_before_connection(field, value):
    values = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "source_profile_id": PROFILE_ID,
    }
    values[field] = value
    with pytest.raises(resolution.StakeholderIdentityResolutionInvalid):
        resolution.resolve_location_farmer_party_identity(
            **values,
            connection_factory=lambda: pytest.fail("invalid request opened a database connection"),
        )


def test_missing_currently_resolvable_mapping_returns_none():
    conn = _Connection(None)
    with patch.object(resolution, "set_operator_tenant_context"):
        result = resolution.resolve_location_farmer_party_identity(
            OPERATOR_ID,
            LOCATION_ID,
            PROFILE_ID,
            connection_factory=lambda: conn,
        )
    assert result is None
    assert conn.rolled_back and conn.closed


def test_resolution_route_returns_only_location_and_canonical_party():
    from services.gateway.stakeholder_identity_resolution_routes import (
        register_stakeholder_identity_resolution_routes,
    )

    app = FastAPI()
    psycopg2 = SimpleNamespace(Error=type("PgError", (Exception,), {}))

    @app.middleware("http")
    async def attach_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    async def run_inline(_function, *_args, **_kwargs):
        return {"party_id": PARTY_ID, "resolved_at": RESOLVED_AT}

    register_stakeholder_identity_resolution_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        psycopg2,
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/resolve/{PROFILE_ID}"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "location_id": LOCATION_ID,
        "party_id": PARTY_ID,
        "resolved_at": RESOLVED_AT.isoformat(),
    }
    assert PROFILE_ID not in response.text


def test_resolution_route_publishes_strict_openapi_success_contract():
    from services.gateway.stakeholder_identity_resolution_routes import (
        register_stakeholder_identity_resolution_routes,
    )

    app = FastAPI()
    psycopg2 = SimpleNamespace(Error=type("PgError", (Exception,), {}))
    register_stakeholder_identity_resolution_routes(
        app.router,
        SimpleNamespace(),
        lambda *_args, **_kwargs: None,
        psycopg2,
    )

    operation = app.openapi()["paths"][
        "/operator/api/stakeholder-identity/{location_id}/resolve/{source_profile_id}"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/StakeholderIdentityResolutionResponse"
    }
    schema = app.openapi()["components"]["schemas"][
        "StakeholderIdentityResolutionResponse"
    ]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"location_id", "party_id", "resolved_at"}


@pytest.mark.parametrize(
    "invalid_result",
    [
        {
            "party_id": PARTY_ID,
            "resolved_at": RESOLVED_AT,
            "private_internal_field": "must not escape",
        },
        {"party_id": "invalid", "resolved_at": RESOLVED_AT},
        {"party_id": PARTY_ID, "resolved_at": datetime(2026, 10, 19, 12, 0)},
    ],
)
def test_resolution_route_sanitizes_invalid_success_projection(invalid_result):
    from services.gateway.stakeholder_identity_resolution_routes import (
        register_stakeholder_identity_resolution_routes,
    )

    app = FastAPI()
    psycopg2 = SimpleNamespace(Error=type("PgError", (Exception,), {}))

    @app.middleware("http")
    async def attach_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    async def run_inline(_function, *_args, **_kwargs):
        return invalid_result

    register_stakeholder_identity_resolution_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        psycopg2,
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/resolve/{PROFILE_ID}"
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": "Stakeholder identity resolution unavailable"
    }
    assert response.headers["cache-control"] == "no-store"
    assert PROFILE_ID not in response.text
    assert "must not escape" not in response.text


def test_resolution_route_hides_unavailable_mapping_as_not_found():
    from services.gateway.stakeholder_identity_resolution_routes import (
        register_stakeholder_identity_resolution_routes,
    )

    app = FastAPI()
    psycopg2 = SimpleNamespace(Error=type("PgError", (Exception,), {}))

    @app.middleware("http")
    async def attach_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    async def run_inline(_function, *_args, **_kwargs):
        return None

    register_stakeholder_identity_resolution_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        psycopg2,
    )
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-identity/{LOCATION_ID}/resolve/{PROFILE_ID}"
        )

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert "profile_id" not in response.json()
