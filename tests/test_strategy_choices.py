"""Tests for strategic choices and assumptions."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.analytics import strategy_choices, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002602"


def test_test_assumption_rejects_invalid_status():
    with pytest.raises(ValueError, match="invalid assumption status"):
        strategy_choices.test_assumption(None, str(uuid.uuid4()), "unknown_status")


def test_approve_choice_rejects_non_submitted():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only submitted"):
        strategy_choices.approve_choice(mock_conn, str(uuid.uuid4()), str(uuid.uuid4()))


def test_submit_choice_rejects_non_draft():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with pytest.raises(ValueError, match="only draft"):
        strategy_choices.submit_choice(mock_conn, str(uuid.uuid4()))


def test_choices_preserve_alternatives_tradeoffs_and_assumptions():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Choice Test', 'collective') RETURNING id", (f"choice-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Choice Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Choice plan", "2026-01-01", "2026-12-31", PARTY_ID)
        plan_id = str(plan["id"])
        choice = strategy_choices.create_choice(conn, plan_id, "how_to_win", "Build trusted evidence infrastructure", created_by_party_id=PARTY_ID)
        alternative = strategy_choices.add_alternative(conn, str(choice["id"]), "Scale before verification", status="rejected", reason_not_selected="Evidence risk")
        tradeoff = strategy_choices.add_tradeoff(conn, str(choice["id"]), "trust", "speed", "Verification precedes scale", mitigation="Use staged pilots")
        assumption = strategy_choices.create_assumption(conn, plan_id, "Pilot demand remains above capacity", importance="high", test_metric_key="demand_gap")
        validated = strategy_choices.test_assumption(conn, str(assumption["id"]), "validated", evidence=[{"source": "pilot"}])
        assert alternative["status"] == "rejected"
        assert tradeoff["favored_dimension"] == "trust"
        assert validated["status"] == "validated"
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
