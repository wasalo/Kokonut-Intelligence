"""Stage-appropriate solution funding and evidence-gated tranche release."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def create_case(conn, solution_id: str, capital_stage: str, funding_instrument: str, requested_amount: float, rationale: str, *, experiment_id: Optional[str] = None, strategy_investment_id: Optional[str] = None, minimum_viable_amount: Optional[float] = None, maximum_authorized_amount: Optional[float] = None, currency: str = "USD", risk_adjusted_expected_value: Optional[float] = None, public_goods_value: Optional[float] = None, community_share: Optional[float] = None, downside_exposure: Optional[float] = None, evidence: Optional[list[Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_funding_case
            (solution_id, experiment_id, strategy_investment_id, capital_stage, funding_instrument,
             requested_amount, minimum_viable_amount, maximum_authorized_amount, currency,
             risk_adjusted_expected_value, public_goods_value, community_share, downside_exposure,
             rationale, evidence)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING *""", (solution_id, experiment_id, strategy_investment_id, capital_stage,
                              funding_instrument, requested_amount, minimum_viable_amount,
                              maximum_authorized_amount, currency, risk_adjusted_expected_value,
                              public_goods_value, community_share, downside_exposure, rationale,
                              json.dumps(evidence or [])))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def submit_case(conn, case_id: str, submitted_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE solution_funding_case SET decision_status = 'submitted', submitted_by_party_id = %s::uuid WHERE id = %s::uuid AND decision_status = 'draft' RETURNING *", (submitted_by_party_id, case_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only draft funding cases can be submitted")
        conn.commit()
        return _clean(row)


def approve_case(conn, case_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("UPDATE solution_funding_case SET decision_status = 'approved', approved_by_party_id = %s::uuid, approved_at = NOW() WHERE id = %s::uuid AND decision_status = 'submitted' RETURNING *", (approved_by_party_id, case_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("only submitted funding cases can be approved")
        conn.commit()
        return _clean(row)


def add_tranche(conn, case_id: str, tranche_number: int, amount: float, milestone_conditions: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""INSERT INTO solution_funding_tranche
            (funding_case_id, tranche_number, amount, milestone_conditions)
            VALUES (%s::uuid, %s, %s, %s::jsonb) RETURNING *""", (case_id, tranche_number, amount, json.dumps(milestone_conditions or {})))
        row = _clean(cur.fetchone())
        conn.commit()
        return row


def approve_tranche(conn, tranche_id: str, approved_by_party_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""UPDATE solution_funding_tranche t SET status = 'approved', approved_by_party_id = %s::uuid, approved_at = NOW()
            FROM solution_funding_case c WHERE t.id = %s::uuid AND t.funding_case_id = c.id
              AND c.decision_status = 'approved' AND t.status = 'proposed' RETURNING t.*""", (approved_by_party_id, tranche_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            raise ValueError("funding case must be approved before tranche approval")
        conn.commit()
        return _clean(row)


def release_tranche(conn, tranche_id: str, amount: float, released_by_party_id: str, milestone_evidence: list[Any]) -> Dict[str, Any]:
    if not milestone_evidence:
        raise ValueError("milestone evidence is required before funding release")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM solution_funding_tranche WHERE id = %s::uuid FOR UPDATE", (tranche_id,))
        tranche = cur.fetchone()
        if not tranche or tranche["status"] != "approved":
            conn.rollback()
            raise ValueError("only approved tranches can be released")
        if float(amount) > float(tranche["amount"]):
            conn.rollback()
            raise ValueError("release exceeds tranche amount")
        cur.execute("""INSERT INTO solution_funding_release
            (tranche_id, amount, milestone_evidence, released_by_party_id)
            VALUES (%s::uuid, %s, %s::jsonb, %s::uuid) RETURNING *""", (tranche_id, amount, json.dumps(milestone_evidence), released_by_party_id))
        release = cur.fetchone()
        cur.execute("UPDATE solution_funding_tranche SET status = 'released', released_at = NOW(), released_by_party_id = %s::uuid WHERE id = %s::uuid", (released_by_party_id, tranche_id))
        conn.commit()
        return _clean(release)
