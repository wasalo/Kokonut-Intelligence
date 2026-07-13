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

_ROLE_WEIGHTS = {
    "expert": 1.5,
    "policymaker": 1.2,
    "citizen": 1.0,
}


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
            from services.common.env import get_db
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
        """Derive expert weight from reputation snapshot or role default.

        Reputation-based weighting: if a guild reputation snapshot exists for
        the participant, normalize reputation_pct to a 0.5..2.0 weight band.
        Falls back to role-based default.
        """
        base = _ROLE_WEIGHTS.get(role, 1.0)

        if participant_ref_type == "guild_contributor" and participant_ref_id:
            try:
                cur.execute(
                    """
                    SELECT reputation_pct
                    FROM guild_reputation_snapshot
                    WHERE contributor_id = %s
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                    """,
                    (participant_ref_id,),
                )
                row = cur.fetchone()
                if row and row.get("reputation_pct") is not None:
                    pct = float(row["reputation_pct"])
                    # Map 0..100 pct to 0.5..2.0 weight
                    return round(0.5 + (pct / 100.0) * 1.5, 4)
            except psycopg2.Error:
                # Table may not exist in all environments; fall back to role.
                pass

        return base

    def member_weights(self, study_id: str) -> Dict[str, float]:
        """Return mapping of panel_member_id -> expert_weight for a study."""
        members = self.list_members(study_id)
        return {m["id"]: float(m["expert_weight"]) for m in members}
