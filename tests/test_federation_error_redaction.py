"""Federation service failures never log provider or database exception text."""

from __future__ import annotations

import logging

import pytest

from services.federation.node import FederationNode
from services.federation.protocol import FederationProtocol
from services.federation.sync import SyncEngine

SECRET_ERROR = "postgresql://operator:secret@db.internal/kokonut"


class _DatabaseFailure(Exception):
    pass


class _FailingCursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        raise _DatabaseFailure(SECRET_ERROR)


class _FailingConnection:
    def __init__(self):
        self.rollbacks = 0
        self.commits = 0

    def cursor(self):
        return _FailingCursor()

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1


@pytest.mark.parametrize(
    ("factory", "method", "args", "expected"),
    [
        (FederationNode, "register", ("farm", "https://farm.example"), "raise"),
        (FederationNode, "update_heartbeat", ("farm",), False),
        (FederationNode, "set_trust_level", ("farm", "trusted"), False),
        (FederationNode, "list_nodes", (), []),
        (FederationNode, "get_node", ("farm",), None),
        (FederationProtocol, "share", ("farm", "rainfall", {"mm": 1}), "raise"),
        (FederationProtocol, "query", ("rainfall",), "raise"),
        (FederationProtocol, "complete_query", ("query-id", {}), False),
        (FederationProtocol, "get_shares", (), []),
        (FederationProtocol, "get_queries", (), []),
        (SyncEngine, "get_nodes_due_for_sync", (), []),
        (SyncEngine, "record_sync", ("farm", True), None),
    ],
)
def test_database_exception_text_is_not_logged(factory, method, args, expected, caplog):
    conn = _FailingConnection()
    service = factory(conn=conn)

    with caplog.at_level(logging.WARNING, logger="kokonut.federation"):
        if expected == "raise":
            with pytest.raises(_DatabaseFailure, match="operator:secret"):
                getattr(service, method)(*args)
        else:
            assert getattr(service, method)(*args) == expected

    assert SECRET_ERROR not in caplog.text
    assert "_DatabaseFailure" in caplog.text
    assert "Traceback" not in caplog.text
    assert conn.rollbacks == (1 if method in {"register", "update_heartbeat", "set_trust_level", "share", "query", "complete_query", "record_sync"} else 0)


def test_sync_error_argument_is_not_logged(caplog):
    conn = _FailingConnection()
    service = SyncEngine(conn=conn)

    with caplog.at_level(logging.WARNING, logger="kokonut.federation"):
        service.record_sync("farm", success=False, error=SECRET_ERROR)

    assert SECRET_ERROR not in caplog.text
    assert "Sync failed for farm" in caplog.text
