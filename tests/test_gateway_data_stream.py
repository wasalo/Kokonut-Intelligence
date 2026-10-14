"""Focused tenant-context contract for Gateway Data Stream writes."""

from contextlib import AbstractContextManager
from types import SimpleNamespace

import pytest

from services.common.tenant_context import TenantContextDenied
from services.gateway.data_stream import create_gateway_data_stream_post

LOCATION_ID = "11111111-1111-4111-8111-111111111111"
ACTOR_ID = "22222222-2222-4222-8222-222222222222"
AUTHORIZATION = {
    "resource": "data_stream_post",
    "action": "create",
    "location_id": LOCATION_ID,
    "credential_type": "api_key",
    "credential_hash": "a" * 64,
}


class FakeConnection(AbstractContextManager):
    def __init__(self, events):
        self.events = events

    def __enter__(self):
        self.events.append("connection-open")
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.events.append("rollback" if exc_type else "commit")
        return False


def test_gateway_post_sets_db_verified_context_before_insert(monkeypatch):
    events = []
    connection = FakeConnection(events)

    def set_context(actual_connection, **kwargs):
        assert actual_connection is connection
        events.append(("context", kwargs))
        return SimpleNamespace(location_id=LOCATION_ID, actor_id=ACTOR_ID)

    def create_post(actual_connection, **kwargs):
        assert actual_connection is connection
        events.append(("insert", kwargs))
        return {"id": "33333333-3333-4333-8333-333333333333", "created_at": None}

    monkeypatch.setattr(
        "services.common.tenant_context.set_gateway_tenant_context", set_context
    )
    monkeypatch.setattr("services.data_stream.post.create_post", create_post)

    result = create_gateway_data_stream_post(
        {
            "location_id": LOCATION_ID,
            "title": "Field observation",
            "content": "Observed soil cover.",
            "created_by": "spoofed-user",
        },
        AUTHORIZATION,
        connection_factory=lambda: connection,
    )

    assert result["id"] == "33333333-3333-4333-8333-333333333333"
    assert events[0] == "connection-open"
    assert events[1] == (
        "context",
        {
            "credential_type": "api_key",
            "credential_hash": "a" * 64,
            "location_id": LOCATION_ID,
            "resource": "data_stream_post",
            "action": "create",
        },
    )
    assert events[2] == (
        "insert",
        {
            "location_id": LOCATION_ID,
            "post_type": "monitoring_report",
            "title": "Field observation",
            "content": "Observed soil cover.",
            "created_by": ACTOR_ID,
        },
    )
    assert events[-1] == "commit"


def test_denied_database_context_prevents_insert_and_rolls_back(monkeypatch):
    events = []
    connection = FakeConnection(events)

    def deny(_connection, **_kwargs):
        events.append("denied")
        raise TenantContextDenied("credential scope is stale")

    monkeypatch.setattr(
        "services.common.tenant_context.set_gateway_tenant_context", deny
    )
    monkeypatch.setattr(
        "services.data_stream.post.create_post",
        lambda *_args, **_kwargs: pytest.fail("insert ran after tenant denial"),
    )

    with pytest.raises(TenantContextDenied):
        create_gateway_data_stream_post(
            {"location_id": LOCATION_ID, "title": "Field observation"},
            AUTHORIZATION,
            connection_factory=lambda: connection,
        )

    assert events == ["connection-open", "denied", "rollback"]


@pytest.mark.parametrize(
    ("body", "authorization", "error"),
    [
        ({"location_id": "not-a-uuid", "title": "Bad"}, AUTHORIZATION, "location_id"),
        (
            {"location_id": LOCATION_ID, "title": "Wrong route"},
            {**AUTHORIZATION, "action": "read"},
            "authorization",
        ),
        (
            {"location_id": LOCATION_ID, "title": "Wrong location"},
            {**AUTHORIZATION, "location_id": "44444444-4444-4444-8444-444444444444"},
            "location",
        ),
    ],
)
def test_invalid_request_scope_fails_before_opening_database(body, authorization, error):
    opened = False

    def factory():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open for invalid request scope")

    with pytest.raises(ValueError, match=error):
        create_gateway_data_stream_post(body, authorization, connection_factory=factory)

    assert opened is False


def test_credential_without_database_revalidation_is_denied_before_open(monkeypatch):
    opened = False

    def factory():
        nonlocal opened
        opened = True
        raise AssertionError("database must not open for unsupported credential")

    with pytest.raises(TenantContextDenied, match="cannot establish tenant context"):
        create_gateway_data_stream_post(
            {"location_id": LOCATION_ID, "title": "Field observation"},
            {**AUTHORIZATION, "credential_type": None, "credential_hash": None},
            connection_factory=factory,
        )

    assert opened is False
