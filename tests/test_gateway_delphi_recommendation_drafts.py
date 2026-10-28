"""Focused contracts for location-scoped Delphi facilitator draft creation."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_recommendation_drafts as drafts

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
STUDY_ID = str(uuid4())
REQUEST_ID = str(uuid4())
RECOMMENDATION_ID = str(uuid4())


class _Connection:
    def __init__(self, rows=(), one=None):
        self.rows = list(rows)
        self.one = one
        self.operations = []
        self.events = []
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
        normalized = " ".join(query.split())
        self.connection.operations.append((normalized, params))
        self.connection.events.append(normalized)

    def fetchall(self):
        return self.connection.rows

    def fetchone(self):
        return self.connection.one


def _set_context(connection, **kwargs):
    connection.events.append("SIGNED_CONTEXT")
    connection.context = kwargs


def test_study_listing_sets_signed_draft_scope_before_bounded_query_and_cleans_up():
    connection = _Connection(
        [
            (str(uuid4()), "Open study", "open", None),
            (str(uuid4()), "Closed study", "closed", None),
        ]
    )
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        result = drafts.list_location_delphi_draftable_studies(
            OPERATOR_ID,
            LOCATION_ID,
            limit=1,
            offset=7,
            connection_factory=lambda: connection,
        )

    query_index = next(
        index for index, event in enumerate(connection.events)
        if "list_location_delphi_draftable_studies" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < query_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "draft",
    }
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 7)
    assert len(result["studies"]) == 1 and result["has_more"] is True
    assert connection.rolled_back and connection.closed
    assert not connection.committed


@pytest.mark.parametrize(
    ("offset", "expected_has_more"),
    [(9980, True), (9990, False), (10000, False)],
)
def test_study_listing_only_advertises_pages_within_offset_ceiling(
    offset, expected_has_more
):
    connection = _Connection(
        [(str(uuid4()), f"Study {index}", "open", None) for index in range(21)]
    )
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        result = drafts.list_location_delphi_draftable_studies(
            OPERATOR_ID,
            LOCATION_ID,
            limit=20,
            offset=offset,
            connection_factory=lambda: connection,
        )

    assert len(result["studies"]) == 20
    assert result["has_more"] is expected_has_more
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("limit", 0),
        ("limit", 51),
        ("limit", "1.2"),
        ("limit", True),
        ("offset", -1),
        ("offset", 10001),
        ("offset", "1.2"),
        ("offset", False),
    ],
)
def test_invalid_study_list_request_fails_before_database(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "limit": 50,
        "offset": 0,
    }
    arguments[field] = value
    with pytest.raises(drafts.DelphiDraftInvalid):
        drafts.list_location_delphi_draftable_studies(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a connection"),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operator_id", "bad"),
        ("location_id", "bad"),
        ("study_id", "bad"),
        ("request_id", "bad"),
        ("recommendation_text", "  "),
        ("recommendation_text", "x" * 20001),
        ("summary", "x" * 4001),
        ("summary", 42),
    ],
)
def test_invalid_draft_request_fails_before_database(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "study_id": STUDY_ID,
        "request_id": REQUEST_ID,
        "recommendation_text": "A bounded draft recommendation.",
        "summary": None,
    }
    arguments[field] = value
    with pytest.raises(drafts.DelphiDraftInvalid):
        drafts.create_location_delphi_recommendation_draft(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a connection"),
        )


def test_draft_creation_uses_signed_scope_and_commits_only_after_function_returns():
    created_at = "2026-10-19T12:00:00+00:00"
    connection = _Connection(one=(RECOMMENDATION_ID, STUDY_ID, "draft", created_at))
    with patch.object(drafts, "set_operator_tenant_context", _set_context):
        result = drafts.create_location_delphi_recommendation_draft(
            OPERATOR_ID,
            LOCATION_ID,
            STUDY_ID,
            request_id=REQUEST_ID,
            recommendation_text="  Draft text  ",
            summary="  Draft summary  ",
            connection_factory=lambda: connection,
        )

    query_index = next(
        index for index, event in enumerate(connection.events)
        if "create_location_delphi_recommendation_draft" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < query_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "draft",
    }
    assert connection.operations[-1][1] == (
        LOCATION_ID,
        STUDY_ID,
        REQUEST_ID,
        "Draft summary",
        "Draft text",
    )
    assert result == {
        "recommendation_id": RECOMMENDATION_ID,
        "study_id": STUDY_ID,
        "status": "draft",
        "created_at": created_at,
    }
    assert connection.committed and connection.closed


def test_tenant_denial_rolls_back_without_calling_draft_function():
    connection = _Connection()
    with patch.object(
        drafts,
        "set_operator_tenant_context",
        side_effect=TenantContextDenied("missing draft grant"),
    ):
        with pytest.raises(TenantContextDenied):
            drafts.create_location_delphi_recommendation_draft(
                OPERATOR_ID,
                LOCATION_ID,
                STUDY_ID,
                request_id=REQUEST_ID,
                recommendation_text="Draft text",
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any(
        "create_location_delphi_recommendation_draft" in query
        for query, _params in connection.operations
    )


def _make_app(provider, run_in_threadpool, psycopg2_errors=None):
    from services.gateway.delphi_recommendation_draft_routes import (
        register_delphi_recommendation_draft_routes,
    )

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_recommendation_draft_routes(
        router,
        provider,
        run_in_threadpool,
        psycopg2_errors or __import__("psycopg2"),
    )
    app.include_router(router)
    return app


def test_draft_routes_are_no_store_and_forward_actor_location_and_paging():
    calls = []
    expected = {"location_id": LOCATION_ID, "studies": [], "offset": 60, "has_more": False}

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.get(
        f"/operator/api/delphi/{LOCATION_ID}/draft-studies?limit=30&offset=60"
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID)
    assert calls[0][2] == {"limit": 30, "offset": 60}


def test_draft_study_list_publishes_service_bounds_in_openapi():
    app = _make_app(object(), lambda *_args, **_kwargs: None)
    operation = app.openapi()["paths"][
        "/operator/api/delphi/{location_id}/draft-studies"
    ]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}

    assert parameters["limit"]["schema"]["default"] == 50
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["default"] == 0
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000
    assert operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/DelphiDraftStudyPage")


@pytest.mark.parametrize(
    "projection",
    [
        {"location_id": str(uuid4()), "studies": [], "offset": 0, "has_more": False},
        {"location_id": LOCATION_ID, "studies": [], "offset": 1, "has_more": False},
        {
            "location_id": LOCATION_ID,
            "studies": [
                {
                    "study_id": str(uuid4()),
                    "title": "Open study",
                    "status": "draft",
                    "updated_at": None,
                }
            ],
            "offset": 0,
            "has_more": False,
        },
        {
            "location_id": LOCATION_ID,
            "studies": [],
            "offset": 0,
            "has_more": True,
        },
        {
            "location_id": LOCATION_ID,
            "studies": [],
            "offset": 0,
            "has_more": False,
            "extra": "not in the source projection",
        },
    ],
)
def test_draft_study_list_rejects_invalid_or_unbound_service_projection(projection):
    async def run_in_threadpool(*_args, **_kwargs):
        return projection

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/draft-studies")

    assert response.status_code == 500
    assert response.json() == {"error": "Delphi draft-study list unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_draft_study_list_accepts_source_projection_and_binds_page_to_request():
    study_id = str(uuid4())
    expected = {
        "location_id": LOCATION_ID,
        "studies": [
            {
                "study_id": study_id,
                "title": "Open study",
                "status": "open",
                "updated_at": datetime(2026, 10, 28, 12, tzinfo=timezone.utc),
            }
        ],
        "offset": 10,
        "has_more": False,
    }

    async def run_in_threadpool(*_args, **_kwargs):
        return expected

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.get(
        f"/operator/api/delphi/{LOCATION_ID}/draft-studies?limit=20&offset=10"
    )

    expected["studies"][0]["updated_at"] = "2026-10-28T12:00:00Z"
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1", "offset=10001"])
def test_draft_study_list_rejects_out_of_bounds_before_service(query):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid page bounds must not invoke the draft-list service")

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.get(
        f"/operator/api/delphi/{LOCATION_ID}/draft-studies?{query}"
    )

    assert response.status_code == 422


def test_draft_route_requires_exact_json_fields_and_keeps_response_private():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke the draft service")

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/recommendation-drafts",
        json={
            "request_id": REQUEST_ID,
            "summary": None,
            "recommendation_text": "Draft text",
            "publish": True,
        },
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_draft_routes_fail_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    client = TestClient(_make_app(None, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/draft-studies")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_create_route_is_no_store_and_forwards_exact_draft_payload():
    calls = []
    expected = {
        "recommendation_id": RECOMMENDATION_ID,
        "study_id": STUDY_ID,
        "status": "draft",
        "created_at": "2026-10-19T12:00:00+00:00",
    }

    async def run_in_threadpool(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return expected

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/recommendation-drafts",
        json={
            "request_id": REQUEST_ID,
            "summary": "Facilitator summary",
            "recommendation_text": "Draft only",
        },
    )
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert calls[0][1] == (OPERATOR_ID, LOCATION_ID, STUDY_ID)
    assert calls[0][2] == {
        "request_id": REQUEST_ID,
        "summary": "Facilitator summary",
        "recommendation_text": "Draft only",
    }


def test_missing_draft_grant_fails_closed_without_database_response_details():
    async def run_in_threadpool(*_args, **_kwargs):
        raise TenantContextDenied("scope denied")

    client = TestClient(_make_app(object(), run_in_threadpool))
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/recommendation-drafts",
        json={
            "request_id": REQUEST_ID,
            "summary": None,
            "recommendation_text": "Draft only",
        },
    )
    assert response.status_code == 403
    assert "scope denied" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_ineligible_study_conflict_is_a_private_409_response():
    class _DatabaseConflict(Exception):
        pgcode = "55000"

    async def run_in_threadpool(*_args, **_kwargs):
        raise _DatabaseConflict("database detail must not be returned")

    client = TestClient(
        _make_app(object(), run_in_threadpool, SimpleNamespace(Error=_DatabaseConflict))
    )
    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/studies/{STUDY_ID}/recommendation-drafts",
        json={
            "request_id": REQUEST_ID,
            "summary": None,
            "recommendation_text": "Draft only",
        },
    )
    assert response.status_code == 409
    assert "database detail" not in response.text
    assert response.headers["cache-control"] == "no-store"
