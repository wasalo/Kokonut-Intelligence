"""Focused contract tests for the location-scoped identity trust projection."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.gateway import stakeholder_trust as trust

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
PARTY_ID = str(uuid4())
EVIDENCE_ID = str(uuid4())
REVIEWED_AT = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)


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
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)
        if "list_location_party_identity_trust_evidence" in normalized:
            fields = (
                "evidence_id", "dimension", "direction", "evidence_code",
                "match_method", "confidence", "reviewed_at",
            )
            self.description = [SimpleNamespace(name=field) for field in fields]

    def fetchall(self):
        return self.connection.rows


def _row(evidence_id=EVIDENCE_ID):
    return (
        evidence_id,
        "identity",
        "supporting",
        "document_review",
        "verified_document",
        0.91,
        REVIEWED_AT,
    )


def test_trust_projection_sets_signed_scope_before_bounded_sql_and_cleans_up():
    conn = _Connection([_row(), _row(str(uuid4()))])
    contexts = []

    def set_context(connection, **kwargs):
        assert connection is conn
        contexts.append(kwargs)
        connection.events.append("SIGNED_CONTEXT")

    with patch.object(trust, "set_operator_tenant_context", set_context):
        result = trust.list_location_identity_trust_evidence(
            OPERATOR_ID,
            LOCATION_ID,
            PARTY_ID,
            limit=1,
            connection_factory=lambda: conn,
        )

    assert conn.operations[0][0] == "SET LOCAL statement_timeout = '8s'"
    assert not any(query == "SET TRANSACTION READ ONLY" for query, _params in conn.operations)
    query_index = next(
        index for index, (query, _params) in enumerate(conn.operations)
        if "list_location_party_identity_trust_evidence" in query
    )
    assert conn.events.index("SIGNED_CONTEXT") < next(
        index for index, event in enumerate(conn.events)
        if "list_location_party_identity_trust_evidence" in event
    )
    assert conn.operations[query_index][1] == (LOCATION_ID, PARTY_ID, 2, None, None)
    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "stakeholder_trust",
        "action": "read",
    }]
    assert result["location_id"] == LOCATION_ID
    assert result["party_id"] == PARTY_ID
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["dimension"] == "identity"
    assert result["next_cursor"] == {
        "reviewed_at": REVIEWED_AT.isoformat(),
        "evidence_id": EVIDENCE_ID,
    }
    assert conn.rolled_back and conn.closed


@pytest.mark.parametrize(
    "overrides",
    [
        {"location_id": "not-a-uuid"},
        {"party_id": "not-a-uuid"},
        {"limit": 51},
        {"limit": True},
        {"cursor_reviewed_at": "2026-10-19T11:00:00"},
        {"cursor_reviewed_at": REVIEWED_AT.isoformat()},
    ],
)
def test_invalid_trust_projection_input_fails_before_database(overrides):
    values = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "party_id": PARTY_ID,
    }
    values.update(overrides)
    with pytest.raises(trust.StakeholderTrustInvalid):
        trust.list_location_identity_trust_evidence(
            **values,
            connection_factory=lambda: pytest.fail("invalid input opened a database connection"),
        )


def test_trust_response_contract_contains_no_global_score_or_private_feedback():
    from services.gateway.stakeholder_trust_routes import register_stakeholder_trust_routes

    fake_pg_error = type("PgError", (Exception,), {})
    psycopg2 = SimpleNamespace(Error=fake_pg_error)
    app = FastAPI()

    @app.middleware("http")
    async def attach_operator_session(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    payload = {
        "location_id": LOCATION_ID,
        "party_id": PARTY_ID,
        "evidence": [{
            "evidence_id": EVIDENCE_ID,
            "dimension": "identity",
            "direction": "supporting",
            "evidence_code": "document_review",
            "match_method": "verified_document",
            "confidence": 0.91,
            "reviewed_at": REVIEWED_AT,
        }],
        "next_cursor": None,
    }
    async def run_inline(_function, *args, **kwargs):
        return payload

    register_stakeholder_trust_routes(
        app.router,
        SimpleNamespace(),
        run_inline,
        psycopg2,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/stakeholder-trust/{LOCATION_ID}/parties/{PARTY_ID}/identity-evidence"
        )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["evidence"][0]["evidence_code"] == "document_review"
    assert "score" not in body
    assert "summary" not in str(body).lower()
    assert "feedback" not in str(body).lower()
