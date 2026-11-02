"""Location-scoped funding draft and proposed-tranche Gateway contracts."""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import solution_lifecycle_actions as actions
from services.gateway import solution_lifecycle_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SOLUTION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
RESULT = {
    "funding_case_id": str(uuid4()),
    "decision_status": "draft",
    "tranche_count": 1,
    "created_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
SUBMISSION_RESULT = {
    "funding_case_id": str(uuid4()),
    "decision_status": "submitted",
    "tranche_count": 1,
    "submitted_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
APPROVAL_RESULT = {
    "funding_case_id": str(uuid4()),
    "decision_status": "approved",
    "approved_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
TRANCHE_RESULT = {
    "funding_case_id": str(uuid4()),
    "tranche_id": str(uuid4()),
    "tranche_status": "approved",
    "approved_at": "2026-10-20T12:00:00+00:00",
    "replayed": False,
}
TRANCHE_REVIEW_DETAIL = {
    "funding_case_id": RESULT["funding_case_id"],
    "tranche_id": TRANCHE_RESULT["tranche_id"],
    "solution_name": "Watershed restoration",
    "case_decision_status": "approved",
    "case_currency": "cUSD",
    "case_submitter_attributed": True,
    "is_self_authored": False,
    "is_case_approver": False,
    "tranche_number": 1,
    "tranche_amount": 300,
    "milestone_conditions": {"step": "review"},
    "tranche_status": "proposed",
    "tranche_approved_at": None,
    "eligible_for_independent_approval": True,
}
FUNDING_CREATED_AT = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
FUNDING_SUBMITTED_AT = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
FUNDING_APPROVED_AT = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
FUNDING_APPROVAL_ROUTE_RESULT = {
    "funding_case_id": RESULT["funding_case_id"],
    "decision_status": "approved",
    "approved_at": FUNDING_APPROVED_AT,
    "replayed": False,
}
FUNDING_REVIEW_QUEUE_ITEM = {
    "funding_case_id": RESULT["funding_case_id"],
    "solution_name": "Watershed restoration",
    "solution_type": "practice",
    "solution_stage": "investment_ready",
    "capital_stage": "pilot",
    "funding_instrument": "grant",
    "requested_amount": Decimal("1000.00"),
    "currency": "cUSD",
    "created_at": FUNDING_CREATED_AT,
    "submitted_at": FUNDING_SUBMITTED_AT,
    "tranche_count": 1,
    "submitter_attributed": True,
    "is_self_authored": False,
}
FUNDING_REVIEW_QUEUE_PAGE = {
    "location_id": LOCATION_ID,
    "offset": 0,
    "funding_cases": [FUNDING_REVIEW_QUEUE_ITEM],
    "has_more": False,
    "next_offset": None,
}
FUNDING_REVIEW_DETAIL = {
    "funding_case_id": RESULT["funding_case_id"],
    "solution_name": "Watershed restoration",
    "solution_type": "practice",
    "solution_stage": "investment_ready",
    "capital_stage": "pilot",
    "funding_instrument": "grant",
    "requested_amount": Decimal("1000.00"),
    "minimum_viable_amount": Decimal("500.00"),
    "maximum_authorized_amount": Decimal("1200.00"),
    "currency": "cUSD",
    "risk_adjusted_expected_value": Decimal("900.00"),
    "public_goods_value": Decimal("1100.00"),
    "community_share": Decimal("100.00"),
    "downside_exposure": Decimal("250.00"),
    "decision_status": "submitted",
    "rationale": "Synthetic independent review rationale",
    "evidence": [{"ref": "private:budget"}],
    "created_at": FUNDING_CREATED_AT,
    "submitted_at": FUNDING_SUBMITTED_AT,
    "tranches": [{
        "tranche_number": 1,
        "amount": Decimal("500.00"),
        "milestone_conditions": {"milestone": "soil baseline reviewed"},
        "status": "proposed",
    }],
    "submitter_attributed": True,
    "is_self_authored": False,
}
PROPOSAL = {
    "capital_stage": "pilot",
    "funding_instrument": "community_fund",
    "requested_amount": "1000.00",
    "minimum_viable_amount": "500.00",
    "maximum_authorized_amount": "1200.00",
    "currency": "cUSD",
    "risk_adjusted_expected_value": "900.00",
    "public_goods_value": "1100.00",
    "community_share": "100.00",
    "downside_exposure": "250.00",
    "rationale": "Synthetic pilot funding draft",
    "evidence": [{"ref": "synthetic:budget"}],
    "tranches": [{
        "amount": 400,
        "milestone_conditions": {"milestone": "soil baseline reviewed"},
    }],
}
BODY = {"request_id": REQUEST_ID, **PROPOSAL}


class _Connection:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)
        self.operations = []
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
        row = connection.row or (connection.rows[0] if connection.rows else {})
        self.description = tuple(SimpleNamespace(name=key) for key in row)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        if self.connection.row is None:
            return None
        return tuple(self.connection.row.values())

    def fetchall(self):
        return [tuple(row.values()) for row in self.connection.rows]


def test_funding_proposal_sets_exact_create_context_and_commits_draft_only():
    connection = _Connection(RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.propose_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            SOLUTION_ID,
            REQUEST_ID,
            **PROPOSAL,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "create",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.propose_location_solution_funding" in query
    assert params == (
        LOCATION_ID, SOLUTION_ID, REQUEST_ID, "pilot", "community_fund",
        "1000.00", "500.00", "1200.00", "cUSD", "900.00", "1100.00",
        "100.00", "250.00", "Synthetic pilot funding draft",
        '[{"ref":"synthetic:budget"}]',
        '[{"amount":400.00,"milestone_conditions":{"milestone":"soil baseline reviewed"}}]',
    )
    assert result == RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"capital_stage": "unknown"}, "capital stage"),
        ({"funding_instrument": "crypto"}, "instrument"),
        ({"requested_amount": -1}, "nonnegative"),
        ({"requested_amount": 1.001}, "two decimal places"),
        ({"requested_amount": float("inf")}, "finite amount"),
        ({"minimum_viable_amount": 1201}, "Minimum viable amount cannot exceed"),
        ({"maximum_authorized_amount": 999}, "Maximum authorized amount cannot be below"),
        ({"currency": "bad currency"}, "Currency"),
        ({"rationale": "  "}, "rationale"),
        ({"evidence": {}}, "evidence must be a list"),
        ({"tranches": {}}, "tranches must be a list"),
        ({"tranches": [{"amount": -1, "milestone_conditions": {}}]}, "Tranche amount must be nonnegative"),
        ({"tranches": [{"amount": 1201, "milestone_conditions": {}}]}, "tranche total exceeds"),
        ({"tranches": [{"amount": 1, "milestone_conditions": []}]}, "milestone conditions"),
    ],
)
def test_invalid_funding_proposal_fails_before_database(changes, message):
    payload = {**PROPOSAL, **changes}
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match=message):
        actions.propose_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            SOLUTION_ID,
            REQUEST_ID,
            **payload,
            connection_factory=lambda: pytest.fail("invalid proposal must fail before DB"),
        )


