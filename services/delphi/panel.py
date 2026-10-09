"""Panel management for Real-time Delphi.

Handles panel member registration, pseudonymous display tokens, and
expert-weight derivation from reputation (guild snapshot) or role.
"""

from __future__ import annotations

import secrets
import string
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)

def _generate_token(prefix: str = "P") -> str:
    """Generate a short pseudonymous display token."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{suffix}"


class PanelManager:
    """Manages Delphi panel members."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def add_member(
        self,
        study_id: str,
        participant_ref_type: str = "farmer_identity",
        participant_ref_id: Optional[str] = None,
        role: str = "expert",
        display_token: Optional[str] = None,
        is_anonymous: bool = True,
        expert_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Add a panel member. Weight is auto-derived if not supplied."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if display_token is None:
            display_token = _generate_token()

        if expert_weight is None:
            expert_weight = self._derive_weight(cur, participant_ref_type, participant_ref_id, role)

        member_id = str(__import__("uuid").uuid4())
        cur.execute(
            """
            INSERT INTO delphi_panel_member
                (id, study_id, participant_ref_type, participant_ref_id,
                 display_token, is_anonymous, expert_weight, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                member_id, study_id, participant_ref_type, participant_ref_id,
                display_token, is_anonymous, expert_weight, role,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()

        logger.info("Added panel member %s to study %s", display_token, study_id)
        return result

    def list_members(self, study_id: str) -> List[Dict[str, Any]]:
        """List panel members for a study (respects anonymity for outputs)."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT id, study_id, display_token, is_anonymous, expert_weight, role, joined_at
            FROM delphi_panel_member
            WHERE study_id = %s
            ORDER BY joined_at
            """,
            (study_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM delphi_panel_member WHERE id = %s", (member_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def remove_member(self, member_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM delphi_panel_member WHERE id = %s", (member_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted

    def _derive_weight(
        self,
        cur,
        participant_ref_type: str,
        participant_ref_id: Optional[str],
        role: str,
    ) -> float:
        """Use equal weighting until sufficient resolved forecasts calibrate skill."""
        return 1.0

    def member_weights(self, study_id: str) -> Dict[str, float]:
        """Return mapping of panel_member_id -> expert_weight for a study."""
        members = self.list_members(study_id)
        return {m["id"]: float(m["expert_weight"]) for m in members}

    def assess_diversity(self, study_id: str) -> Dict[str, Any]:
        """Evaluate configured panel targets without exposing identities."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM delphi_diversity_target WHERE study_id=%s", (study_id,))
        targets = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """
            SELECT role, stakeholder_group, affected_community, lived_experience,
                   COUNT(*) AS member_count
            FROM delphi_panel_member
            WHERE study_id=%s AND consent_status <> 'withdrawn'
            GROUP BY role, stakeholder_group, affected_community, lived_experience
            """,
            (study_id,),
        )
        groups = [dict(row) for row in cur.fetchall()]
        panel_size = sum(int(row["member_count"]) for row in groups)
        results, unmet = [], []
        for target in targets:
            key, category = target["dimension_key"], target["category_code"]
            count = sum(int(row["member_count"]) for row in groups if str(row.get(key)).lower() == category.lower())
            share = count / panel_size if panel_size else 0.0
            met = ((target["minimum_count"] is None or count >= target["minimum_count"])
                   and (target["minimum_share"] is None or share >= float(target["minimum_share"])))
            result = {"dimension_key": key, "category_code": category, "count": count, "share": round(share, 4), "met": met}
            results.append(result)
            if not met:
                unmet.append(result)
        if not targets:
            status = "not_configured"
        elif not panel_size:
            status = "insufficient_data"
        elif not unmet:
            status = "targets_met"
        elif len(unmet) == len(targets):
            status = "targets_not_met"
        else:
            status = "targets_partially_met"
        cur.execute(
            """INSERT INTO delphi_diversity_assessment
               (study_id,panel_size,participating_size,target_results,unmet_targets,diversity_status)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
            (study_id, panel_size, panel_size, psycopg2.extras.Json(results), psycopg2.extras.Json(unmet), status),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result
