"""Bounded participant workspace, private answer, and browser-route contracts."""

from decimal import Decimal
from uuid import uuid4

import pytest

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from services.gateway import delphi_participant_workspace as workspace  # noqa: E402

SESSION = "11" * 32
CSRF = "22" * 32
ITEM = "33333333-3333-4333-8333-333333333333"
REQUEST = str(uuid4())


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


def test_workspace_calls_only_bounded_function_and_closes_connection():
    expected = {
        "study": {"study_id": str(uuid4()), "title": "Water resilience", "status": "open"},
        "items": [],
        "has_more": False,
        "limit": 20,
        "offset": 40,
    }
    connection = _Connection((expected,))
    result = workspace.get_location_delphi_participant_workspace(
        SESSION, limit="20", offset="40", connection_factory=lambda: connection
    )
    query, params = connection.calls[-1]
    assert "get_location_delphi_participant_workspace" in query
    assert params == (SESSION, 20, 40)
    assert result == expected
    assert connection.committed and connection.rolled_back and connection.closed


def test_contribution_normalizes_decimal_and_calls_only_bounded_function():
    contribution_id = str(uuid4())
    connection = _Connection(("submitted", ITEM, contribution_id, "2026-10-25T12:00:00Z", False))
    result = workspace.submit_location_delphi_participant_contribution(
        SESSION,
        CSRF,
        ITEM,
        "0.6250",
        "A private participant explanation",
        REQUEST,
        connection_factory=lambda: connection,
    )
    query, params = connection.calls[-1]
    assert "submit_location_delphi_participant_contribution" in query
    assert params == (SESSION, CSRF, ITEM, Decimal("0.6250"), "A private participant explanation", REQUEST)
    assert result["contribution_id"] == contribution_id
    assert result["replayed"] is False
    assert connection.committed and connection.closed


@pytest.mark.parametrize(
    ("method", "values"),
    [
        ("workspace", {"limit": 0}),
        ("workspace", {"offset": "1.5"}),
        ("contribution", {"score": True}),
        ("contribution", {"score": "NaN"}),
        ("contribution", {"score": "1.00001"}),
        ("contribution", {"score": "10000"}),
        ("contribution", {"item_id": "not-a-uuid"}),
        ("contribution", {"reasoning": "x" * 4001}),
    ],
)
def test_invalid_workspace_or_answer_fails_before_database(method, values):
    def factory():
        pytest.fail("invalid Delphi participant request opened a connection")

    with pytest.raises(workspace.DelphiParticipantWorkspaceInvalid):
        if method == "workspace":
            workspace.get_location_delphi_participant_workspace(
                SESSION,
                limit=values.get("limit", 50),
                offset=values.get("offset", 0),
                connection_factory=factory,
            )
        else:
            workspace.submit_location_delphi_participant_contribution(
                SESSION,
                CSRF,
                values.get("item_id", ITEM),
                values.get("score", 0.5),
                values.get("reasoning", None),
                REQUEST,
                connection_factory=factory,
            )


def _app(run_in_threadpool):
    from services.gateway.delphi_participant_routes import register_delphi_participant_routes

    app = FastAPI()
    router = APIRouter()
    register_delphi_participant_routes(router, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router, prefix="/api")
    return app


def test_participant_assets_are_private_same_origin_and_self_hosted():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("static participant page unexpectedly used the database")

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    page = client.get("/api/participation/delphi")
    script = client.get("/api/participation/delphi/app.js")
    styles = client.get("/api/participation/delphi/styles.css")
    assert page.status_code == script.status_code == styles.status_code == 200
    assert page.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in page.headers["content-security-policy"]
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert "./app.js" in page.text and "./styles.css" in page.text
    assert "localStorage" not in script.text
    assert "innerHTML" not in script.text
    assert "credentials: \"same-origin\"" in script.text


def test_workspace_route_requires_session_and_returns_no_store_payload():
    calls = []
    expected = {"study": {"title": "Water resilience", "status": "draft"}, "items": []}

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    denied = client.get("/api/participation/delphi/workspace")
    assert denied.status_code == 401 and calls == []
    client.cookies.set(
        "kokonut_delphi_participant_session", SESSION, path="/api/participation/delphi"
    )
    response = client.get("/api/participation/delphi/workspace?limit=20&offset=40")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert calls[0][1] == (SESSION,)
    assert calls[0][2] == {"limit": "20", "offset": "40"}


@pytest.mark.parametrize("csrf_header", [None, "33" * 32])
def test_contribution_route_requires_double_submit_csrf(csrf_header):
    calls = []

    async def run_in_threadpool(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "submitted", "replayed": False}

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    client.cookies.set("kokonut_delphi_participant_session", SESSION,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF,
                       path="/api/participation/delphi")
    headers = {} if csrf_header is None else {"X-Kokonut-CSRF": csrf_header}
    response = client.post(
        "/api/participation/delphi/contributions",
        headers=headers,
        json={"item_id": ITEM, "score": 0.5, "reasoning": None, "request_id": REQUEST},
    )
    assert response.status_code == 403
    assert calls == []


def test_contribution_route_forwards_only_valid_fields_and_supports_retry_status():
    calls = []

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return {
            "status": "submitted",
            "item_id": ITEM,
            "contribution_id": str(uuid4()),
            "updated_at": "2026-10-25T12:00:00Z",
            "replayed": len(calls) > 1,
        }

    client = TestClient(_app(run_in_threadpool), base_url="https://testserver")
    client.cookies.set("kokonut_delphi_participant_session", SESSION,
                       path="/api/participation/delphi")
    client.cookies.set("kokonut_delphi_participant_csrf", CSRF,
                       path="/api/participation/delphi")
    payload = {"item_id": ITEM, "score": 0.5, "reasoning": "private", "request_id": REQUEST}
    response = client.post(
        "/api/participation/delphi/contributions",
        headers={"X-Kokonut-CSRF": CSRF},
        json=payload,
    )
    replay = client.post(
        "/api/participation/delphi/contributions",
        headers={"X-Kokonut-CSRF": CSRF},
        json=payload,
    )
    assert response.status_code == 201 and replay.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert SESSION not in response.text and CSRF not in response.text
    assert calls[0][0] is workspace.submit_location_delphi_participant_contribution
    assert calls[0][1] == (SESSION, CSRF, ITEM, 0.5, "private", REQUEST)
    assert calls[0][2] == {}