def test_funding_submission_sets_exact_submit_context_and_commits():
    connection = _Connection(SUBMISSION_RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.submit_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            REQUEST_ID,
            True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "submit",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.submit_location_solution_funding" in query
    assert params == (LOCATION_ID, RESULT["funding_case_id"], REQUEST_ID, True)
    assert result == SUBMISSION_RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("acknowledged", [False, None, 1, "true"])
def test_funding_submission_requires_literal_acknowledgement_before_database(acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.submit_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            REQUEST_ID,
            acknowledged,
            connection_factory=lambda: pytest.fail("missing acknowledgement must fail before DB"),
        )


def test_funding_approval_sets_exact_review_context_and_commits_case_decision_only():
    connection = _Connection(APPROVAL_RESULT)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(actions, "set_operator_tenant_context", set_context):
        result = actions.approve_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            REQUEST_ID,
            True,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    }]
    query, params = connection.operations[-1]
    assert "kokonut_security.approve_location_solution_funding" in query
    assert params == (LOCATION_ID, RESULT["funding_case_id"], REQUEST_ID, True)
    assert result == APPROVAL_RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("acknowledged", [False, None, 1, "true"])
def test_funding_approval_requires_literal_acknowledgement_before_database(acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.approve_location_solution_funding(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            REQUEST_ID,
            acknowledged,
            connection_factory=lambda: pytest.fail("missing acknowledgement must fail before DB"),
        )


def test_funding_tranche_approval_sets_exact_review_context_and_commits():
    connection = _Connection(TRANCHE_RESULT)
    contexts = []
    with patch.object(
        actions,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = actions.approve_location_solution_funding_tranche(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            TRANCHE_RESULT["tranche_id"],
            REQUEST_ID,
            True,
            connection_factory=lambda: connection,
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    query, params = connection.operations[-1]
    assert "kokonut_security.approve_location_solution_funding_tranche" in query
    assert params == (
        LOCATION_ID, RESULT["funding_case_id"], TRANCHE_RESULT["tranche_id"],
        REQUEST_ID, True,
    )
    assert result == TRANCHE_RESULT
    assert connection.committed and connection.closed and not connection.rolled_back


@pytest.mark.parametrize("acknowledged", [False, None, 1, "true"])
def test_funding_tranche_approval_requires_literal_acknowledgement_before_database(acknowledged):
    with pytest.raises(actions.SolutionLifecycleActionInvalid, match="acknowledgement"):
        actions.approve_location_solution_funding_tranche(
            OPERATOR_ID,
            LOCATION_ID,
            RESULT["funding_case_id"],
            TRANCHE_RESULT["tranche_id"],
            REQUEST_ID,
            acknowledged,
            connection_factory=lambda: pytest.fail("missing acknowledgement must fail before DB"),
        )


def test_funding_target_read_uses_same_connection_and_signed_read_context():
    row = {
        "solution_id": SOLUTION_ID,
        "solution_name": "Soil restoration",
        "solution_type": "practice",
        "current_stage": "testing",
        "solution_status": "active",
    }
    connection = _Connection(rows=[row])
    contexts = []
    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.list_location_solution_funding_targets(
            OPERATOR_ID, LOCATION_ID, limit=1, connection_factory=lambda: connection
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "read",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.list_location_solution_funding_targets" in connection.operations[-1][0]
    assert result["solutions"] == [row]
    assert connection.closed and connection.rolled_back and not connection.committed


def test_funding_review_queue_uses_same_connection_exact_review_context_and_bounded_page():
    row = {
        "funding_case_id": str(uuid4()),
        "solution_name": "Watershed restoration",
        "requested_amount": "1250.00",
        "submitter_attributed": True,
        "is_self_authored": False,
    }
    connection = _Connection(rows=[row])
    contexts = []
    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.list_location_solution_funding_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=1, connection_factory=lambda: connection
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.list_location_solution_funding_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 0)
    assert result["funding_cases"] == [row]
    assert result["has_more"] is False
    assert connection.closed and connection.rolled_back and not connection.committed


def test_funding_review_queue_does_not_advertise_offset_beyond_cap():
    rows = [
        {"funding_case_id": str(uuid4()), "requested_amount": "10.00"},
        {"funding_case_id": str(uuid4()), "requested_amount": "20.00"},
    ]
    connection = _Connection(rows=rows)
    with patch.object(reads, "set_operator_tenant_context", lambda *_a, **_k: None):
        result = reads.list_location_solution_funding_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=1,
            offset=10000,
            connection_factory=lambda: connection,
        )
    assert result["funding_cases"] == rows[:1]
    assert result["has_more"] is False
    assert result["next_offset"] is None
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 10000)
    assert connection.closed and connection.rolled_back and not connection.committed


def test_funding_review_detail_is_exact_grant_context_read_only_and_private():
    row = {
        "funding_case_id": str(uuid4()),
        "solution_name": "Watershed restoration",
        "requested_amount": "1250.00",
        "rationale": "Synthetic private rationale",
        "evidence": [{"ref": "private:budget"}],
        "tranches": [{"tranche_number": 1, "amount": "500.00"}],
        "submitter_attributed": True,
        "is_self_authored": False,
    }
    connection = _Connection(row=row)
    contexts = []
    funding_case_id = row["funding_case_id"]
    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.get_location_solution_funding_review_detail(
            OPERATOR_ID, LOCATION_ID, funding_case_id,
            connection_factory=lambda: connection,
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.get_location_solution_funding_review_detail" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, funding_case_id)
    assert result == row
    assert connection.closed and connection.rolled_back and not connection.committed


def test_funding_tranche_review_detail_uses_exact_grant_read_only_context():
    row = {
        "funding_case_id": RESULT["funding_case_id"],
        "tranche_id": TRANCHE_RESULT["tranche_id"],
        "case_decision_status": "approved",
        "case_submitter_attributed": True,
        "is_self_authored": False,
        "is_case_approver": False,
        "tranche_status": "proposed",
        "tranche_amount": "300.00",
        "milestone_conditions": {"step": "review"},
        "eligible_for_independent_approval": True,
    }
    connection = _Connection(row=row)
    contexts = []
    with patch.object(
        reads,
        "set_operator_tenant_context",
        lambda conn, **kwargs: contexts.append((conn, kwargs)),
    ):
        result = reads.get_location_solution_funding_tranche_review_detail(
            OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"],
            TRANCHE_RESULT["tranche_id"], connection_factory=lambda: connection,
        )
    assert contexts == [(connection, {
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "solution_lifecycle",
        "action": "review",
    })]
    assert connection.operations[0][0] == "SET TRANSACTION READ ONLY"
    assert "kokonut_security.get_location_solution_funding_tranche_review_detail" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (
        LOCATION_ID, RESULT["funding_case_id"], TRANCHE_RESULT["tranche_id"]
    )
    assert result == row
    assert connection.closed and connection.rolled_back and not connection.committed


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (1, -1), (1, 10001), (True, 0)])
def test_funding_review_queue_invalid_page_fails_before_database(limit, offset):
    with pytest.raises(reads.SolutionLifecycleReadInvalid):
        reads.list_location_solution_funding_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB"),
        )


