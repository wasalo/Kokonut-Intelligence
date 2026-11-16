from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

pytest.importorskip("fastapi")
from starlette.testclient import TestClient

from services.gateway import operator_auth, scheduler_operator
from services.gateway.app import create_app
from services.gateway.audit import GatewayAudit

_TASK_ID = UUID("33333333-3333-4333-8333-333333333338")
_SESSION_HASH = "a" * 64


class _Provider:
    def __init__(self, capabilities=()):
        self.capabilities = set(capabilities)
        self.checked_capabilities = []
        self.session = SimpleNamespace(
            session_id="session-id",
            csrf_token_hash="unused-by-fake",
            session_token_hash=_SESSION_HASH,
            operator=SimpleNamespace(operator_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        )
        self.settings = SimpleNamespace(state_secret="test-state-secret-with-at-least-32-bytes")

    def authenticate_request(self, request):
        if request.cookies.get(operator_auth.SESSION_COOKIE) == "valid-session":
            return self.session
        return None

    def has_global_capability(self, session_token_hash, capability):
        self.checked_capabilities.append((session_token_hash, capability))
        return capability in self.capabilities

    def has_scope(self, *_args):
        return False

    def csrf_valid(self, request, _session):
        return (
            request.cookies.get(operator_auth.CSRF_COOKIE) == "valid-csrf"
            and request.headers.get("x-csrf-token") == "valid-csrf"
        )

    def list_scopes(self, _operator_id):
        return []

    def revoke_session(self, _session_id):
        return None


def _app(monkeypatch, provider):
    monkeypatch.setattr(operator_auth, "create_provider", lambda: provider)
    monkeypatch.setattr(GatewayAudit, "log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(GatewayAudit, "reserve_mutation", lambda _self: "reservation")
    monkeypatch.setattr(GatewayAudit, "release_mutation", lambda *_args: None)
    monkeypatch.setattr(GatewayAudit, "replay_pending", lambda *_args: 0)
    monkeypatch.setattr(GatewayAudit, "capture_status", lambda _self: "ok")
    return create_app()


def _set_session(client, *, csrf=False):
    client.cookies.set(operator_auth.SESSION_COOKIE, "valid-session")
    if csrf:
        client.cookies.set(operator_auth.CSRF_COOKIE, "valid-csrf")


def test_scheduler_routes_require_exact_global_capabilities():
    assert operator_auth.auth_route_policy(
        "GET", "/operator/api/scheduler/tasks", enabled=True
    )["global_capability"] == "scheduler:read"
    assert operator_auth.auth_route_policy(
        "POST", f"/operator/api/scheduler/tasks/{_TASK_ID}/enable", enabled=True
    )["global_capability"] == "scheduler:enable"
    assert operator_auth.auth_route_policy(
        "POST", f"/operator/api/scheduler/tasks/{_TASK_ID}/disable", enabled=True
    )["global_capability"] == "scheduler:disable"
    assert operator_auth.auth_route_policy(
        "DELETE", f"/operator/api/scheduler/tasks/{_TASK_ID}/enable", enabled=True
    ) is None
    assert operator_auth.auth_route_policy(
        "GET", "/operator/api/scheduler/tasks", enabled=False
    ) is None


def test_scheduler_task_inventory_is_capability_gated(monkeypatch):
    provider = _Provider({"scheduler:read"})
    monkeypatch.setattr(
        scheduler_operator,
        "_list_tasks",
        lambda limit: {"items": [{"name": "test-task"}], "returned": limit},
    )
    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client)
        response = client.get("/operator/api/scheduler/tasks?limit=7")

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"items": [{"name": "test-task"}], "returned": 7}
    assert provider.checked_capabilities == [(_SESSION_HASH, "scheduler:read")]


def test_scheduler_mutation_requires_capability_and_csrf(monkeypatch):
    provider = _Provider({"scheduler:enable"})
    monkeypatch.setattr(
        scheduler_operator,
        "_set_task_enabled",
        lambda *_args, **_kwargs: pytest.fail("CSRF failure must prevent scheduler mutation"),
    )
    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client)
        response = client.post(
            f"/operator/api/scheduler/tasks/{_TASK_ID}/enable",
            json={"reason": "reviewed"},
        )

    assert response.status_code == 403
    assert provider.checked_capabilities == [(_SESSION_HASH, "scheduler:enable")]


def test_scheduler_mutation_passes_session_hash_reason_and_graph_choice(monkeypatch):
    provider = _Provider({"scheduler:enable"})
    calls = []
    monkeypatch.setattr(
        scheduler_operator,
        "_set_task_enabled",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"action": "enable"},
    )
    with TestClient(_app(monkeypatch, provider)) as client:
        _set_session(client, csrf=True)
        response = client.post(
            f"/operator/api/scheduler/tasks/{_TASK_ID}/enable",
            headers={"X-CSRF-Token": "valid-csrf"},
            json={"reason": "reviewed activation", "include_dependencies": True},
        )

    assert response.status_code == 200, response.text
    assert calls == [
        (
            (_SESSION_HASH, _TASK_ID, "enable", "reviewed activation"),
            {"include_dependencies": True},
        )
    ]


def test_disable_is_rejected_while_enabled_dependents_remain():
    tasks = [
        {"id": "root", "name": "root", "is_enabled": True, "depends_on": []},
        {"id": "middle", "name": "middle", "is_enabled": True, "depends_on": ["root"]},
        {"id": "leaf", "name": "leaf", "is_enabled": True, "depends_on": ["middle"]},
        {"id": "off", "name": "off", "is_enabled": False, "depends_on": ["root"]},
    ]

    assert scheduler_operator._enabled_dependents("root", tasks) == ["leaf", "middle"]
