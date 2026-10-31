"""The private metric Gateway keeps signed scope and responses on one connection."""

from datetime import date
from uuid import UUID, uuid4

import pytest

from services.gateway.metric_value_contracts import MetricValueListResponse
from services.gateway.metric_value_reads import (
    MetricValueReadInvalid,
    list_location_metric_values,
)
from services.gateway.metric_value_writes import (
    MetricValueWriteInvalid,
    create_location_metric_value_draft,
    verify_location_metric_value,
)

OPERATOR_ID = str(uuid4())
REVIEWER_ID = str(uuid4())
LOCATION_ID = str(uuid4())
REQUEST_ID = str(uuid4())
METRIC_ID = str(uuid4())
METRIC_VALUE_ID = str(uuid4())


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.connection.result


class _Connection:
    def __init__(self, result):
        self.result = (result,)
        self.queries = []
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


def _compute_receipt(*, created=True):
    return {
        "metric_value_id": METRIC_VALUE_ID,
        "metric_key": "soil_organic_matter",
        "display_name": "Soil organic matter",
        "location_id": LOCATION_ID,
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "value": 3.25,
        "unit": "%",
        "status": "draft",
        "verified": False,
        "request_id": REQUEST_ID,
        "created_at": "2026-02-01T12:00:00Z",
        "created": created,
    }


def test_metric_compute_uses_signed_context_and_bounded_writer(monkeypatch):
    connection = _Connection(_compute_receipt())
    context_calls = []
    monkeypatch.setattr(
        "services.gateway.metric_value_writes.set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )
    monkeypatch.setattr(
        "services.metrics.engine.compute_metric_draft",
        lambda *_args: {
            "location_id": LOCATION_ID,
            "metric_key": "soil_organic_matter",
            "metric_id": METRIC_ID,
            "display_name": "Soil organic matter",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31),
            "value": 3.25,
            "unit": "%",
            "computation_method": "soil_organic_matter",
            "source_record_ids": [],
            "metadata": {},
        },
    )

    result = create_location_metric_value_draft(
        OPERATOR_ID,
        LOCATION_ID,
        REQUEST_ID,
        "soil_organic_matter",
        date(2026, 1, 1),
        date(2026, 1, 31),
        connection_factory=lambda: connection,
    )

    assert result["status"] == "draft" and result["created"] is True
    assert context_calls == [
        (
            connection,
            {
                "operator_id": OPERATOR_ID,
                "location_id": LOCATION_ID,
                "resource": "metric_value",
                "action": "compute",
            },
        )
    ]
    assert "kokonut_security.create_location_metric_value_draft" in connection.queries[-1][0]
    assert connection.committed and not connection.rolled_back and connection.closed


def test_metric_compute_rejects_calculator_scope_mismatch_before_bounded_write(monkeypatch):
    connection = _Connection(_compute_receipt())
    monkeypatch.setattr(
        "services.gateway.metric_value_writes.set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "services.metrics.engine.compute_metric_draft",
        lambda *_args: {
            "location_id": str(uuid4()),
            "metric_key": "soil_organic_matter",
            "metric_id": METRIC_ID,
            "value": 1,
            "unit": "%",
            "computation_method": "method",
            "source_record_ids": [],
            "metadata": {},
        },
    )
    with pytest.raises(MetricValueWriteInvalid, match="mismatched scope"):
        create_location_metric_value_draft(
            OPERATOR_ID,
            LOCATION_ID,
            REQUEST_ID,
            "soil_organic_matter",
            connection_factory=lambda: connection,
        )
    assert not any(
        "create_location_metric_value_draft" in query for query, _ in connection.queries
    )
    assert connection.rolled_back and connection.closed and not connection.committed


def test_metric_verification_uses_reviewer_context_and_bounded_function(monkeypatch):
    receipt = {
        "metric_value_id": METRIC_VALUE_ID,
        "location_id": LOCATION_ID,
        "metric_key": "soil_organic_matter",
        "status": "verified",
        "verified": True,
        "verified_at": "2026-02-02T12:00:00Z",
        "request_id": REQUEST_ID,
        "replayed": False,
    }
    connection = _Connection(receipt)
    context_calls = []
    monkeypatch.setattr(
        "services.gateway.metric_value_writes.set_operator_tenant_context",
        lambda conn, **kwargs: context_calls.append((conn, kwargs)),
    )
    result = verify_location_metric_value(
        REVIEWER_ID,
        LOCATION_ID,
        METRIC_VALUE_ID,
        REQUEST_ID,
        "Reviewed the linked evidence.",
        connection_factory=lambda: connection,
    )
    assert result["verified"] is True
    assert context_calls == [
        (
            connection,
            {
                "operator_id": REVIEWER_ID,
                "location_id": LOCATION_ID,
                "resource": "metric_value",
                "action": "verify",
            },
        )
    ]
    assert "kokonut_security.verify_location_metric_value" in connection.queries[-1][0]
    assert REVIEWER_ID not in connection.queries[-1][0]
    assert connection.committed and connection.closed


def test_metric_list_validates_bound_and_request_bound_page(monkeypatch):
    timestamp = "2026-02-02T12:00:00Z"
    page = {
        "location_id": LOCATION_ID,
        "cursor": "0",
        "limit": 1,
        "next_cursor": None,
        "has_more": False,
        "items": [
            {
                "metric_value_id": METRIC_VALUE_ID,
                "metric_key": "soil_organic_matter",
                "display_name": "Soil organic matter",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "value": 3.25,
                "unit": "%",
                "status": "draft",
                "computed_at": timestamp,
                "verified_at": None,
            }
        ],
    }
    connection = _Connection(page)
    monkeypatch.setattr(
        "services.gateway.metric_value_reads.set_operator_tenant_context",
        lambda *_args, **_kwargs: None,
    )
    result = list_location_metric_values(
        OPERATOR_ID,
        LOCATION_ID,
        "0",
        1,
        connection_factory=lambda: connection,
    )
    assert MetricValueListResponse.model_validate(result).location_id == UUID(LOCATION_ID)
    assert "kokonut_security.list_location_metric_values" in connection.queries[-1][0]
    assert connection.committed and connection.closed

    with pytest.raises(MetricValueReadInvalid):
        list_location_metric_values(
            OPERATOR_ID, LOCATION_ID, "010", 1,
            connection_factory=lambda: (_ for _ in ()).throw(
                AssertionError("invalid page must fail before DB access")
            ),
        )
