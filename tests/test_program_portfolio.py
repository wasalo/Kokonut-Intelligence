"""Tests for program / project portfolio (PPM)."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.planning import portfolio
from services.workflow_specs.validator import validate
from services.workflow_specs.project import PROJECT


def test_project_spec_validates():
    validate(PROJECT)
    assert PROJECT.states == frozenset({"draft", "active", "on_hold", "done", "cancelled"})


def _db():
    try:
        return get_db()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no database available: {exc}")


@pytest.fixture
def org_id():
    conn = _db()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO organization (name) VALUES (%s) RETURNING id", ("ppm-test",))
            oid = cur.fetchone()[0]
            conn.commit()
        yield str(oid)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM project WHERE organization_id = %s", (oid,))
            cur.execute("DELETE FROM program WHERE organization_id = %s", (oid,))
            cur.execute("DELETE FROM organization WHERE id = %s", (oid,))
            conn.commit()
    finally:
        conn.close()


def test_program_project_lifecycle_and_rollup(org_id):
    conn = _db()
    try:
        prog = portfolio.create_program(conn, org_id, "Regenerative rollout")
        program_id = str(prog["id"])
        proj = portfolio.create_project(conn, org_id, "Plot A establishment", program_id=program_id)
        project_id = str(proj["id"])
        assert proj["status"] == "draft"

        portfolio.start(conn, project_id, "manager")
        assert portfolio.get_project(conn, project_id)["status"] == "active"

        with pytest.raises(ValueError):
            portfolio.hold(conn, project_id, "", "manager")  # note required
        portfolio.hold(conn, project_id, "weather delay", "manager")
        assert portfolio.get_project(conn, project_id)["status"] == "on_hold"

        portfolio.resume(conn, project_id, "manager")
        portfolio.complete(conn, project_id, "manager")
        assert portfolio.get_project(conn, project_id)["status"] == "done"

        rollup = portfolio.project_rollup(conn, project_id)
        assert rollup["status"] == "done"
        prog_rollup = portfolio.program_rollup(conn, program_id)
        assert prog_rollup["project_counts"].get("done") == 1
    finally:
        conn.close()