def test_funding_routes_have_exact_read_and_create_location_policies():
    target_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/targets"
    proposal_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    submission_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/submit"
    )
    review_queue_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/review"
    review_detail_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/review"
    )
    approval_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/approve"
    )
    tranche_review_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/{RESULT['funding_case_id']}"
        f"/tranches/{TRANCHE_RESULT['tranche_id']}/review"
    )
    tranche_approve_path = tranche_review_path.removesuffix("/review") + "/approve"
    assert auth_route_policy("GET", target_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "read", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("POST", proposal_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "create", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("PATCH", proposal_path, enabled=True) is None
    assert auth_route_policy("POST", submission_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "submit", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("GET", submission_path, enabled=True) is None
    for review_path in (review_queue_path, review_detail_path):
        assert auth_route_policy("GET", review_path, enabled=True) == {
            "resource": "solution_lifecycle", "action": "review", "public": False,
            "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
        }
        assert auth_route_policy("POST", review_path, enabled=True) is None
    assert auth_route_policy("POST", approval_path, enabled=True) == {
        "resource": "solution_lifecycle", "action": "review", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }
    assert auth_route_policy("GET", approval_path, enabled=True) is None
    for method, path in (("GET", tranche_review_path), ("POST", tranche_approve_path)):
        assert auth_route_policy(method, path, enabled=True) == {
            "resource": "solution_lifecycle", "action": "review", "public": False,
            "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
        }


def _app(
    provider, monkeypatch, proposal_action, submission_action=None,
    review_queue_action=None, review_detail_action=None, approval_action=None,
    tranche_detail_action=None, tranche_approval_action=None,
):
    from services.gateway.solution_lifecycle_routes import register_solution_lifecycle_routes

    monkeypatch.setattr(reads, "list_location_solution_funding_targets", lambda *_a, **_k: {"solutions": []})
    monkeypatch.setattr(
        reads,
        "list_location_solution_funding_review_queue",
        review_queue_action or (lambda *_a, **_k: FUNDING_REVIEW_QUEUE_PAGE),
    )
    monkeypatch.setattr(
        reads,
        "get_location_solution_funding_review_detail",
        review_detail_action or (lambda *_a, **_k: FUNDING_REVIEW_DETAIL),
    )
    monkeypatch.setattr(
        reads,
        "get_location_solution_funding_tranche_review_detail",
        tranche_detail_action or (lambda *_a, **_k: TRANCHE_RESULT),
    )
    monkeypatch.setattr(actions, "propose_location_solution_funding", proposal_action)
    monkeypatch.setattr(
        actions,
        "submit_location_solution_funding",
        submission_action or (lambda *_args, **_kwargs: SUBMISSION_RESULT),
    )
    monkeypatch.setattr(
        actions,
        "approve_location_solution_funding",
        approval_action or (lambda *_args, **_kwargs: APPROVAL_RESULT),
    )
    monkeypatch.setattr(
        actions,
        "approve_location_solution_funding_tranche",
        tranche_approval_action or (lambda *_args, **_kwargs: TRANCHE_RESULT),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_solution_lifecycle_routes(router, provider, run_in_threadpool, SimpleNamespace(Error=Exception))
    app.include_router(router)
    return app


def test_funding_draft_route_returns_created_with_no_store(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT)

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 201
    assert response.json() == RESULT
    assert response.headers["cache-control"] == "no-store"


def test_funding_proposal_tenant_denial_maps_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch,
        lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/solutions/{SOLUTION_ID}/funding"
    with TestClient(app) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_funding_submission_route_requires_exact_body_and_returns_no_store(monkeypatch):
    submitted = []
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
               lambda *args: submitted.append(args) or SUBMISSION_RESULT)

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/submit"
    )
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
        malformed = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True, "amount": 20})
    assert response.status_code == 200
    assert response.json() == SUBMISSION_RESULT
    assert response.headers["cache-control"] == "no-store"
    assert submitted == [(
        OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"], REQUEST_ID, True
    )]
    assert malformed.status_code == 400


