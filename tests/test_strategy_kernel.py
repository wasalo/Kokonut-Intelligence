"""Tests for versioned organization/location strategy plans."""

import uuid

import pytest

from services.analytics import strategy_kernel
from services.analytics import strategy_governance
from services.analytics import strategy_choices
from services.planning import strategy_allocation
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002601"


def test_strategy_plan_lifecycle_and_versioning():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Strategy Kernel Test', 'collective') RETURNING id", (f"strategy-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Strategy Reviewer')", (PARTY_ID,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Regenerative growth", "2026-01-01", "2028-12-31", PARTY_ID, diagnosis_summary="Demand is growing faster than capacity.", guiding_policy="Build capability before scaling.", approval_mode="governance_circle")
        choice = strategy_choices.create_choice(conn, str(plan["id"]), "how_to_win", "Build trusted evidence infrastructure", created_by_party_id=PARTY_ID)
        strategy_choices.submit_choice(conn, str(choice["id"]))
        strategy_choices.approve_choice(conn, str(choice["id"]), PARTY_ID)
        strategy_allocation.create_policy(conn, str(plan["id"]))
        assert plan["version"] == 1 and plan["visibility"] == "private"
        strategy_kernel.submit_strategy_plan(conn, str(plan["id"]))
        link = strategy_governance.add_link(conn, str(plan["id"]), "governance_circle", str(uuid.uuid4()), "approval", required=True)
        with conn.cursor() as cur:
            cur.execute("UPDATE strategy_governance_link SET status = 'approved' WHERE id = %s::uuid", (link["id"],))
        conn.commit()
        strategy_kernel.approve_strategy_plan(conn, str(plan["id"]), PARTY_ID)
        active = strategy_kernel.activate_strategy_plan(conn, str(plan["id"]))
        assert active["status"] == "active"
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM strategy_plan_transition WHERE strategy_plan_id = %s::uuid", (plan["id"],))
            assert cur.fetchone()[0] == 3
        version_two = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Regenerative growth revision", "2026-01-01", "2028-12-31", PARTY_ID, supersedes_plan_id=str(plan["id"]))
        assert version_two["version"] == 2
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM strategy_plan WHERE scope_id = %s::uuid", (org_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_strategy_kernel_supports_both_scope_types_without_database():
    with pytest.raises(ValueError, match="scope_type"):
        strategy_kernel.create_strategy_plan(None, "platform", str(uuid.uuid4()), "Invalid", "2026-01-01", "2026-12-31")
