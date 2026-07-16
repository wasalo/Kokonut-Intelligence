"""Tests for versioned organization/location strategy plans."""

import uuid

import pytest

from services.analytics import strategy_kernel
from services.analytics import strategy_governance
from services.analytics import strategy_choices
from services.analytics import strategy_foresight
from services.planning import strategy_allocation
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002601"


def test_strategy_plan_lifecycle_and_versioning():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    objective_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Strategy Kernel Test', 'collective') RETURNING id", (f"strategy-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Strategy Reviewer')", (PARTY_ID,))
            cur.execute("""INSERT INTO objective
                (objective_name, objective_type, target_value, current_value, target_date, owner, status)
                VALUES ('Build evidence capability', 'strategic', 100, 0, '2026-12-31', 'Strategy Reviewer', 'proposed') RETURNING id""")
            objective_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO objective_kpi (objective_id, metric_key, target_value, direction) VALUES (%s::uuid, 'evidence_coverage', 100, 'gte')", (objective_id,))
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Regenerative growth", "2026-01-01", "2028-12-31", PARTY_ID, diagnosis_summary="Demand is growing faster than capacity.", guiding_policy="Build capability before scaling.", approval_mode="governance_circle")
        choice = strategy_choices.create_choice(conn, str(plan["id"]), "how_to_win", "Build trusted evidence infrastructure", created_by_party_id=PARTY_ID)
        strategy_choices.submit_choice(conn, str(choice["id"]))
        strategy_choices.approve_choice(conn, str(choice["id"]), PARTY_ID)
        strategy_allocation.create_policy(conn, str(plan["id"]))
        frame = strategy_foresight.create_frame(conn, str(plan["id"]), "How should evidence capability evolve?", "Which capability should be funded first?", "Organization and its evidence systems", "2026-01-01", "2028-12-31")
        strategy_foresight.add_driver(conn, str(frame["id"]), "critical_uncertainty", "Adoption uncertainty", "Farmer and partner adoption may vary materially.")
        strategy_foresight.link_input(conn, str(frame["id"]), "external_document", "scan", source_ref="https://example.test/adoption")
        strategy_foresight.submit_frame(conn, str(frame["id"]))
        strategy_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO strategy_map
                (id, entity_type, entity_id, perspective, strategy_plan_id, objective_id, statement, accountable_party_id, leading_or_lagging)
                VALUES (%s::uuid, 'organization', %s::uuid, 'internal_process', %s::uuid, %s::uuid, 'Build evidence capability', %s::uuid, 'leading')""", (strategy_id, org_id, plan["id"], objective_id, PARTY_ID))
            cur.execute("""INSERT INTO strategy_initiative
                (strategy_map_id, name, owner, target_date)
                VALUES (%s::uuid, 'Build evidence capability', 'Strategy Reviewer', '2026-12-31')""", (strategy_id,))
        conn.commit()
        assert plan["version"] == 1 and plan["visibility"] == "private"
        strategy_kernel.submit_strategy_plan(conn, str(plan["id"]))
        circle_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO governance_circle
                (id, circle_key, name, purpose, scope_type, scope_id, status)
                VALUES (%s::uuid, %s, 'Strategy Circle', 'Approve strategy plans', 'organization', %s::uuid, 'draft')""", (circle_id, f"strategy-circle-{uuid.uuid4().hex[:8]}", org_id))
        conn.commit()
        link = strategy_governance.add_link(conn, str(plan["id"]), "governance_circle", circle_id, "approval", required=True)
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
            cur.execute("DELETE FROM governance_circle WHERE scope_id = %s::uuid", (org_id,))
            if objective_id:
                cur.execute("DELETE FROM objective WHERE id = %s::uuid", (objective_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()


def test_strategy_kernel_supports_both_scope_types_without_database():
    with pytest.raises(ValueError, match="scope_type"):
        strategy_kernel.create_strategy_plan(None, "platform", str(uuid.uuid4()), "Invalid", "2026-01-01", "2026-12-31")