def test_funding_approval_route_requires_exact_body_and_returns_created_or_replayed(monkeypatch):
    approved = []
    approval_results = [
        dict(FUNDING_APPROVAL_ROUTE_RESULT),
        {**FUNDING_APPROVAL_ROUTE_RESULT, "replayed": True},
    ]
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        approval_action=lambda *args: approved.append(args) or approval_results.pop(0),
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/approve"
    )
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
        replay = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
        malformed = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True, "release": True})
    assert response.status_code == 201
    assert response.json() == {
        **FUNDING_APPROVAL_ROUTE_RESULT,
        "approved_at": "2026-10-22T12:00:00+00:00",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert replay.status_code == 200
    assert replay.json() == {
        **FUNDING_APPROVAL_ROUTE_RESULT,
        "approved_at": "2026-10-22T12:00:00+00:00",
        "replayed": True,
    }
    assert replay.headers["cache-control"] == "no-store"
    assert replay.headers["vary"] == "Cookie"
    assert approved == [(
        OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"], REQUEST_ID, True
    )] * 2
    assert malformed.status_code == 400


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(funding_case_id=str(uuid4())),
        lambda result: result.update(decision_status="submitted"),
        lambda result: result.pop("approved_at"),
        lambda result: result.update(unexpected="private receipt detail"),
        lambda result: result.update(approved_at="2026-10-20T12:00:00"),
    ],
)
def test_funding_approval_route_rejects_malformed_service_output(monkeypatch, mutate):
    malformed = dict(FUNDING_APPROVAL_ROUTE_RESULT)
    mutate(malformed)
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        approval_action=lambda *_args, **_kwargs: malformed,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/approve"
    )
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})

    assert response.status_code == 500
    assert response.json() == {"error": "Solution funding approval unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "private receipt detail" not in response.text


def test_funding_approval_route_declares_exact_create_and_replay_openapi_contract(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT)
    path = "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/approve"
    operation = app.openapi()["paths"][path]["post"]
    components = app.openapi()["components"]["schemas"]

    expected_schema = {
        "$ref": "#/components/schemas/SolutionLifecycleFundingApprovalResponse"
    }
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == expected_schema
    assert operation["responses"]["201"]["content"]["application/json"]["schema"] == expected_schema
    assert set(
        components["SolutionLifecycleFundingApprovalResponse"]["properties"]
    ) == {"funding_case_id", "decision_status", "approved_at", "replayed"}
    assert auth_route_policy(
        "POST", f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/{RESULT['funding_case_id']}/approve",
        enabled=True,
    ) == {
        "resource": "solution_lifecycle", "action": "review", "public": False,
        "location_id": LOCATION_ID, "scope_required": True, "operator_auth": True,
    }


def test_funding_approval_route_maps_tenant_denial_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        approval_action=lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/approve"
    )
    with TestClient(app) as client:
        response = client.post(path, json={"request_id": REQUEST_ID, "acknowledged": True})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_funding_tranche_review_and_approval_routes_are_private_and_exact(monkeypatch):
    calls = []
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        tranche_detail_action=lambda *args: calls.append(("detail", args)) or TRANCHE_REVIEW_DETAIL,
        tranche_approval_action=lambda *args: calls.append(("approve", args)) or TRANCHE_RESULT,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    base = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/tranches/{TRANCHE_RESULT['tranche_id']}"
    )
    with TestClient(app) as client:
        detail_response = client.get(f"{base}/review")
        approval_response = client.post(
            f"{base}/approve", json={"request_id": REQUEST_ID, "acknowledged": True}
        )
        malformed = client.post(
            f"{base}/approve", json={"request_id": REQUEST_ID, "acknowledged": True, "amount": 300}
        )
    assert detail_response.status_code == 200
    assert detail_response.json() == TRANCHE_REVIEW_DETAIL
    assert detail_response.headers["cache-control"] == "no-store"
    assert approval_response.status_code == 201
    assert approval_response.json() == TRANCHE_RESULT
    assert approval_response.headers["cache-control"] == "no-store"
    assert malformed.status_code == 400
    assert calls == [
        ("detail", (OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"], TRANCHE_RESULT["tranche_id"])),
        ("approve", (
            OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"],
            TRANCHE_RESULT["tranche_id"], REQUEST_ID, True,
        )),
    ]


def test_funding_tranche_review_declares_exact_openapi_response(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT)

    response_schema = app.openapi()["paths"][
        "/operator/api/solution-lifecycle/{location_id}/funding/{funding_case_id}/tranches/{tranche_id}/review"
    ]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert response_schema == {
        "$ref": "#/components/schemas/SolutionLifecycleFundingTrancheReviewDetailResponse"
    }
    properties = app.openapi()["components"]["schemas"][
        "SolutionLifecycleFundingTrancheReviewDetailResponse"
    ]["properties"]
    assert set(properties) == set(TRANCHE_REVIEW_DETAIL)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda result: result.update(tranche_id=str(uuid4())),
        lambda result: result.update(unexpected="private detail"),
        lambda result: result.update(milestone_conditions={"invalid": float("nan")}),
    ],
)
def test_funding_tranche_review_rejects_malformed_service_output(monkeypatch, mutate):
    malformed = dict(TRANCHE_REVIEW_DETAIL)
    mutate(malformed)
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        tranche_detail_action=lambda *_args: malformed,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/tranches/{TRANCHE_RESULT['tranche_id']}/review"
    )
    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 500
    assert response.json() == {"error": "Solution funding tranche review unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_funding_review_routes_are_private_no_store_and_call_review_readers(monkeypatch):
    queue = {**FUNDING_REVIEW_QUEUE_PAGE, "offset": 5}
    detail = FUNDING_REVIEW_DETAIL
    calls = []
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        review_queue_action=lambda *args, **kwargs: calls.append(("queue", args, kwargs)) or queue,
        review_detail_action=lambda *args, **kwargs: calls.append(("detail", args, kwargs)) or detail,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    queue_path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/review?limit=10&offset=5"
    detail_path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/review"
    )
    with TestClient(app) as client:
        queue_response = client.get(queue_path)
        detail_response = client.get(detail_path)
    assert queue_response.status_code == 200
    assert queue_response.json() == jsonable_encoder(queue)
    assert detail_response.status_code == 200
    assert detail_response.json() == jsonable_encoder(detail)
    assert queue_response.headers["cache-control"] == "no-store"
    assert detail_response.headers["cache-control"] == "no-store"
    assert calls == [
        ("queue", (OPERATOR_ID, LOCATION_ID), {"limit": 10, "offset": 5}),
        ("detail", (OPERATOR_ID, LOCATION_ID, RESULT["funding_case_id"]), {}),
    ]


