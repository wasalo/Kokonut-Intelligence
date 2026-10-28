"""Focused contracts for independent location-scoped pollinator review."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.gateway import pollinator_health_reads, pollinator_health_writes
from services.gateway.pollinator_health_writes import PollinatorObservationInvalid

_OPERATOR = "11111111-1111-4111-8111-111111111111"
_LOCATION = "22222222-2222-4222-8222-222222222222"
_RECORD = "33333333-3333-4333-8333-333333333333"
_UPDATED_AT = "2026-10-25T12:34:56.123456+00:00"


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.one = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        self.one = (self.connection.result,)

    def fetchone(self):
        return self.one


class Connection:
    def __init__(self, result):
        self.result = result
        self.queries = []
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


def review_payload(**changes):
    return {
        "request_id": str(uuid4()),
        "expected_updated_at": _UPDATED_AT,
        "decision": "reviewed",
        "reason": "Independent field review completed",
        **changes,
    }


def test_review_queue_sets_review_context_and_validates_bounded_response(monkeypatch):
    now = datetime(2026, 10, 25, 12, 34, tzinfo=timezone.utc)
    connection = Connection({
        "location_id": _LOCATION,
        "limit": 10,
        "offset": 0,
        "items": [{
            "record_id": _RECORD,
            "record_type": "observation",
            "occurred_on": "2026-10-24",
            "status": "recorded",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "details": {"pollinator_type": "wild_bee", "count": 10, "notes": "Private reviewer note"},
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    })
    context = {}
    monkeypatch.setattr(
        pollinator_health_reads, "set_operator_tenant_context",
        lambda *_args, **kwargs: context.update(kwargs),
    )

    result = pollinator_health_reads.list_location_pollinator_review_queue(
        _OPERATOR, _LOCATION, limit=10, offset=0, connection_factory=lambda: connection
    )

    assert context == {
        "operator_id": _OPERATOR, "location_id": _LOCATION,
        "resource": "pollinator_health", "action": "review",
    }
    assert result["items"][0]["record_id"] == _RECORD
    assert result["items"][0]["updated_at"] == now.isoformat()
    assert connection.queries[-1][0].startswith("SELECT kokonut_security.list_location_pollinator_review_queue(")
    assert connection.rollbacks == 1 and connection.closed


@pytest.mark.parametrize(("offset", "expected_more", "expected_next"), [
    (9975, True, 10000),
    (10000, False, None),
])
def test_review_queue_stops_continuation_at_supported_offset_ceiling(
    monkeypatch, offset, expected_more, expected_next
):
    item = {
        "record_id": _RECORD,
        "record_type": "observation",
        "occurred_on": "2026-10-24",
        "status": "recorded",
        "created_at": _UPDATED_AT,
        "updated_at": _UPDATED_AT,
        "details": {
            "pollinator_type": "wild_bee", "count": 10, "method": "transect",
            "duration_minutes": 20, "species_name": "Native bee", "notes": "Field note",
        },
    }
    limit = 25
    connection = Connection({
        "location_id": _LOCATION,
        "limit": limit,
        "offset": offset,
        "items": [item] * limit,
        "has_more": True,
        "next_offset": offset + limit,
        "total": offset + limit + 1,
    })
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **_kw: None)

    result = pollinator_health_reads.list_location_pollinator_review_queue(
        _OPERATOR, _LOCATION, limit=limit, offset=offset,
        connection_factory=lambda: connection,
    )

    assert result["has_more"] is expected_more
    assert result["next_offset"] == expected_next


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (1, -1), (1, 10001), (True, 0)])
def test_review_queue_rejects_invalid_page_before_connecting(limit, offset):
    with pytest.raises(ValueError):
        pollinator_health_reads.list_location_pollinator_review_queue(
            _OPERATOR, _LOCATION, limit=limit, offset=offset,
            connection_factory=lambda: pytest.fail("invalid page must not connect"),
        )


def test_review_queue_rejects_foreign_location_result_and_closes_connection(monkeypatch):
    connection = Connection({
        "location_id": str(uuid4()), "limit": 25, "offset": 0,
        "items": [], "has_more": False, "next_offset": None, "total": 0,
    })
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="invalid result"):
        pollinator_health_reads.list_location_pollinator_review_queue(
            _OPERATOR, _LOCATION, connection_factory=lambda: connection
        )
    assert connection.rollbacks == 1 and connection.closed


def test_review_queue_accepts_only_the_bounded_hive_inspection_projection(monkeypatch):
    now = datetime(2026, 10, 25, 12, 34, tzinfo=timezone.utc)
    connection = Connection({
        "location_id": _LOCATION,
        "limit": 25,
        "offset": 0,
        "items": [{
            "record_id": _RECORD,
            "record_type": "hive_inspection",
            "occurred_on": "2026-10-24",
            "status": "recorded",
            "created_at": now,
            "updated_at": now,
            "details": {
                "hive_id": "Hive-7", "colony_strength": "moderate",
                "colony_strength_score": 6, "queen_seen": True,
                "varroa_count": 2, "swarm_cells": False,
                "notes": "Observation only",
            },
        }],
        "has_more": False,
        "next_offset": None,
        "total": 1,
    })
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **_kw: None)

    result = pollinator_health_reads.list_location_pollinator_review_queue(
        _OPERATOR, _LOCATION, connection_factory=lambda: connection
    )

    assert result["items"][0]["record_type"] == "hive_inspection"
    assert result["items"][0]["details"]["hive_id"] == "Hive-7"
    assert connection.closed and connection.rollbacks == 1


def test_review_queue_rejects_unexpected_hive_inspection_fields(monkeypatch):
    now = datetime(2026, 10, 25, 12, 34, tzinfo=timezone.utc)
    connection = Connection({
        "location_id": _LOCATION, "limit": 25, "offset": 0,
        "items": [{
            "record_id": _RECORD, "record_type": "hive_inspection",
            "occurred_on": "2026-10-24", "status": "recorded",
            "created_at": now, "updated_at": now,
            "details": {"api_key": "secret"},
        }],
        "has_more": False, "next_offset": None, "total": 1,
    })
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="unexpected detail field"):
        pollinator_health_reads.list_location_pollinator_review_queue(
            _OPERATOR, _LOCATION, connection_factory=lambda: connection
        )
    assert connection.closed and connection.rollbacks == 1


@pytest.mark.parametrize("created_at", ["not-a-timestamp", "2026-10-25T12:34:00"])
def test_review_queue_rejects_invalid_json_timestamp_values(monkeypatch, created_at):
    connection = Connection({
        "location_id": _LOCATION, "limit": 25, "offset": 0,
        "items": [{
            "record_id": _RECORD, "record_type": "observation",
            "occurred_on": "2026-10-24", "status": "recorded",
            "created_at": created_at, "updated_at": "2026-10-25T12:34:00+00:00",
            "details": {"count": 1},
        }],
        "has_more": False, "next_offset": None, "total": 1,
    })
    monkeypatch.setattr(pollinator_health_reads, "set_operator_tenant_context", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="timestamp"):
        pollinator_health_reads.list_location_pollinator_review_queue(
            _OPERATOR, _LOCATION, connection_factory=lambda: connection
        )
    assert connection.closed and connection.rollbacks == 1


def test_review_normalizes_input_before_connecting_and_requires_reason_and_timezone():
    with pytest.raises(PollinatorObservationInvalid, match="reason is required"):
        pollinator_health_writes._normalize_pollinator_review_payload(review_payload(reason="  "))
    with pytest.raises(PollinatorObservationInvalid, match="include a timezone"):
        pollinator_health_writes._normalize_pollinator_review_payload(
            review_payload(expected_updated_at="2026-10-25T12:34:56")
        )
    with pytest.raises(PollinatorObservationInvalid, match="Unsupported pollinator review decision"):
        pollinator_health_writes._normalize_pollinator_review_payload(
            review_payload(decision="approved")
        )


def test_review_calls_exact_location_function_and_commits(monkeypatch):
    decision_id = str(uuid4())
    connection = Connection({
        "decision_id": decision_id, "location_id": _LOCATION,
        "record_type": "pesticide_impact", "record_id": _RECORD,
        "status": "dismissed", "replayed": False,
    })
    context = {}
    monkeypatch.setattr(
        pollinator_health_writes, "set_operator_tenant_context",
        lambda *_args, **kwargs: context.update(kwargs),
    )

    result = pollinator_health_writes.review_location_pollinator_record(
        _OPERATOR, _LOCATION, "pesticide_impact", _RECORD,
        review_payload(decision="dismissed"),
        connection_factory=lambda: connection,
    )

    assert context == {
        "operator_id": _OPERATOR, "location_id": _LOCATION,
        "resource": "pollinator_health", "action": "review",
    }
    assert result["decision_id"] == decision_id
    assert connection.queries[-1][0].startswith("SELECT kokonut_security.review_location_pollinator_record(")
    assert connection.queries[-1][1][1:3] == ("pesticide_impact", _RECORD)
    assert connection.commits == 1 and connection.rollbacks == 0 and connection.closed


@pytest.mark.parametrize("record_type", ["habitat", "hive", "pesticide", "unknown", None])
def test_review_rejects_unsupported_record_type_before_connecting(record_type):
    with pytest.raises(PollinatorObservationInvalid, match="Unsupported pollinator record type"):
        pollinator_health_writes.review_location_pollinator_record(
            _OPERATOR, _LOCATION, record_type, _RECORD, review_payload(),
            connection_factory=lambda: pytest.fail("unsupported record type must not connect"),
        )


def test_review_rolls_back_database_failure_and_keeps_retry_receipt(monkeypatch):
    class FailingCursor(Cursor):
        def execute(self, query, params=None):
            self.connection.queries.append((query, params))
            raise RuntimeError("synthetic failure")

    class FailingConnection(Connection):
        def cursor(self):
            return FailingCursor(self)

    connection = FailingConnection(None)
    monkeypatch.setattr(pollinator_health_writes, "set_operator_tenant_context", lambda *_a, **_kw: None)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        pollinator_health_writes.review_location_pollinator_record(
            _OPERATOR, _LOCATION, "observation", _RECORD, review_payload(),
            connection_factory=lambda: connection,
        )
    assert connection.commits == 0 and connection.rollbacks == 1 and connection.closed


def test_hive_inspection_review_uses_its_bounded_database_function(monkeypatch):
    decision_id = str(uuid4())
    connection = Connection({
        "decision_id": decision_id, "location_id": _LOCATION,
        "record_type": "hive_inspection", "record_id": _RECORD,
        "status": "reviewed", "replayed": False,
    })
    monkeypatch.setattr(pollinator_health_writes, "set_operator_tenant_context", lambda *_a, **_kw: None)

    result = pollinator_health_writes.review_location_pollinator_record(
        _OPERATOR, _LOCATION, "hive_inspection", _RECORD, review_payload(),
        connection_factory=lambda: connection,
    )

    assert result["record_type"] == "hive_inspection"
    assert connection.queries[-1][0].startswith(
        "SELECT kokonut_security.review_location_pollinator_hive_inspection("
    )
    assert connection.queries[-1][1][0:2] == (_LOCATION, _RECORD)
    assert connection.commits == 1 and connection.closed
