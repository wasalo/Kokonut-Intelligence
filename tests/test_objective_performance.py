"""Tests for performance management (objectives, KPIs, reviews)."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.planning import performance
from services.workflow_specs.validator import validate
from services.workflow_specs.objective import OBJECTIVE


def test_objective_spec_validates():
    validate(OBJECTIVE)
    assert OBJECTIVE.states == frozenset({"on_track", "at_risk", "off_track", "closed"})


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


@pytest.fixture
def org_and_objective():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO organization (org_key, name) VALUES (%s, %s) RETURNING id",
                (str(uuid.uuid4()), "perf-test"),
            )
            org = cur.fetchone()[0]
            cur.execute("INSERT INTO objective (objective_name) VALUES (%s) RETURNING id", ("Grow maize",))
            obj = cur.fetchone()[0]
            conn.commit()
        yield str(org), str(obj)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM objective_review WHERE objective_id = %s", (obj,))
            cur.execute("DELETE FROM objective_kpi WHERE objective_id = %s", (obj,))
            cur.execute("DELETE FROM objective WHERE id = %s", (obj,))
            cur.execute("DELETE FROM organization WHERE id = %s", (org,))
            conn.commit()
    finally:
        conn.close()


def test_assign_kpi_and_review_health(org_and_objective):
    conn = _db()
    org_id, obj_id = org_and_objective
    try:
        kpi = performance.assign_kpi(conn, obj_id, target_value=100.0, direction="gte", metric_key="yield")
        assert kpi["target_value"] == 100.0

        review, _ = performance.record_review(conn, obj_id, "staff", "on_track", reviewer_id=str(uuid.uuid4()))
        assert performance.objective_health(conn, obj_id) == "on_track"

        review, _ = performance.record_review(conn, obj_id, "staff", "at_risk", reviewer_id=str(uuid.uuid4()))
        assert performance.objective_health(conn, obj_id) == "at_risk"

        # off_track spawns a corrective work item.
        review, wi = performance.record_review(
            conn, obj_id, "staff", "off_track", reviewer_id=str(uuid.uuid4()), organization_id=org_id,
        )
        assert performance.objective_health(conn, obj_id) == "off_track"
        assert wi is not None
    finally:
        conn.close()


def test_invalid_review_transition_rejected(org_and_objective):
    conn = _db()
    org_id, obj_id = org_and_objective
    try:
        performance.record_review(conn, obj_id, "staff", "on_track")
        # closed -> off_track invalid (closed is terminal).
        performance.record_review(conn, obj_id, "staff", "closed")
        with pytest.raises(ValueError):
            performance.record_review(conn, obj_id, "staff", "off_track")
    finally:
        conn.close()
