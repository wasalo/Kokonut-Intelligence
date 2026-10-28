"""Tests for the location-scoped operating-pilot Gateway projection."""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import operating_pilot_reads as reads
from services.gateway.operator_auth import auth_route_policy

pytest.importorskip("fastapi")
from fastapi import APIRouter, FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

OPERATOR_ID = str(uuid4())
LOCATION_ID = str(uuid4())
SUMMARY = {
    "scope_configured": True,
    "capacity_profiles": {
        "suppressed": False, "submitted": 1, "approved": 2, "available_hours": 30,
    },
    "demand_signals": {"submitted": 1, "required_hours": 20},
    "work_items": {"total": 2, "open": 1, "claimed": 1},
    "work_claims": {"suppressed": False, "proposed": 1, "accepted": 1},
    "competency_reviews": {"suppressed": False, "submitted": 1, "verified": 2, "open_gap": 2},
    "learning_plans": {"suppressed": False, "active": 3},
    "resource_requests": {"suppressed": False, "pending": 3},
    "aggregate_only_coaching_sessions": {"suppressed": False, "count": 3},
}


class _Connection:
    def __init__(self, row):
        self.row = row
        self.operations = []
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
        self.connection.operations.append((" ".join(query.split()), params))

    def fetchone(self):
        return (self.connection.row,)


