"""Legacy agent action APIs fail closed without authenticated scope."""

from unittest.mock import MagicMock

import pytest

from services.agents import logging as agent_logging
from services.agents.safety import audit_agent_action
from services.common import database


def _install_database_tripwire(monkeypatch):
    get_db = MagicMock(side_effect=AssertionError("database access must not occur"))
    monkeypatch.setattr(database, "get_db", get_db)
    # Catch both qualified database access and a future local import alias.
    monkeypatch.setattr(agent_logging, "get_db", get_db, raising=False)
    return get_db


def test_legacy_agent_action_write_fails_before_database_access(monkeypatch):
    get_db = _install_database_tripwire(monkeypatch)

    with pytest.raises(agent_logging.AgentActionIdentityUnavailable, match="authenticated"):
        agent_logging.log_agent_action(
            agent_id="caller-supplied-agent-id",
            task_id=None,
            action="read",
            collection="location",
        )

    get_db.assert_not_called()


def test_safety_audit_wrapper_cannot_turn_caller_id_into_agent_identity(monkeypatch):
    get_db = _install_database_tripwire(monkeypatch)

    with pytest.raises(agent_logging.AgentActionIdentityUnavailable, match="authenticated"):
        audit_agent_action(
            agent_id="caller-supplied-agent-id",
            action="read",
            collection="location",
            payload={"location_id": "synthetic-location"},
        )

    get_db.assert_not_called()


def test_global_agent_action_history_read_fails_before_database_access(monkeypatch):
    get_db = _install_database_tripwire(monkeypatch)

    with pytest.raises(agent_logging.AgentActionIdentityUnavailable, match="authenticated"):
        agent_logging.get_agent_actions()

    get_db.assert_not_called()
