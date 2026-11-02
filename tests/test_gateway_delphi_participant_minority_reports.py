"""Participant-only, explicitly consented Delphi minority-report submission."""

from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import delphi_participant_minority_reports as reports  # noqa: E402

SESSION = "11" * 32
CSRF = "22" * 32
ITEM = "33333333-3333-4333-8333-333333333333"
REQUEST = str(uuid4())
REPORT = str(uuid4())


class _Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []
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
        self.connection.calls.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.row


def test_submission_calls_only_bounded_function_and_returns_no_participant_identity():
    connection = _Connection(("submitted", REPORT, "2026-10-25T12:00:00Z", False))
    result = reports.submit_location_delphi_participant_minority_report(
        SESSION,
        CSRF,
        item_id=ITEM,
        title="  A different view  ",
        position_summary="  The position I want considered.  ",
        rationale="  My reasons are private to the review process.  ",
        implications="  It could change the order of work.  ",
        request_id=REQUEST,
        connection_factory=lambda: connection,
    )
    query, params = connection.calls[-1]
    assert "submit_location_delphi_participant_minority_report" in query
    assert params == (
        SESSION,
        CSRF,
        ITEM,
        "A different view",
        "The position I want considered.",
        "My reasons are private to the review process.",
        "It could change the order of work.",
        REQUEST,
    )
    assert result == {
        "status": "submitted",
        "report_id": REPORT,
        "submitted_at": "2026-10-25T12:00:00Z",
        "replayed": False,
    }
    assert "panel_member_id" not in result and "participant_id" not in result
    assert connection.committed and connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    "values",
    [
        {"session_token": "invalid"},
        {"csrf_token": SESSION},
        {"item_id": "not-a-uuid"},
        {"title": " "},
        {"title": "x" * 256},
        {"position_summary": " "},
        {"position_summary": "x" * 4001},
        {"rationale": " "},
        {"rationale": "x" * 8001},
        {"implications": "x" * 3001},
        {"implications": 5},
        {"request_id": "bad"},
    ],
)
def test_invalid_submission_fails_before_database(values):
    arguments = {
        "session_token": SESSION,
        "csrf_token": CSRF,
        "item_id": ITEM,
        "title": "A different view",
        "position_summary": "The position I want considered.",
        "rationale": "My reasons are private to the review process.",
        "implications": None,
        "request_id": REQUEST,
    }
    arguments.update(values)
    with pytest.raises(reports.DelphiParticipantMinorityReportInvalid):
        reports.submit_location_delphi_participant_minority_report(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid report opened a connection"),
        )


def _app(run_in_threadpool):
    from services.gateway.delphi_participant_routes import register_delphi_participant_routes

    app = FastAPI()
    router = APIRouter()
    register_delphi_participant_routes(router, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router, prefix="/api")
    return app


def _payload():
    return {
        "item_id": ITEM,
        "title": "A different view",
        "position_summary": "The position I want considered.",
        "rationale": "My reasons are private to the review process.",
        "implications": None,
        "request_id": REQUEST,
    }


def test_route_requires_session_csrf_and_exact_payload_before_database():
    calls = []

    async def run_in_threadpool(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "submitted", "report_id": REPORT, "submitted_at": None, "replayed": False}

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    denied = client.post("/api/participation/delphi/minority-reports", json=_payload())
    assert denied.status_code == 401 and calls == []

    client.cookies.set("kokonut_delphi_participant_session", SESSION,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF,
                       path="/api/participation/delphi")
    denied = client.post(
        "/api/participation/delphi/minority-reports",
        headers={"X-Kokonut-CSRF": "33" * 32},
        json=_payload(),
    )
    assert denied.status_code == 403 and calls == []
    malformed = {**_payload(), "evidence_refs": ["https://example.invalid"]}
    denied = client.post(
        "/api/participation/delphi/minority-reports",
        headers={"X-Kokonut-CSRF": CSRF},
        json=malformed,
    )
    assert denied.status_code == 400 and calls == []


def test_route_forwards_only_bounded_fields_and_returns_no_session_credentials():
    calls = []

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return {
            "status": "submitted",
            "report_id": REPORT,
            "submitted_at": "2026-10-25T12:00:00Z",
            "replayed": len(calls) > 1,
        }

    app = _app(run_in_threadpool)
    schema = app.openapi()["paths"]["/api/participation/delphi/minority-reports"]["post"][
        "responses"]["200"]["content"]["application/json"]["schema"]
    assert schema["$ref"].endswith("DelphiParticipantMinorityReportResponse")
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set("kokonut_delphi_participant_session", SESSION,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF,
                       path="/api/participation/delphi")
    response = client.post(
        "/api/participation/delphi/minority-reports",
        headers={"X-Kokonut-CSRF": CSRF},
        json=_payload(),
    )
    replay = client.post(
        "/api/participation/delphi/minority-reports",
        headers={"X-Kokonut-CSRF": CSRF},
        json=_payload(),
    )
    assert response.status_code == 201 and replay.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {"status", "report_id", "submitted_at", "replayed"}
    assert SESSION not in response.text and CSRF not in response.text
    assert calls[0][0] is reports.submit_location_delphi_participant_minority_report
    assert calls[0][1] == (SESSION, CSRF)
    assert calls[0][2] == {
        "item_id": ITEM,
        "title": "A different view",
        "position_summary": "The position I want considered.",
        "rationale": "My reasons are private to the review process.",
        "implications": None,
        "request_id": REQUEST,
    }


def test_malformed_minority_report_success_is_sanitized_and_not_cached():
    async def run_in_threadpool(*_args, **_kwargs):
        return {
            "status": "published",
            "report_id": REPORT,
            "submitted_at": "2026-10-25T12:00:00Z",
            "replayed": False,
            "private_participant_id": "participant-secret",
        }

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    client.cookies.set(
        "kokonut_delphi_participant_session", SESSION,
        path="/api/participation/delphi",
    )
    client.cookies.set(
        "kokonut_delphi_participant_csrf", CSRF,
        path="/api/participation/delphi",
    )
    response = client.post(
        "/api/participation/delphi/minority-reports",
        headers={"X-Kokonut-CSRF": CSRF},
        json=_payload(),
    )
    assert response.status_code == 503
    assert response.json() == {"error": "Delphi participant service unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert "participant-secret" not in response.text
