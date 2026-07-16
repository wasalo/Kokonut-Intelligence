"""Integration coverage for staged solution funding."""

import uuid

import pytest

from services.ingestion.base import get_db
from services.innovation import solution_funding, solution_lifecycle


PARTY_ID = "b0000000-0000-0000-0000-000000002710"


def test_funding_release_requires_milestone_evidence():
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no database available: {exc}")
    solution_id = case_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
            cur.execute("INSERT INTO party (id, party_type, display_name) VALUES (%s::uuid, 'person', 'Funding Reviewer')", (PARTY_ID,))
        conn.commit()
        solution = solution_lifecycle.create_solution(conn, f"funding-{uuid.uuid4().hex[:8]}", "Field protocol", "practice", "A field problem", owner_party_id=PARTY_ID)
        solution_id = str(solution["id"])
        case = solution_funding.create_case(conn, solution_id, "experiment", "grant", 1000, "Fund a bounded experiment", evidence=[{"source":"field-need"}])
        case_id = str(case["id"])
        solution_funding.submit_case(conn, case_id, PARTY_ID)
        solution_funding.approve_case(conn, case_id, PARTY_ID)
        tranche = solution_funding.add_tranche(conn, case_id, 1, 1000, {"success_metric":"water_reliability"})
        solution_funding.approve_tranche(conn, str(tranche["id"]), PARTY_ID)
        with pytest.raises(ValueError, match="evidence"):
            solution_funding.release_tranche(conn, str(tranche["id"]), 1000, PARTY_ID, [])
        release = solution_funding.release_tranche(conn, str(tranche["id"]), 1000, PARTY_ID, [{"metric":"water_reliability","value":90}])
        assert float(release["amount"]) == 1000
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            if solution_id:
                cur.execute("DELETE FROM solution WHERE id = %s::uuid", (solution_id,))
            cur.execute("DELETE FROM party WHERE id = %s::uuid", (PARTY_ID,))
        conn.commit()
        conn.close()