def test_funding_review_routes_declare_exact_migration_490_openapi_contract(monkeypatch):
    app = _app(object(), monkeypatch, lambda *_args, **_kwargs: RESULT)
    paths = app.openapi()["paths"]
    components = app.openapi()["components"]["schemas"]
    queue_path = "/operator/api/solution-lifecycle/{location_id}/funding/review"
    detail_path = (
        "/operator/api/solution-lifecycle/{location_id}/funding/"
        "{funding_case_id}/review"
    )

    assert paths[queue_path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {
        "$ref": "#/components/schemas/SolutionLifecycleFundingReviewQueueResponse"
    }
    assert paths[detail_path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {
        "$ref": "#/components/schemas/SolutionLifecycleFundingReviewDetailResponse"
    }
    assert set(components["SolutionLifecycleFundingReviewQueueResponse"]["properties"]) == {
        "location_id", "offset", "funding_cases", "has_more", "next_offset"
    }
    assert set(
        components["SolutionLifecycleFundingReviewQueueItemResponse"]["properties"]
    ) == set(FUNDING_REVIEW_QUEUE_ITEM)
    assert set(
        components["SolutionLifecycleFundingReviewDetailResponse"]["properties"]
    ) == set(FUNDING_REVIEW_DETAIL)
    for name in (
        "SolutionLifecycleFundingReviewQueueItemResponse",
        "SolutionLifecycleFundingReviewDetailResponse",
    ):
        assert not {
            "reviewer_operator_id", "reviewer_party_id", "reviewed_by_party_id"
        } & set(components[name]["properties"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda page: page.update(location_id=str(uuid4())),
        lambda page: page.update(offset=4),
        lambda page: page.update(has_more=True, next_offset=999),
        lambda page: page.update(funding_cases=[page["funding_cases"][0]] * 2),
        lambda page: page.update(
            funding_cases=[
                {
                    **deepcopy(FUNDING_REVIEW_QUEUE_ITEM),
                    "funding_case_id": str(uuid4()),
                    "created_at": datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
                },
                {
                    **deepcopy(FUNDING_REVIEW_QUEUE_ITEM),
                    "funding_case_id": str(uuid4()),
                    "created_at": datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc),
                },
            ]
        ),
    ],
)
def test_funding_review_queue_rejects_malformed_or_unbound_pages(monkeypatch, mutate):
    malformed = deepcopy(FUNDING_REVIEW_QUEUE_PAGE)
    mutate(malformed)
    app = _app(
        object(),
        monkeypatch,
        lambda *_args, **_kwargs: RESULT,
        review_queue_action=lambda *_args, **_kwargs: malformed,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/review?limit=2"
        )
    assert response.status_code == 500
    assert response.json() == {"error": "Solution funding review queue unavailable"}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda detail: detail.update(funding_case_id=str(uuid4())),
        lambda detail: detail.update(unexpected="private reviewer data"),
        lambda detail: detail.update(evidence=[{"score": float("nan")}]),
        lambda detail: detail.update(rationale="x" * 4001),
        lambda detail: detail.update(
            maximum_authorized_amount=Decimal("10000000000000.00")
        ),
        lambda detail: detail.update(maximum_authorized_amount=Decimal("900.00")),
    ],
)
def test_funding_review_detail_rejects_malformed_or_unbound_results(
    monkeypatch, mutate
):
    malformed = deepcopy(FUNDING_REVIEW_DETAIL)
    mutate(malformed)
    app = _app(
        object(),
        monkeypatch,
        lambda *_args, **_kwargs: RESULT,
        review_detail_action=lambda *_args, **_kwargs: malformed,
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = (
        f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/"
        f"{RESULT['funding_case_id']}/review"
    )
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 500
    assert response.json() == {"error": "Solution funding review detail unavailable"}
    assert response.headers["cache-control"] == "no-store"


def test_funding_review_tenant_denial_maps_to_forbidden(monkeypatch):
    app = _app(
        object(), monkeypatch, lambda *_args, **_kwargs: RESULT,
        review_queue_action=lambda *_a, **_k: (_ for _ in ()).throw(TenantContextDenied("denied")),
    )

    @app.middleware("http")
    async def operator_context(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    path = f"/operator/api/solution-lifecycle/{LOCATION_ID}/funding/review"
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
