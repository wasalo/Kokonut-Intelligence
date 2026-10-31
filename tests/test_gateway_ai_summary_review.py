"""Contracts for the location-scoped AI summary human-review surface."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import ai_summary_review as review

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SUMMARY_ID = str(uuid4())
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


def test_review_queue_sets_signed_scope_before_query_and_cleans_up():
    row = (
        SUMMARY_ID,
        "operations",
        "Synthetic summary content",
        False,
        ["farm_activity"],
        "rules-v1",
        None,
        True,
        [],
        {"harvest_event": {"record_ids": [], "row_count": 0, "truncated": False}},
        "holistic_wellbeing_synthesis",
        REQUEST_ID,
        "registered_worker",
        None,
        None,
    )
    connection = _Connection([row])
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.list_location_ai_summary_reviews(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    query_index = next(
        index for index, event in enumerate(connection.events)
        if "list_location_ai_summary_reviews_with_creator" in event
    )
    assert connection.events.index("SIGNED_CONTEXT") < query_index
    assert connection.context == {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "ai_summary",
        "action": "review",
    }
    assert result["summaries"][0]["summary_id"] == SUMMARY_ID
    assert result["summaries"][0]["review_ready"] is True
    assert result["summaries"][0]["creator_task_key"] == "holistic_wellbeing_synthesis"
    assert result["summaries"][0]["creator_run_id"] == REQUEST_ID
    assert result["summaries"][0]["creator_kind"] == "registered_worker"
    assert result["summaries"][0]["creator_operator_id"] is None
    assert result["summaries"][0]["creator_request_id"] is None
    assert result["summaries"][0]["source_references"]["harvest_event"]["row_count"] == 0
    assert result["limit"] == 50
    assert result["offset"] == 0
    assert connection.rolled_back and connection.closed
    assert not connection.committed


def test_review_queue_does_not_advertise_a_page_beyond_the_offset_ceiling():
    row = (
        SUMMARY_ID,
        "operations",
        "Synthetic summary content",
        False,
        ["harvest_event"],
        "rules-v1",
        None,
        True,
        [],
        {"harvest_event": {"record_ids": [], "row_count": 0, "truncated": False}},
        "holistic_wellbeing_synthesis",
        REQUEST_ID,
        "registered_worker",
        None,
        None,
    )
    connection = _Connection([row] * 51)
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.list_location_ai_summary_reviews(
            OPERATOR_ID,
            LOCATION_ID,
            limit=50,
            offset=10000,
            connection_factory=lambda: connection,
        )

    assert result["limit"] == 50
    assert result["offset"] == 10000
    assert len(result["summaries"]) == 50
    assert result["has_more"] is False


def test_review_queue_returns_human_creator_and_request_receipt():
    request_id = str(uuid4())
    row = (
        SUMMARY_ID,
        "operations",
        "Operator-created draft",
        False,
        ["harvest_event"],
        "rules-v1",
        None,
        False,
        ["self_review"],
        {"harvest_event": {"record_ids": [], "row_count": 0, "truncated": False}},
        None,
        None,
        "operator",
        OPERATOR_ID,
        request_id,
    )
    connection = _Connection([row])
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.list_location_ai_summary_reviews(
            OPERATOR_ID,
            LOCATION_ID,
            connection_factory=lambda: connection,
        )

    summary = result["summaries"][0]
    assert summary["creator_kind"] == "operator"
    assert summary["creator_operator_id"] == OPERATOR_ID
    assert summary["creator_request_id"] == request_id
    assert summary["creator_task_key"] is None
    assert summary["creator_run_id"] is None


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
def test_invalid_queue_request_fails_before_database(field, value):
    arguments = {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "limit": 50,
        "offset": 0,
    }
    arguments[field] = value
    with pytest.raises(review.AiSummaryReviewInvalid):
        review.list_location_ai_summary_reviews(
            **arguments,
            connection_factory=lambda: pytest.fail("invalid request opened a connection"),
        )


@pytest.mark.parametrize(
    ("decision", "reason_code"),
    [
        ("accept", "approved_after_review"),
        ("approve", "privacy_concern"),
        ("reject", "approved_after_review"),
        ("reject", "free-text reason"),
        ([], "other"),
        ("reject", []),
        (None, "other"),
        ("reject", None),
    ],
)
def test_invalid_decision_fails_before_database(decision, reason_code):
    with pytest.raises(review.AiSummaryReviewInvalid):
        review.decide_location_ai_summary_review(
            OPERATOR_ID,
            LOCATION_ID,
            SUMMARY_ID,
            decision=decision,
            request_id=REQUEST_ID,
            reason_code=reason_code,
            connection_factory=lambda: pytest.fail("invalid decision opened a connection"),
        )


def test_human_decision_sets_scope_before_call_and_commits():
    connection = _Connection(
        one=(str(uuid4()), SUMMARY_ID, "approve", "verified", None)
    )
    with patch.object(review, "set_operator_tenant_context", _set_context):
        result = review.decide_location_ai_summary_review(
            OPERATOR_ID,
            LOCATION_ID,
            SUMMARY_ID,
            decision="approve",
            request_id=REQUEST_ID,
            reason_code="approved_after_review",
            connection_factory=lambda: connection,
        )

    decision_query = next(
        params for query, params in connection.operations
        if "decide_location_ai_summary_review" in query
    )
    assert decision_query == (
        LOCATION_ID,
        SUMMARY_ID,
        "approve",
        REQUEST_ID,
        "approved_after_review",
    )
    assert connection.events.index("SIGNED_CONTEXT") < next(
        index for index, event in enumerate(connection.events)
        if "decide_location_ai_summary_review" in event
    )
    assert connection.committed and connection.closed
    assert result["resulting_status"] == "verified"


def test_tenant_denial_rolls_back_without_review_call():
    connection = _Connection()
    with patch.object(
        review,
        "set_operator_tenant_context",
        side_effect=TenantContextDenied("missing review grant"),
    ):
        with pytest.raises(TenantContextDenied):
            review.decide_location_ai_summary_review(
                OPERATOR_ID,
                LOCATION_ID,
                SUMMARY_ID,
                decision="reject",
                request_id=REQUEST_ID,
                reason_code="insufficient_evidence",
                connection_factory=lambda: connection,
            )
    assert connection.rolled_back and connection.closed
    assert not any(
        "decide_location_ai_summary_review" in query
        for query, _params in connection.operations
    )


def _make_app(provider, funcs, run_in_threadpool):
    from services.gateway.ai_summary_review_routes import register_ai_summary_review_routes

    app = FastAPI()
    router = APIRouter()

    @app.middleware("http")
    async def bind_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    register_ai_summary_review_routes(router, provider, run_in_threadpool, __import__("psycopg2"))
    app.include_router(router)
    return app


def test_review_route_is_no_store_and_uses_operator_session():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    expected = {
        "location_id": LOCATION_ID,
        "limit": 50,
        "offset": 0,
        "summaries": [],
        "has_more": False,
    }
    funcs = {review.list_location_ai_summary_reviews: lambda *_a, **_k: expected}
    client = TestClient(_make_app(object(), funcs, run_in_threadpool))
    response = client.get(f"/operator/api/ai-summaries/{LOCATION_ID}/reviews")

    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def _valid_review_response():
    return {
        "location_id": LOCATION_ID,
        "limit": 50,
        "offset": 0,
        "summaries": [
            {
                "summary_id": SUMMARY_ID,
                "summary_type": "operations",
                "content": "Synthetic summary content",
                "content_truncated": False,
                "source_tables": ["harvest_event"],
                "source_references": {
                    "harvest_event": {
                        "record_ids": [REQUEST_ID],
                        "row_count": 1,
                        "truncated": False,
                    }
                },
                "model_version": "rules-v1",
                "created_at": datetime(2026, 10, 28, tzinfo=UTC),
                "review_ready": True,
                "blocked_reasons": [],
                "creator_task_key": "holistic_wellbeing_synthesis",
                "creator_run_id": REQUEST_ID,
                "creator_kind": "registered_worker",
                "creator_operator_id": None,
                "creator_request_id": None,
            }
        ],
        "has_more": False,
    }


def test_review_route_validates_response_and_documents_strict_projection():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    expected = _valid_review_response()
    funcs = {review.list_location_ai_summary_reviews: lambda *_a, **_k: expected}
    app = _make_app(object(), funcs, run_in_threadpool)
    operation = app.openapi()["paths"][
        "/operator/api/ai-summaries/{location_id}/reviews"
    ]["get"]
    schemas = app.openapi()["components"]["schemas"]
    page_schema = schemas["AiSummaryReviewPage"]
    item_schema = schemas["AiSummaryReviewItem"]
    source_schema = schemas["AiSummarySourceReference"]
    reference_map_schema = item_schema["properties"]["source_references"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AiSummaryReviewPage"
    }
    assert page_schema["additionalProperties"] is False
    assert page_schema["properties"]["limit"]["maximum"] == 50
    assert page_schema["properties"]["offset"]["maximum"] == 10000
    assert item_schema["additionalProperties"] is False
    assert item_schema["properties"]["content"]["maxLength"] == 20000
    assert source_schema["additionalProperties"] is False
    assert source_schema["properties"]["record_ids"]["items"]["format"] == "uuid"
    assert reference_map_schema["maxProperties"] == 20
    assert reference_map_schema["propertyNames"]["pattern"] == "^[a-z][a-z0-9_]{0,62}$"
    assert source_schema["properties"]["scope"]["anyOf"][0]["enum"] == [
        "location",
        "network",
        "location_or_network",
    ]
    assert operation["responses"]["403"]["headers"]["Cache-Control"]["schema"][
        "example"
    ] == "no-store"

    response = TestClient(app).get(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews"
    )
    assert response.status_code == 200
    assert response.json()["summaries"][0]["summary_id"] == SUMMARY_ID
    assert response.json()["summaries"][0]["created_at"] == "2026-10-28T00:00:00Z"
    assert response.headers["cache-control"] == "no-store"


def test_review_route_accepts_network_reference_scope_and_unregistered_worker_blocker():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    response_body = _valid_review_response()
    summary = response_body["summaries"][0]
    summary["source_tables"] = [f"network_source_{index:02d}" for index in range(12)]
    summary["source_references"] = {
        table: {
            "record_ids": [REQUEST_ID],
            "row_count": 1,
            "truncated": False,
            "scope": "network",
        }
        for table in summary["source_tables"]
    }
    summary["blocked_reasons"] = ["worker_task_unregistered"]
    summary["review_ready"] = False
    summary["creator_task_key"] = "unregistered_worker"
    summary["creator_kind"] = "unregistered_worker"
    funcs = {review.list_location_ai_summary_reviews: lambda *_a, **_k: response_body}

    response = TestClient(_make_app(object(), funcs, run_in_threadpool)).get(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews"
    )

    assert response.status_code == 200
    assert len(response.json()["summaries"][0]["source_references"]) == 12
    assert response.json()["summaries"][0]["source_references"][
        "network_source_00"
    ]["scope"] == "network"
    assert response.json()["summaries"][0]["blocked_reasons"] == [
        "worker_task_unregistered"
    ]


def test_review_route_preserves_null_timestamps_last():
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    response_body = _valid_review_response()
    dated = response_body["summaries"][0]
    dated["created_at"] = datetime(2026, 10, 28, tzinfo=UTC)
    null_dated = deepcopy(dated)
    null_dated["summary_id"] = str(uuid4())
    null_dated["created_at"] = None
    response_body["summaries"].append(null_dated)
    funcs = {review.list_location_ai_summary_reviews: lambda *_a, **_k: response_body}

    response = TestClient(_make_app(object(), funcs, run_in_threadpool)).get(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews"
    )

    assert response.status_code == 200
    assert response.json()["summaries"][1]["created_at"] is None


@pytest.mark.parametrize(
    ("mutation", "query"),
    [
        ("location", ""),
        ("limit", ""),
        ("offset", "offset=10"),
        ("page_extra", ""),
        ("item_extra", ""),
        ("creator_kind", ""),
        ("reference_table", ""),
        ("reference_counts", ""),
        ("blocked_reason", ""),
        ("readiness", ""),
        ("oversized_content", ""),
        ("duplicate_summary_ids", ""),
        ("descending_order", ""),
        ("truncated_content_short", ""),
    ],
)
def test_review_route_rejects_mismatched_or_private_projection(mutation, query):
    async def run_in_threadpool(func, *args, **kwargs):
        return funcs[func](*args, **kwargs)

    invalid = deepcopy(_valid_review_response())
    item = invalid["summaries"][0]
    if mutation == "location":
        invalid["location_id"] = str(uuid4())
    elif mutation == "limit":
        invalid["limit"] = 49
    elif mutation == "offset":
        invalid["offset"] = 0
    elif mutation == "page_extra":
        invalid["internal_receipt"] = "must not escape"
    elif mutation == "item_extra":
        item["private_operator_note"] = "must not escape"
    elif mutation == "creator_kind":
        item["creator_kind"] = "unknown"
    elif mutation == "reference_table":
        item["source_references"]["private_table"] = {
            "record_ids": [str(uuid4())],
            "row_count": 1,
            "truncated": False,
        }
    elif mutation == "reference_counts":
        item["source_references"]["harvest_event"]["row_count"] = 0
    elif mutation == "blocked_reason":
        item["blocked_reasons"] = ["private_internal_reason"]
    elif mutation == "readiness":
        item["blocked_reasons"] = ["self_review"]
    elif mutation == "oversized_content":
        item["content"] = "x" * 20_001
    elif mutation == "duplicate_summary_ids":
        invalid["summaries"].append(deepcopy(item))
    elif mutation == "descending_order":
        later = deepcopy(item)
        later["summary_id"] = str(uuid4())
        item["created_at"] = datetime(2026, 10, 29, tzinfo=UTC)
        later["created_at"] = datetime(2026, 10, 28, tzinfo=UTC)
        invalid["summaries"].append(later)
    elif mutation == "truncated_content_short":
        item["content_truncated"] = True

    funcs = {review.list_location_ai_summary_reviews: lambda *_a, **_k: invalid}
    client = TestClient(_make_app(object(), funcs, run_in_threadpool))
    response = client.get(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews"
        + (f"?{query}" if query else "")
    )

    assert response.status_code == 500
    assert response.json() == {"error": "AI summary review unavailable"}
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_review_route_keeps_no_store_on_tenant_denial():
    async def run_in_threadpool(*_args, **_kwargs):
        raise TenantContextDenied("missing review grant")

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.get(f"/operator/api/ai-summaries/{LOCATION_ID}/reviews")

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_review_route_documents_page_bounds_and_rejects_invalid_values_before_service():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid page must not invoke the review service")

    app = _make_app(object(), {}, run_in_threadpool)
    operation = app.openapi()["paths"][
        "/operator/api/ai-summaries/{location_id}/reviews"
    ]["get"]
    parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
    assert parameters["limit"]["schema"]["default"] == 50
    assert parameters["limit"]["schema"]["minimum"] == 1
    assert parameters["limit"]["schema"]["maximum"] == 50
    assert parameters["offset"]["schema"]["default"] == 0
    assert parameters["offset"]["schema"]["minimum"] == 0
    assert parameters["offset"]["schema"]["maximum"] == 10000

    client = TestClient(app)
    for query in ("limit=0", "limit=51", "offset=-1", "offset=10001"):
        response = client.get(
            f"/operator/api/ai-summaries/{LOCATION_ID}/reviews?{query}"
        )
        assert response.status_code == 422


def test_decision_route_rejects_extra_body_fields():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid payload must not invoke decision service")

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews/{SUMMARY_ID}/decision",
        json={
            "decision": "reject",
            "request_id": REQUEST_ID,
            "reason_code": "other",
            "free_text": "unexpected",
        },
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": [], "request_id": REQUEST_ID, "reason_code": "other"},
        {"decision": "reject", "request_id": REQUEST_ID, "reason_code": []},
    ],
)
def test_decision_route_returns_bad_request_for_malformed_field_types(payload):
    async def run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    with patch.object(
        review,
        "_connection_factory",
        side_effect=AssertionError("malformed payload must fail before database setup"),
    ):
        response = client.post(
            f"/operator/api/ai-summaries/{LOCATION_ID}/reviews/{SUMMARY_ID}/decision",
            json=payload,
        )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


def _valid_decision_result(request_decision="approve", **overrides):
    result = {
        "review_id": str(uuid4()),
        "summary_id": SUMMARY_ID,
        "decision": request_decision,
        "resulting_status": "verified" if request_decision == "approve" else "rejected",
        "created_at": datetime(2026, 10, 29, tzinfo=UTC),
    }
    result.update(overrides)
    return result


@pytest.mark.parametrize(
    ("decision", "reason_code", "resulting_status"),
    [
        ("approve", "approved_after_review", "verified"),
        ("reject", "privacy_concern", "rejected"),
    ],
)
def test_decision_route_publishes_and_validates_schema(decision, reason_code, resulting_status):
    captured = []
    result = _valid_decision_result(decision)

    async def run_in_threadpool(func, *args, **kwargs):
        captured.append((func, args, kwargs))
        return result

    app = _make_app(
        object(),
        {review.decide_location_ai_summary_review: lambda *_a, **_k: result},
        run_in_threadpool,
    )
    operation = app.openapi()["paths"][
        "/operator/api/ai-summaries/{location_id}/reviews/{summary_id}/decision"
    ]["post"]
    schemas = app.openapi()["components"]["schemas"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert request_schema["additionalProperties"] is False
    assert set(request_schema["required"]) == {"decision", "request_id", "reason_code"}
    assert request_schema["properties"]["decision"]["enum"] == ["approve", "reject"]
    assert request_schema["properties"]["reason_code"]["enum"] == [
        "approved_after_review",
        "insufficient_evidence",
        "privacy_concern",
        "unsupported_claim",
        "other",
    ]
    assert response_schema == {"$ref": "#/components/schemas/AiSummaryReviewDecisionResponse"}
    assert schemas["AiSummaryReviewDecisionResponse"]["additionalProperties"] is False
    assert operation["responses"]["500"]["headers"]["Cache-Control"]["schema"][
        "example"
    ] == "no-store"

    response = TestClient(app).post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews/{SUMMARY_ID}/decision",
        json={"decision": decision, "request_id": REQUEST_ID, "reason_code": reason_code},
    )

    assert response.status_code == 200
    assert response.json()["summary_id"] == SUMMARY_ID
    assert response.json()["resulting_status"] == resulting_status
    assert response.headers["cache-control"] == "no-store"
    assert len(captured) == 1
    assert captured[0][1][1:3] == (LOCATION_ID, SUMMARY_ID)
    assert captured[0][2] == {
        "decision": decision,
        "request_id": REQUEST_ID,
        "reason_code": reason_code,
    }


@pytest.mark.parametrize(
    ("location_id", "summary_id"),
    [("invalid-location", SUMMARY_ID), (LOCATION_ID, "invalid-summary")],
)
def test_invalid_decision_path_identifiers_fail_before_service(location_id, summary_id):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("invalid path identifiers must not invoke the decision service")

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.post(
        f"/operator/api/ai-summaries/{location_id}/reviews/{summary_id}/decision",
        json={
            "decision": "reject",
            "request_id": REQUEST_ID,
            "reason_code": "other",
        },
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("decision", "reason_code"),
    [("approve", "privacy_concern"), ("reject", "approved_after_review")],
)
def test_decision_route_rejects_inconsistent_reason_before_service(decision, reason_code):
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("inconsistent decision reason must fail before service dispatch")

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews/{SUMMARY_ID}/decision",
        json={"decision": decision, "request_id": REQUEST_ID, "reason_code": reason_code},
    )

    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "malformed_result",
    [
        _valid_decision_result("approve", summary_id=str(uuid4())),
        _valid_decision_result("approve", decision="approve", resulting_status="verified"),
        _valid_decision_result("approve", resulting_status="published"),
        _valid_decision_result("reject", extra="private"),
        _valid_decision_result("reject", created_at="not-a-timestamp"),
    ],
)
def test_malformed_decision_result_fails_closed_without_store(malformed_result):
    async def run_in_threadpool(*_args, **_kwargs):
        return malformed_result

    client = TestClient(_make_app(object(), {}, run_in_threadpool))
    response = client.post(
        f"/operator/api/ai-summaries/{LOCATION_ID}/reviews/{SUMMARY_ID}/decision",
        json={
            "decision": "reject",
            "request_id": REQUEST_ID,
            "reason_code": "other",
        },
    )

    assert response.status_code == 500
    assert response.json() == {"error": "AI summary review unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_routes_fail_closed_when_oidc_is_disabled():
    async def run_in_threadpool(*_args, **_kwargs):
        pytest.fail("OIDC-disabled request must not reach service")

    client = TestClient(_make_app(None, {}, run_in_threadpool))
    response = client.get(f"/operator/api/ai-summaries/{LOCATION_ID}/reviews")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
