"""Focused Gateway contracts for tenant-scoped operational farm activity."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway import farm_activity_records
from services.gateway.farm_activity_records import (
    FarmActivityRecordInvalid,
    create_farm_activity_record,
    edit_farm_activity_record_draft,
    get_farm_activity_record,
    list_farm_activity_records,
    transition_farm_activity_record,
)

OPERATOR_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
LOCATION_ID = "11111111-1111-4111-8111-111111111111"
ACTIVITY_ID = "22222222-2222-4222-8222-222222222222"
EVENT_ID = "33333333-3333-4333-8333-333333333333"
FARM_TASK_ID = "44444444-4444-4444-8444-444444444444"
CREATED_AT = datetime(2026, 10, 16, 9, 30, tzinfo=timezone.utc)


def _activity_row(**overrides):
    row = (
        UUID(ACTIVITY_ID),
        UUID(LOCATION_ID),
        None,
        None,
        None,
        "weeding",
        date(2026, 10, 15),
        "Removed invasive growth",
        Decimal("2.50"),
        Decimal("12.00"),
        [],
        [],
        None,
        "draft",
        "kokonut_gateway",
        CREATED_AT,
        CREATED_AT,
    )
    if not overrides:
        return row
    values = dict(
        zip(
            (
                "id", "location_id", "plot_id", "crop_cycle_id", "farm_task_id", "activity_type",
                "activity_date", "description", "labor_hours", "labor_cost",
                "materials_used", "evidence_urls", "notes", "status", "source_system",
                "created_at", "updated_at",
            ),
            row,
        )
    )
    values.update(overrides)
    return tuple(values.values())


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None
        self.rows = []
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters=None):
        self.connection.statements.append((statement, parameters))
        self.result = None
        self.rows = []
        if "FROM farm_task" in statement:
            self.result = self.connection.task_row
        elif "SELECT id::text FROM farm_activity_operator_event" in statement:
            self.result = (EVENT_ID,)
        elif "SELECT status::text FROM farm_activity" in statement:
            self.result = (self.connection.current_status,)
        elif "SELECT id FROM farm_activity" in statement and "FOR UPDATE" in statement:
            self.result = (UUID(ACTIVITY_ID),)
        elif "RETURNING id, location_id" in statement:
            self.result = self.connection.activity_row
        elif "SELECT id::text, action, from_status" in statement:
            action = self.connection.event_action
            self.result = (EVENT_ID, action, self.connection.event_from, self.connection.event_to, None, CREATED_AT)
        elif "FROM farm_activity AS activity" in statement:
            self.result = (*self.connection.activity_row, self.connection.operator_events)
        elif "FROM farm_activity\n" in statement and "LIMIT %s" in statement:
            row = self.connection.activity_row
            self.rows = [
                (
                    row[0], row[1], row[2], row[3], row[4], row[5], row[6],
                    row[13], row[14], row[15], row[16],
                )
            ]

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.rows


class FakeConnection:
    autocommit = False

    def __init__(self, *, current_status="draft", event_action="submitted", event_from="draft", event_to="submitted"):
        self.statements = []
        self.activity_row = _activity_row()
        self.task_row = (UUID(FARM_TASK_ID),)
        self.operator_events = [
            {
                "action": "draft_created",
                "from_status": None,
                "to_status": "draft",
                "reason": None,
                "actor_operator_id": OPERATOR_ID,
                "changed_fields": None,
                "created_at": CREATED_AT.isoformat(),
            }
        ]
        self.current_status = current_status
        self.event_action = event_action
        self.event_from = event_from
        self.event_to = event_to
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


@pytest.fixture
def tenant_context_spy(monkeypatch):
    calls = []

    def set_context(connection, **kwargs):
        calls.append((connection, kwargs))
        connection.statements.append(("SET TENANT CONTEXT", kwargs))

    monkeypatch.setattr(farm_activity_records, "set_operator_tenant_context", set_context)
    return calls


def test_content_validation_rejects_protected_or_unbounded_fields():
    with pytest.raises(FarmActivityRecordInvalid, match="protected or unsupported"):
        farm_activity_records._normalize_content(
            {"activity_type": "weeding", "status": "published"}, creating=True
        )
    with pytest.raises(FarmActivityRecordInvalid, match="two decimal places"):
        farm_activity_records._normalize_content({"labor_hours": "1.001"}, creating=False)
    with pytest.raises(FarmActivityRecordInvalid, match="100 bounded"):
        farm_activity_records._normalize_content({"evidence_urls": ["x" * 2049]}, creating=False)


def test_list_uses_signed_scope_before_bounded_select_and_excludes_private_content(
    tenant_context_spy,
):
    connection = FakeConnection()
    rows = list_farm_activity_records(
        OPERATOR_ID, LOCATION_ID, 7, connection_factory=lambda: connection
    )

    assert rows[0]["id"] == ACTIVITY_ID
    assert rows[0]["farm_task_id"] is None
    assert "description" not in rows[0]
    scope_index = next(i for i, (sql, _) in enumerate(connection.statements) if sql == "SET TENANT CONTEXT")
    select_index = next(i for i, (sql, _) in enumerate(connection.statements) if "LIMIT %s" in sql)
    query, params = connection.statements[select_index]
    assert tenant_context_spy[0][1]["action"] == "read"
    assert scope_index < select_index
    assert "source_system IS DISTINCT FROM 'field_collector'" in query
    assert params == (LOCATION_ID, False, 7)
    assert not any(sql == "SET TRANSACTION READ ONLY" for sql, _ in connection.statements)
    assert connection.rolled_back and connection.closed


def test_detail_uses_published_scope_when_requested_and_returns_bounded_audit(
    tenant_context_spy,
):
    connection = FakeConnection()
    result = get_farm_activity_record(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        published_only=True,
        connection_factory=lambda: connection,
    )

    assert result["id"] == ACTIVITY_ID
    assert result["operator_events"][0]["action"] == "draft_created"
    assert "evidence_hashes" not in result
    assert "source_raw" not in result
    assert tenant_context_spy[0][1]["action"] == "read_published_detail"
    query = next(sql for sql, _ in connection.statements if "FROM farm_activity AS activity" in sql)
    assert "activity.status IN ('verified', 'published')" in query
    assert "LIMIT 100" in query
    assert connection.rolled_back and connection.closed


def test_create_scopes_before_insert_and_records_only_gateway_owned_lineage(tenant_context_spy):
    connection = FakeConnection()
    result = create_farm_activity_record(
        OPERATOR_ID,
        LOCATION_ID,
        {"activity_type": "weeding", "activity_date": "2026-10-15"},
        connection_factory=lambda: connection,
    )

    assert result["id"] == ACTIVITY_ID
    assert result["event_id"] == EVENT_ID
    assert tenant_context_spy[0][1]["required_scopes"] == (("farm_activity", "read_detail"),)
    insert_index = next(i for i, (sql, _) in enumerate(connection.statements) if "INSERT INTO farm_activity" in sql)
    context_index = next(i for i, (sql, _) in enumerate(connection.statements) if sql == "SET TENANT CONTEXT")
    insert_sql, _ = connection.statements[insert_index]
    assert context_index < insert_index
    assert "'draft', 'gateway_v1', 'kokonut_gateway'" in insert_sql
    assert "source_raw" not in insert_sql and "source_id" not in insert_sql
    assert connection.committed and connection.closed


def test_create_validates_same_location_task_before_insert_and_returns_link(tenant_context_spy):
    connection = FakeConnection()
    connection.activity_row = _activity_row(farm_task_id=UUID(FARM_TASK_ID))
    result = create_farm_activity_record(
        OPERATOR_ID,
        LOCATION_ID,
        {
            "activity_type": "weeding",
            "activity_date": "2026-10-15",
            "farm_task_id": FARM_TASK_ID,
        },
        connection_factory=lambda: connection,
    )

    task_index = next(
        i for i, (sql, _) in enumerate(connection.statements) if "FROM farm_task" in sql
    )
    insert_index = next(
        i for i, (sql, _) in enumerate(connection.statements) if "INSERT INTO farm_activity" in sql
    )
    task_sql, task_params = connection.statements[task_index]
    assert "location_id = %s::uuid" in task_sql and "FOR SHARE" in task_sql
    assert task_params == (FARM_TASK_ID, LOCATION_ID)
    assert task_index < insert_index
    assert result["farm_task_id"] == FARM_TASK_ID
    assert connection.committed and connection.closed


def test_create_rejects_task_from_another_location_before_insert(tenant_context_spy):
    connection = FakeConnection()
    connection.task_row = None

    with pytest.raises(FarmActivityRecordInvalid, match="requested location"):
        create_farm_activity_record(
            OPERATOR_ID,
            LOCATION_ID,
            {
                "activity_type": "weeding",
                "activity_date": "2026-10-15",
                "farm_task_id": FARM_TASK_ID,
            },
            connection_factory=lambda: connection,
        )

    assert not any("INSERT INTO farm_activity" in sql for sql, _ in connection.statements)
    assert connection.rolled_back and connection.closed


def test_draft_edit_sets_actor_reason_and_requires_atomic_event(tenant_context_spy):
    connection = FakeConnection()
    result = edit_farm_activity_record_draft(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        {"notes": "Corrected from field review"},
        "Fix a transcription error",
        connection_factory=lambda: connection,
    )

    assert result["event_id"] == EVENT_ID
    assert tenant_context_spy[0][1]["action"] == "edit_draft"
    action_statement = next(
        (sql, params) for sql, params in connection.statements if "workflow_reason" in sql
    )
    assert action_statement[1] == (OPERATOR_ID, "draft_edited", "Fix a transcription error")
    assert connection.committed and connection.closed


def test_draft_edit_validates_task_scope_before_update_and_returns_link(tenant_context_spy):
    connection = FakeConnection()
    connection.activity_row = _activity_row(farm_task_id=UUID(FARM_TASK_ID))
    result = edit_farm_activity_record_draft(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        {"farm_task_id": FARM_TASK_ID},
        "Link to the scheduled task",
        connection_factory=lambda: connection,
    )

    task_index = next(
        i for i, (sql, _) in enumerate(connection.statements) if "FROM farm_task" in sql
    )
    update_index = next(
        i for i, (sql, _) in enumerate(connection.statements) if "UPDATE farm_activity SET" in sql
    )
    update_sql, update_params = connection.statements[update_index]
    assert task_index < update_index
    assert "farm_task_id = %s" in update_sql
    assert update_params[0] == FARM_TASK_ID
    assert result["farm_task_id"] == FARM_TASK_ID
    assert connection.committed and connection.closed


def test_transition_locks_state_and_sets_only_governed_workflow_action(tenant_context_spy):
    connection = FakeConnection(current_status="submitted", event_action="verified", event_from="submitted", event_to="verified")
    connection.activity_row = _activity_row(status="verified")
    result = transition_farm_activity_record(
        OPERATOR_ID,
        ACTIVITY_ID,
        LOCATION_ID,
        "verify",
        connection_factory=lambda: connection,
    )

    assert result["action"] == "verified"
    assert tenant_context_spy[0][1]["action"] == "verify"
    update = next(sql for sql, _ in connection.statements if "UPDATE farm_activity" in sql)
    assert "verified_by = %s::uuid" in update
    assert "rejection_reason" not in update
    assert connection.committed and connection.closed


def test_denied_tenant_context_runs_no_activity_query_and_cleans_up(monkeypatch):
    connection = FakeConnection()

    def deny(*_args, **_kwargs):
        raise TenantContextDenied("tenant-qualified grant required")

    monkeypatch.setattr(farm_activity_records, "set_operator_tenant_context", deny)
    with pytest.raises(TenantContextDenied, match="tenant-qualified"):
        list_farm_activity_records(
            OPERATOR_ID, LOCATION_ID, connection_factory=lambda: connection
        )

    assert not any("FROM farm_activity" in sql for sql, _ in connection.statements)
    assert connection.rolled_back and connection.closed
