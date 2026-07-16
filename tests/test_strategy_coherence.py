"""Tests for strategy coherence findings."""

import uuid

import pytest

from services.analytics import strategy_coherence, strategy_kernel
from services.ingestion.base import get_db


PARTY_ID = "b0000000-0000-0000-0000-000000002604"


def test_coherence_finds_missing_kernel_fields():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Coherence Test', 'collective') RETURNING id", (f"coherence-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Incomplete plan", "2026-01-01", "2026-12-31")
        plan_id = str(plan["id"])
        findings = strategy_coherence.run_checks(conn, plan_id)
        rules = {finding["rule_key"] for finding in findings}
        assert "plan_requires_diagnosis" in rules
        assert "plan_requires_guiding_policy" in rules
        assert {"plan_requires_diagnosis", "plan_requires_guiding_policy", "plan_requires_foresight_frame", "plan_requires_approved_choice", "plan_requires_allocation_policy", "plan_requires_executable_objective", "plan_requires_initiative"} == rules
        assert len(strategy_coherence.list_findings(conn, plan_id)) == 7
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
