"""Tests for typed strategy evidence lineage."""

import uuid

import pytest

from services.analytics import strategy_evidence
from services.ingestion.base import get_db


def test_link_evidence_rejects_invalid_subject_type():
    with pytest.raises(ValueError, match="invalid strategy evidence subject type"):
        strategy_evidence.link_evidence(None, str(uuid.uuid4()), "invalid_type", str(uuid.uuid4()), "metric_value", source_id=str(uuid.uuid4()))


def test_link_evidence_rejects_invalid_source_type():
    with pytest.raises(ValueError, match="invalid strategy evidence source type"):
        strategy_evidence.link_evidence(None, str(uuid.uuid4()), "plan", str(uuid.uuid4()), "fake_source", source_id=str(uuid.uuid4()))


def test_link_evidence_rejects_missing_source():
    with pytest.raises(ValueError, match="source_id or source_ref"):
        strategy_evidence.link_evidence(None, str(uuid.uuid4()), "plan", str(uuid.uuid4()), "metric_value")


def test_evidence_link_is_typed_and_idempotent():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    org_id = None
    plan_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (org_key, name, org_type) VALUES (%s, 'Evidence Test', 'collective') RETURNING id", (f"evidence-{uuid.uuid4().hex[:8]}",))
            org_id = str(cur.fetchone()[0])
            cur.execute("INSERT INTO strategy_plan (scope_type, scope_id, name, planning_horizon_start, planning_horizon_end, diagnosis_summary, guiding_policy) VALUES ('organization', %s::uuid, 'Evidence plan', '2026-01-01', '2026-12-31', 'Evidence', 'Use evidence') RETURNING id", (org_id,))
            plan_id = str(cur.fetchone()[0])
        conn.commit()
        source_id = str(uuid.uuid4())
        first = strategy_evidence.link_evidence(conn, plan_id, "plan", plan_id, "external_document", source_id=source_id, confidence="high")
        second = strategy_evidence.link_evidence(conn, plan_id, "plan", plan_id, "external_document", source_id=source_id, confidence="moderate")
        assert first["id"] == second["id"]
        assert len(strategy_evidence.list_evidence(conn, plan_id)) == 1
        with pytest.raises(ValueError, match="source_id or source_ref"):
            strategy_evidence.link_evidence(conn, plan_id, "plan", plan_id, "external_document")
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if plan_id:
                cur.execute("DELETE FROM strategy_plan WHERE id = %s::uuid", (plan_id,))
            if org_id:
                cur.execute("DELETE FROM organization WHERE id = %s::uuid", (org_id,))
        conn.commit()
        conn.close()