def test_summary_sets_exact_context_and_read_only_transaction():
    connection = _Connection(SUMMARY)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_summary(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_summary" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID,)
    assert result == {"location_id": LOCATION_ID, **SUMMARY}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("operator_id,location_id", [
    ("not-a-uuid", LOCATION_ID), (OPERATOR_ID, "not-a-uuid"),
])
def test_invalid_identifiers_fail_before_database_access(operator_id, location_id):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_summary(
            operator_id, location_id,
            connection_factory=lambda: pytest.fail("invalid identity must fail before DB access"),
        )


def test_tenant_denial_rolls_back_without_calling_summary():
    connection = _Connection(SUMMARY)

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_summary(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_summary" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_demand_page_uses_exact_context_read_only_transaction_and_bounds():
    page = {
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [{
            "work_type": "harvest",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "required_hours": 8,
            "priority": "high",
            "status": "approved",
        }],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_demand_signals(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_demand_signals" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_demand_page_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_demand_signals(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_demand_page_tenant_denial_rolls_back_without_calling_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_demand_signals(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_demand_signals" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_capacity_page_uses_exact_context_read_only_transaction_and_bounds():
    page = {
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [{
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "suppressed": False,
            "available_hours": 30,
            "committed_hours": 12,
            "protected_hours": 4,
        }],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_capacity_periods(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_capacity_periods" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_capacity_page_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_capacity_periods(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_capacity_page_tenant_denial_rolls_back_without_calling_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_capacity_periods(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_capacity_periods" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_own_capacity_page_uses_separate_exact_grant_and_returns_bounded_private_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "profile_id": str(uuid4()),
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "available_hours": 40,
            "committed_hours": 10,
            "protected_hours": 5,
            "notes": "private note for this operator only",
            "source": "self_reported",
            "status": "draft",
            "updated_at": "2026-10-22T00:00:00Z",
        }],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_capacity_profiles(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_capacity_profiles" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_capacity_page_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_capacity_profiles(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_capacity_page_tenant_denial_rolls_back_without_calling_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_capacity_profiles(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_own_capacity_profiles" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_own_competency_history_uses_read_own_context_and_returns_bounded_private_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "draft_id": str(uuid4()),
            "competency_key": "facilitation",
            "current_level": 2.5,
            "target_level": 4,
            "evidence_note": "private self-assessment note",
            "status": "draft",
        }],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_competency_drafts(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_competency_drafts" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_competency_history_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_competency_drafts(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_competency_history_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_competency_drafts(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_own_competency_drafts" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_capacity_review_queue_uses_review_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "profile_id": str(uuid4()),
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "available_hours": 40,
            "committed_hours": 10,
            "protected_hours": 5,
            "status": "submitted",
            "updated_at": "2026-10-22T00:00:00Z",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_capacity_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=2,
            offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_capacity_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_capacity_review_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_capacity_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_capacity_review_queue_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_capacity_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_capacity_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_demand_review_queue_uses_review_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "signal_id": str(uuid4()),
            "work_type": "harvest",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "required_hours": 40,
            "priority": "high",
            "status": "submitted",
            "updated_at": "2026-10-22T00:00:00Z",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_demand_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_demand_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_demand_review_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_demand_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_demand_review_queue_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_demand_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_demand_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_resource_review_queue_uses_review_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "resource_request_id": str(uuid4()),
            "resource_type": "irrigation pump",
            "description": "Private details needed by the authorized reviewer",
            "urgency": "high",
            "requested_by": "2026-11-15",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_resource_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_resource_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_resource_review_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_resource_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_resource_review_queue_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_resource_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_resource_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_resource_fulfillment_queue_uses_fulfill_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "resource_request_id": str(uuid4()),
            "resource_type": "irrigation pump",
            "description": "Synthetic approved request",
            "urgency": "high",
            "requested_by": "2026-11-15",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_resource_fulfillment_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "fulfill",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_resource_fulfillment_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_resource_fulfillment_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_resource_fulfillment_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_resource_fulfillment_queue_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_resource_fulfillment_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_resource_fulfillment_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_work_claim_page_uses_exact_context_read_only_transaction_and_bounds():
    page = {
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [{"work_type": "harvest", "suppressed": False, "claim_count": 5}],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_work_claims(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_work_claims" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_work_claim_page_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_work_claims(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_work_claim_page_tenant_denial_rolls_back_without_calling_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_work_claims(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_work_claims" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_resource_category_page_uses_exact_context_and_bounded_read_transaction():
    page = {
        "scope_configured": True,
        "limit": 2,
        "offset": 4,
        "items": [{"resource_category": "equipment", "suppressed": False, "request_count": 5}],
        "has_more": False,
        "next_offset": None,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_resource_categories(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_resource_categories" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_resource_category_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_resource_categories(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_resource_category_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_resource_categories(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_resource_categories" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_projection_contract_is_aggregate_and_excludes_personal_fields():
    assert "capacity_profiles" in SUMMARY
    assert "work_claims" in SUMMARY
    assert "competency_reviews" in SUMMARY
    assert "aggregate_only_coaching_sessions" in SUMMARY
    assert SUMMARY["capacity_profiles"]["suppressed"] is False
    assert SUMMARY["aggregate_only_coaching_sessions"]["count"] == 3
    assert not any(field in " ".join(SUMMARY).lower() for field in (
        "party_id", "claimant", "coachee", "notes", "evidence", "hours_by_person",
    ))


def test_route_policy_requires_exact_location_operating_pilot_read_grant():
    path = f"/operator/api/operating-pilot/{LOCATION_ID}/summary"
    assert auth_route_policy("GET", path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", path, enabled=True) is None
    assert auth_route_policy("GET", path + "/extra", enabled=True) is None

    review_path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-review-queue"
    assert auth_route_policy("GET", review_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "review",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", review_path, enabled=True) is None
    assert auth_route_policy("GET", review_path + "/extra", enabled=True) is None

    demand_path = f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals"
    assert auth_route_policy("GET", demand_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", demand_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "create",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("GET", demand_path + "/extra", enabled=True) is None

    capacity_path = f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-periods"
    assert auth_route_policy("GET", capacity_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", capacity_path, enabled=True) is None
    assert auth_route_policy("GET", capacity_path + "/extra", enabled=True) is None

    own_competency_path = (
        f"/operator/api/operating-pilot/{LOCATION_ID}/my-competency-assessments"
    )
    assert auth_route_policy("GET", own_competency_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read_own",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", own_competency_path, enabled=True) is None
    assert auth_route_policy("GET", own_competency_path + "/extra", enabled=True) is None
    assert auth_route_policy("GET", own_competency_path, enabled=False) is None

    claims_path = f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims"
    assert auth_route_policy("GET", claims_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", claims_path, enabled=True) is None
    assert auth_route_policy("GET", claims_path + "/extra", enabled=True) is None

    resources_path = f"/operator/api/operating-pilot/{LOCATION_ID}/resource-categories"
    assert auth_route_policy("GET", resources_path, enabled=True) == {
        "resource": "operating_pilot",
        "action": "read",
        "public": False,
        "location_id": LOCATION_ID,
        "scope_required": True,
        "operator_auth": True,
    }
    assert auth_route_policy("POST", resources_path, enabled=True) is None
    assert auth_route_policy("GET", resources_path + "/extra", enabled=True) is None


def test_http_projection_is_no_store_and_operator_authenticated(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_summary",
        lambda *_args, **_kwargs: {"location_id": LOCATION_ID, **SUMMARY},
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/summary")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json()["scope_configured"] is True


def test_http_projection_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_summary",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query the projection"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/summary")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_demand_page_is_no_store_scoped_and_bounded(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_demand_signals",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_resource_category_route_publishes_strict_openapi_contract():
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(
        router, object(), lambda *_args, **_kwargs: None, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    schema = app.openapi()
    operation = schema["paths"][
        "/operator/api/operating-pilot/{location_id}/resource-categories"
    ]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OperatingPilotResourceCategoryPage"
    }
    response_schema = schema["components"]["schemas"][
        "OperatingPilotResourceCategoryPage"
    ]
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["required"]) == {
        "location_id",
        "scope_configured",
        "limit",
        "offset",
        "items",
        "has_more",
        "next_offset",
    }


@pytest.mark.parametrize(
    "invalid_page",
    [
        {
            "location_id": LOCATION_ID,
            "scope_configured": True,
            "limit": 7,
            "offset": 14,
            "items": [{
                "resource_category": "equipment",
                "suppressed": False,
                "request_count": 5,
                "distinct_requesters": 5,
            }],
            "has_more": False,
            "next_offset": None,
        },
        {
            "location_id": str(uuid4()),
            "scope_configured": True,
            "limit": 7,
            "offset": 14,
            "items": [],
            "has_more": False,
            "next_offset": None,
        },
        {
            "location_id": LOCATION_ID,
            "scope_configured": True,
            "limit": 7,
            "offset": 14,
            "items": [{
                "resource_category": "equipment",
                "suppressed": True,
                "request_count": 5,
            }],
            "has_more": False,
            "next_offset": None,
        },
        {
            "location_id": LOCATION_ID,
            "scope_configured": True,
            "limit": 6,
            "offset": 14,
            "items": [],
            "has_more": False,
            "next_offset": None,
        },
    ],
)
def test_resource_category_route_sanitizes_invalid_or_private_projection(
    monkeypatch, invalid_page
):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_categories",
        lambda *_args, **_kwargs: invalid_page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(
        router, object(), run_in_threadpool, SimpleNamespace(Error=Exception)
    )
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-categories?limit=7&offset=14"
        )

    assert response.status_code == 500
    assert response.json() == {"error": "Operating resource read unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert "distinct_requesters" not in response.text


def test_http_demand_page_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_demand_signals",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query demand"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/demand-signals")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_capacity_page_is_no_store_scoped_and_bounded(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_periods",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-periods?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_capacity_page_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_periods",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query capacity"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-periods")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_own_capacity_page_is_no_store_and_uses_exact_operator_scope(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {
        "location_id": LOCATION_ID,
        "items": [{"status": "draft", "notes": "only this operator's note"}],
        "has_more": False,
    }
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_capacity_profiles",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-capacity-profiles?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_own_capacity_page_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_capacity_profiles",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query own capacity"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/my-capacity-profiles")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_own_competency_history_is_no_store_and_uses_exact_operator_scope(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {
        "location_id": LOCATION_ID,
        "items": [{"competency_key": "facilitation", "evidence_note": "private note"}],
        "has_more": False,
    }
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_competency_drafts",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-competency-assessments"
            "?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_own_competency_history_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_competency_drafts",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query competency history"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-competency-assessments"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_capacity_review_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_review_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-review-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_capacity_review_queue_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_capacity_review_queue",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query the review queue"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/capacity-review-queue")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_competency_review_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_competency_review_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/competency-review-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_competency_review_queue_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_competency_review_queue",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query competency review"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/competency-review-queue")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_competency_review_queue_uses_review_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "draft_id": str(uuid4()),
            "competency_key": "facilitation",
            "current_level": 2.5,
            "target_level": 4,
            "evidence_note": "Private evidence for authorized review",
            "status": "submitted",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_competency_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_competency_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_competency_review_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_competency_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_competency_review_queue_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_competency_review_queue(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_competency_review_queue" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_http_demand_review_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_demand_review_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/demand-review-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_resource_review_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_review_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-review-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_resource_fulfillment_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_fulfillment_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-fulfillment-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_resource_fulfillment_queue_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_fulfillment_queue",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query fulfillment queue"),
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, None, run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-fulfillment-queue"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_work_claim_page_is_no_store_scoped_and_bounded(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_work_claims",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_work_claim_page_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_work_claims",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query work claims"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_http_resource_category_page_is_no_store_scoped_and_oidc_protected(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {
        "location_id": LOCATION_ID,
        "scope_configured": True,
        "limit": 7,
        "offset": 14,
        "items": [],
        "has_more": False,
        "next_offset": None,
    }
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_categories",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/resource-categories?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_resource_category_page_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_resource_categories",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query resource categories"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/resource-categories")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "error,status_code",
    [
        (TenantContextDenied("denied"), 403),
        (reads.OperatingPilotReadInvalid("invalid page"), 400),
        (type("PermissionDenied", (Exception,), {"pgcode": "42501"})("denied"), 403),
    ],
)
def test_http_work_claim_page_maps_denials_to_no_store_responses(
    monkeypatch, error, status_code,
):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_work_claims",
        fail,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/work-claims")
    assert response.status_code == status_code
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_own_demand_history_uses_read_own_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "signal_id": str(uuid4()),
            "work_type": "harvest",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "required_hours": 40,
            "priority": "high",
            "description": "private planning note",
            "status": "submitted",
            "created_at": "2026-10-01T00:00:00Z",
            "updated_at": "2026-10-22T00:00:00Z",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_demand_signals(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_demand_signals" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_demand_history_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_demand_signals(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_demand_history_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_demand_signals(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_own_demand_signals" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_http_own_demand_history_is_no_store_scoped_and_bounded(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_demand_signals",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_own_demand_history_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_demand_signals",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query own demand"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "error,status_code",
    [
        (TenantContextDenied("denied"), 403),
        (reads.OperatingPilotReadInvalid("invalid page"), 400),
        (type("PermissionDenied", (Exception,), {"pgcode": "42501"})("denied"), 403),
    ],
)
def test_http_own_demand_history_maps_denials_to_no_store_responses(
    monkeypatch, error, status_code,
):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_demand_signals",
        fail,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(f"/operator/api/operating-pilot/{LOCATION_ID}/my-demand-signals")
    assert response.status_code == status_code
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"


def test_own_resource_history_uses_read_own_context_and_bounded_read_only_transaction():
    page = {
        "items": [{"resource_type": "irrigation", "description": "private request"}],
        "limit": 2,
        "offset": 4,
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_own_resource_requests(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "read_own",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_own_resource_requests" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_own_resource_history_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_own_resource_requests(
            OPERATOR_ID, LOCATION_ID, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_own_resource_history_tenant_denial_rolls_back_without_projection():
    connection = _Connection({})

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("denied")

    with patch.object(reads, "set_operator_tenant_context", deny):
        with pytest.raises(TenantContextDenied):
            reads.get_location_operating_pilot_own_resource_requests(
                OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection,
            )
    assert not any("location_operating_pilot_own_resource_requests" in query
                   for query, _ in connection.operations)
    assert connection.rolled_back and connection.closed


def test_http_own_resource_history_is_no_store_scoped_and_bounded(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_resource_requests",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-resource-requests?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_own_resource_history_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_own_resource_requests",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query own resources"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/my-resource-requests"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_learning_plan_review_queue_uses_review_context_and_read_only_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "learning_plan_id": str(uuid4()),
            "title": "Soil-care learning plan",
            "competency_goals": [{"key": "soil-care"}],
            "support_requested": ["Peer coach"],
            "target_date": "2027-04-01",
            "status": "submitted",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_learning_plan_review_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "review",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_learning_plan_review_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_learning_plan_review_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_learning_plan_review_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must fail before DB access"),
        )


def test_http_learning_plan_review_queue_is_no_store_and_exactly_scoped(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_learning_plan_review_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_in_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_in_threadpool,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-review-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]


def test_http_learning_plan_review_queue_fails_closed_when_oidc_is_disabled(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_learning_plan_review_queue",
        lambda *_args, **_kwargs: pytest.fail("disabled OIDC must not query learning-plan review"),
    )
    app = FastAPI()
    router = APIRouter()
    register_operating_pilot_routes(router, None, lambda *_args: None,
                                    SimpleNamespace(Error=Exception))
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-review-queue"
        )
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_learning_plan_activation_queue_sets_exact_context_read_only_and_bounded_page():
    page = {
        "limit": 2,
        "offset": 4,
        "items": [{
            "learning_plan_id": str(uuid4()),
            "title": "Approved plan",
            "status": "submitted",
            "submitted_at": "2026-10-24T12:00:00+00:00",
            "approved_at": "2026-10-24T13:00:00+00:00",
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    }
    connection = _Connection(page)
    contexts = []

    def set_context(conn, **kwargs):
        assert conn is connection
        contexts.append(kwargs)

    with patch.object(reads, "set_operator_tenant_context", set_context):
        result = reads.get_location_operating_pilot_learning_plan_activation_queue(
            OPERATOR_ID, LOCATION_ID, limit=2, offset=4,
            connection_factory=lambda: connection,
        )

    assert contexts == [{
        "operator_id": OPERATOR_ID,
        "location_id": LOCATION_ID,
        "resource": "operating_pilot",
        "action": "activate",
    }]
    assert [query for query, _ in connection.operations[:3]] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '8s'",
        "SET LOCAL lock_timeout = '2s'",
    ]
    assert "location_operating_pilot_learning_plan_activation_queue" in connection.operations[-1][0]
    assert connection.operations[-1][1] == (LOCATION_ID, 2, 4)
    assert result == {"location_id": LOCATION_ID, **page}
    assert connection.rolled_back and connection.closed


@pytest.mark.parametrize("limit,offset", [
    (0, 0), (51, 0), (True, 0), (25, -1), (25, 10001), (25, False),
])
def test_learning_plan_activation_queue_invalid_bounds_fail_before_database_access(limit, offset):
    with pytest.raises(reads.OperatingPilotReadInvalid):
        reads.get_location_operating_pilot_learning_plan_activation_queue(
            OPERATOR_ID,
            LOCATION_ID,
            limit=limit,
            offset=offset,
            connection_factory=lambda: pytest.fail("invalid activation page must not open DB"),
        )


def test_http_learning_plan_activation_queue_uses_its_exact_grant(monkeypatch):
    from services.gateway.operating_pilot_routes import register_operating_pilot_routes

    calls = []
    page = {"location_id": LOCATION_ID, "items": [], "has_more": False}
    monkeypatch.setattr(
        "services.gateway.operating_pilot_reads.get_location_operating_pilot_learning_plan_activation_queue",
        lambda *args, **kwargs: calls.append((args, kwargs)) or page,
    )
    app = FastAPI()
    router = APIRouter()

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    register_operating_pilot_routes(router, object(), run_inline, SimpleNamespace(Error=Exception))
    app.include_router(router)

    @app.middleware("http")
    async def add_operator(request, call_next):
        request.state.operator_session = SimpleNamespace(
            operator=SimpleNamespace(operator_id=OPERATOR_ID)
        )
        return await call_next(request)

    with TestClient(app) as client:
        response = client.get(
            f"/operator/api/operating-pilot/{LOCATION_ID}/learning-plan-activation-queue?limit=7&offset=14"
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.json() == page
    assert calls == [((OPERATOR_ID, LOCATION_ID), {"limit": 7, "offset": 14})]
