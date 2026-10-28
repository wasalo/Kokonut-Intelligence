"""Contracts for private, location-scoped Delphi minority-report review."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import delphi_minority_review as review

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REPORT_ID = str(uuid4())
REQUEST_ID = str(uuid4())


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


def test_queue_sets_signed_location_context_before_query_and_omits_identity():
    row = (
        REPORT_ID,
        str(uuid4()),
        "Soil priorities",
        str(uuid4()),
        "Water retention",
        "Minority position",
        "Preserve native cover",
        "Evidence and rationale",
        "Implications",
        None,
        None,
    )
    connection = _Connection([row])
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.list_location_delphi_minority_reports(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
        )

    query_index = next(
        index for index, event in enumerate(connection.events)
        if "list_location_delphi_minority_reports" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < query_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "delphi",
        "action": "review",
    }
    assert result["reports"][0]["report_id"] == REPORT_ID
    assert not any("participant" in key or "member" in key for key in result["reports"][0])
    assert connection.rolled_back and connection.closed
    assert not connection.committed


@pytest.mark.parametrize(
    ("field", "value"),
    [("operator_id", "bad"), ("location_id", "bad"), ("limit", 0),
     ("limit", 52), ("limit", "1.2"), ("limit", True),
     ("offset", -1), ("offset", 10001), ("offset", "1.2"), ("offset", False)],
)
def test_invalid_list_request_fails_before_database(field, value):
    arguments = {"operator_id": OPERATOR_ID, "location_id": LOCATION_ID, "limit": 50, "offset": 0}
    arguments[field] = value
    with pytest.raises(review.DelphiMinorityReviewInvalid):
        review.list_location_delphi_minority_reports(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a connection"),
        )


@pytest.mark.parametrize(
    ("decision", "reason_code"),
    [("approve", "evidence_considered"), ("verified", "privacy_concern"),
     ("rejected", "evidence_considered"), ("rejected", "free text")],
)
def test_invalid_decision_fails_before_database(decision, reason_code):
    with pytest.raises(review.DelphiMinorityReviewInvalid):
        review.decide_location_delphi_minority_report(
            OPERATOR_ID, LOCATION_ID, REPORT_ID, decision=decision,
            request_id=REQUEST_ID, reason_code=reason_code,
            connection_factory=lambda: pytest.fail("invalid decision opened a connection"),
        )


def test_decision_sets_signed_context_and_commits_function_result():
    row = (str(uuid4()), REPORT_ID, str(uuid4()), "verified", "verified", None)
    connection = _Connection(one=row)
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.decide_location_delphi_minority_report(
            OPERATOR_ID, LOCATION_ID, REPORT_ID, decision="verified",
            request_id=REQUEST_ID, reason_code="evidence_considered",
            connection_factory=lambda: connection,
        )
    query, params = next(
        operation for operation in connection.operations
        if "decide_location_delphi_minority_report" in operation[0]
    )
    assert params == (LOCATION_ID, REPORT_ID, "verified", REQUEST_ID, "evidence_considered")
    assert connection.events.index("SIGNED_CONTEXT") < connection.events.index(query)
    assert connection.committed and connection.closed
    assert result["decision"] == "verified" and result["status"] == "verified"


def test_tenant_denial_rolls_back_before_database_function():
    connection = _Connection()
    with patch.object(
        review, "set_operator_tenant_context",
        side_effect=TenantContextDenied("missing review grant"),
    ):
        with pytest.raises(TenantContextDenied):
            review.decide_location_delphi_minority_report(
                OPERATOR_ID, LOCATION_ID, REPORT_ID, decision="rejected",
                request_id=REQUEST_ID, reason_code="insufficient_evidence",
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any("decide_location_delphi_minority_report" in query for query, _ in connection.operations)


def _make_app(provider, funcs, run_in_threadpool):
    from services.gateway.delphi_minority_review_routes import register_delphi_minority_review_routes

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_delphi_minority_review_routes(router, provider, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router)
    return app


def test_routes_are_private_no_store_and_reject_extra_payload_fields():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    expected = {"location_id": LOCATION_ID, "reports": [], "has_more": False}
    funcs = {review.list_location_delphi_minority_reports: lambda *_a, **_k: expected}
    client = TestClient(_make_app(object(), funcs, run_in_threadpool))
    response = client.get(f"/operator/api/delphi/{LOCATION_ID}/minority-reports")
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"

    response = client.post(
        f"/operator/api/delphi/{LOCATION_ID}/minority-reports/{REPORT_ID}/decision",
        json={"decision": "rejected", "request_id": REQUEST_ID,
              "reason_code": "other", "participant_note": "unexpected"},
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def test_routes_fail_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    response = TestClient(_make_app(None, {}, run_in_threadpool)).get(
        f"/operator/api/delphi/{LOCATION_ID}/minority-reports"
    )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_list_route_publishes_service_pagination_bounds_and_rejects_invalid_values():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid pagination must not reach the review service")

    app = _make_app(object(), {}, run_in_threadpool)
    operation = app.openapi()["paths"][
        "/operator/api/delphi/{location_id}/minority-reports"
    ]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"] == {
        "type": "integer", "minimum": 1, "maximum": 50, "default": 50,
        "title": "Limit",
    }
    assert parameters["offset"]["schema"] == {
        "type": "integer", "minimum": 0, "maximum": 10000, "default": 0,
        "title": "Offset",
    }

    client = TestClient(app)
    path = f"/operator/api/delphi/{LOCATION_ID}/minority-reports"
    for query in ("limit=0", "limit=51", "offset=-1", "offset=10001"):
        response = client.get(f"{path}?{query}")
        assert response.status_code == 422
