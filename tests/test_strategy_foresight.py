"""Integration coverage for the unified strategic foresight frame."""

import uuid

import pytest

from services.analytics import strategy_foresight, strategy_kernel, strategy_coherence
from services.ingestion.base import get_db


def test_foresight_frame_links_inputs_and_drivers():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = plan_id = frame_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Foresight Test', 'collective') RETURNING id", (f"foresight-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
        conn.commit()
        plan = strategy_kernel.create_strategy_plan(conn, "organization", org_id, "Foresight plan", "2026-01-01", "2030-12-31")
        plan_id = str(plan["id"])
        frame = strategy_foresight.create_frame(conn, plan_id, "How should the organization grow under uncertainty?", "Which capabilities should be funded now?", "Organization and connected farm locations", "2026-01-01", "2030-12-31")
        frame_id = str(frame["id"])
        strategy_foresight.add_driver(conn, frame_id, "critical_uncertainty", "Water availability", "Rainfall and water access may materially change the feasible operating model.", impact_level="critical")
        strategy_foresight.link_input(conn, frame_id, "external_document", "scan", source_ref="https://example.test/water-outlook", interpretation="Regional water outlook")
        strategy_foresight.submit_frame(conn, frame_id)
        loaded = strategy_foresight.get_frame(conn, plan_id)
        assert loaded["status"] == "submitted"
        assert len(loaded["drivers"]) == 1
        assert len(loaded["inputs"]) == 1
        rules = {finding["rule_key"] for finding in strategy_coherence.run_checks(conn, plan_id)}
        assert "plan_requires_foresight_frame" not in rules
        assert "foresight_requires_uncertainty" not in rules
        assert "foresight_requires_inputs" not in rules
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
