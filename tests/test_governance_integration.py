"""Integration coverage for workflow, safety, cockpit, and pilot circles."""

import pytest

from services.agents.safety import assess_agent_action
from services.analytics import governance_cockpit
from services.ingestion.base import get_db
from services.workflow_specs.registry import get_spec, load_builtin_specs


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no database available: {exc}")


def test_governance_workflows_are_registered_and_valid():
    load_builtin_specs()
    for spec_id in (
        "governance_circle", "governance_role", "governance_role_assignment",
        "governance_tension", "governance_proposal", "governance_tactical_session",
        "governance_tactical_item", "governance_circle_link",
    ):
        spec = get_spec(spec_id)
        assert spec.invariants
        assert spec.source_refs


def test_agent_governance_safety_is_draft_only():
    assert assess_agent_action("create", "governance_tension", {"status": "draft"}).allowed
    assert assess_agent_action("create", "governance_proposal", {"status": "draft"}).allowed
    assert assess_agent_action("create", "governance_tactical_item", {"status": "open"}).allowed
    assert not assess_agent_action("update", "governance_tension", {"status": "submitted"}).allowed
    assert not assess_agent_action("update", "governance_proposal", {"status": "approved"}).allowed
    assert not assess_agent_action("create", "governance_role", {"status": "draft"}).allowed


def test_adelphi_adjacent_circles_and_cockpit_exist():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT circle_key FROM governance_circle WHERE circle_key LIKE 'adelphi-%' AND status = 'active'")
            circle_keys = {row[0] for row in cur.fetchall()}
        assert {
            "adelphi-stakeholder-stewardship",
            "adelphi-ecological-stewardship",
            "adelphi-market-relationships",
            "adelphi-evidence-measurement",
        } <= circle_keys
        internal = governance_cockpit.internal_cockpit(conn)
        public = governance_cockpit.public_cockpit(conn)
        assert internal["active_circle_count"] >= 4
        assert public["active_circle_count"] >= 4
        assert "privacy_limitation" in public
    finally:
        conn.close()
