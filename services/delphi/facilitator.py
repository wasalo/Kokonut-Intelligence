"""Facilitator for Real-time Delphi.

Orchestrates studies: opens/closes them, manages items, ingests contributions
(real-time upsert), recomputes live consensus, builds anonymized summaries of
the current distribution, evaluates stopping criteria, and drafts
recommendations (draft only — human approval required for publication).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger
from services.delphi.consensus import ConsensusCalculator, consensus_reached

logger = get_logger(__name__)


class Facilitator:
    """Coordinates a Real-time Delphi study."""

    def __init__(self, conn=None):
        self._conn = conn
        self._calculator = ConsensusCalculator()

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    # ------------------------------------------------------------------
    # Study lifecycle
    # ------------------------------------------------------------------

    def create_study(
        self,
        title: str,
        description: Optional[str] = None,
        location_id: Optional[str] = None,
        variation: str = "real_time",
        facilitator_type: str = "agent",
        stopping_criteria: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Delphi study in draft status."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if stopping_criteria is None:
            stopping_criteria = {
                "max_duration_hours": 720,
                "stability_pct": 5.0,
                "min_participants": 3,
                "iqr_threshold": 1.0,
            }

        study_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO delphi_study
                (id, location_id, title, description, variation, status,
                 facilitator_type, stopping_criteria, created_by)
            VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s, %s)
            RETURNING *
            """,
            (
                study_id, location_id, title, description, variation,
                facilitator_type, json.dumps(stopping_criteria), created_by,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result

    def open_study(self, study_id: str) -> Dict[str, Any]:
        """Open a study for contributions."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            UPDATE delphi_study
            SET status = 'open', opened_at = NOW(), updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (study_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError(f"Study {study_id} not found")
        conn.commit()
        cur.close()
        return dict(row)

    def close_study(self, study_id: str) -> Dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            UPDATE delphi_study
            SET status = 'closed', closed_at = NOW(), updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            (study_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError(f"Study {study_id} not found")
        conn.commit()
        cur.close()
        return dict(row)

    def get_study(self, study_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM delphi_study WHERE id = %s", (study_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def add_item(
        self,
        study_id: str,
        label: str,
        item_type: str = "option",
        scale: str = "desirability",
        description: Optional[str] = None,
        min_value: float = -1.0,
        max_value: float = 1.0,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a questionnaire item (issue/goal/option) with an evaluation scale."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        item_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO delphi_item
                (id, study_id, item_type, label, description, scale,
                 min_value, max_value, target_entity_type, target_entity_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                item_id, study_id, item_type, label, description, scale,
                min_value, max_value, target_entity_type, target_entity_id,
            ),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result

    # ------------------------------------------------------------------
    # Contributions (real-time)
    # ------------------------------------------------------------------

    def submit_contribution(
        self,
        study_id: str,
        item_id: str,
        panel_member_id: str,
        score: float,
        reasoning: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit or update a member's evaluation for an item (upsert).

        Recomputes live consensus for the item and appends a history row.
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Validate item belongs to study and member belongs to study
        cur.execute(
            """
            SELECT di.id, di.min_value, di.max_value, ds.status
            FROM delphi_item di
            JOIN delphi_study ds ON ds.id = di.study_id
            WHERE di.id = %s AND di.study_id = %s
            """,
            (item_id, study_id),
        )
        item = cur.fetchone()
        if not item:
            cur.close()
            raise ValueError("Item does not belong to study")
        if item["status"] != "open":
            cur.close()
            raise ValueError("Study is not open for contributions")
        if score < float(item["min_value"]) or score > float(item["max_value"]):
            cur.close()
            raise ValueError("Score is outside the item's configured range")
        cur.execute(
            "SELECT id FROM delphi_panel_member WHERE id = %s AND study_id = %s",
            (panel_member_id, study_id),
        )
        if not cur.fetchone():
            cur.close()
            raise ValueError("Panel member does not belong to study")

        contrib_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO delphi_contribution
                (id, study_id, item_id, panel_member_id, score, reasoning)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (item_id, panel_member_id)
            DO UPDATE SET score = EXCLUDED.score, reasoning = EXCLUDED.reasoning,
                          updated_at = NOW()
            RETURNING *
            """,
            (contrib_id, study_id, item_id, panel_member_id, score, reasoning),
        )
        contribution = dict(cur.fetchone())

        consensus = self._recompute_consensus(cur, study_id, item_id)
        conn.commit()
        cur.close()
        return {"contribution": contribution, "consensus": consensus}

    def _recompute_consensus(self, cur, study_id: str, item_id: str) -> Dict[str, Any]:
        """Recompute consensus for an item and persist snapshot + history."""
        # Fetch scores + weights
        cur.execute(
            """
            SELECT c.score, pm.expert_weight
            FROM delphi_contribution c
            JOIN delphi_panel_member pm ON pm.id = c.panel_member_id
            WHERE c.item_id = %s
            """,
            (item_id,),
        )
        rows = cur.fetchall()
        scores = [float(r["score"]) for r in rows]
        weights = [float(r["expert_weight"]) for r in rows]

        stats = self._calculator.compute(scores, weights)

        study = self.get_study(study_id)
        stopping = study["stopping_criteria"]
        if isinstance(stopping, str):
            stopping = json.loads(stopping)

        # Consensus reached flag
        reached = consensus_reached(
            stats["iqr"], stats["participant_count"],
            int(stopping.get("min_participants", 3)),
            float(stopping.get("iqr_threshold", 1.0)),
        )

        # Upsert current snapshot
        cur.execute(
            """
            INSERT INTO delphi_consensus
                (study_id, item_id, median, mean, iqr, stddev, cv,
                 participant_count, weighted_median, consensus_reached, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (item_id)
            DO UPDATE SET median = EXCLUDED.median, mean = EXCLUDED.mean,
                          iqr = EXCLUDED.iqr, stddev = EXCLUDED.stddev,
                          cv = EXCLUDED.cv, participant_count = EXCLUDED.participant_count,
                          weighted_median = EXCLUDED.weighted_median,
                          consensus_reached = EXCLUDED.consensus_reached,
                          computed_at = NOW()
            RETURNING *
            """,
            (
                study_id, item_id, stats["median"], stats["mean"], stats["iqr"],
                stats["stddev"], stats["cv"], stats["participant_count"],
                stats["weighted_median"], reached,
            ),
        )
        snapshot = dict(cur.fetchone())

        # Append history
        cur.execute(
            """
            INSERT INTO delphi_consensus_history
                (study_id, item_id, median, iqr, participant_count)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (study_id, item_id, stats["median"], stats["iqr"], stats["participant_count"]),
        )

        snapshot["consensus_reached"] = reached
        return snapshot

    # ------------------------------------------------------------------
    # Live summary (anonymized)
    # ------------------------------------------------------------------

    def get_live_summary(self, study_id: str) -> Dict[str, Any]:
        """Build an anonymized live summary of the current distribution.

        Shows per-item consensus stats plus conflicting-viewpoint snippets,
        without revealing individual identities (uses display_token only).
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM delphi_study WHERE id = %s", (study_id,))
        study = cur.fetchone()
        if not study:
            cur.close()
            raise ValueError(f"Study {study_id} not found")

        cur.execute(
            """
            SELECT di.id AS item_id, di.label, di.scale, di.item_type,
                   dc.median, dc.iqr, dc.stddev, dc.cv, dc.participant_count,
                   dc.weighted_median, dc.consensus_reached
            FROM delphi_item di
            LEFT JOIN delphi_consensus dc ON dc.item_id = di.id
            WHERE di.study_id = %s
            ORDER BY di.created_at
            """,
            (study_id,),
        )
        items = [dict(r) for r in cur.fetchall()]

        # Conflicting viewpoints: highest and lowest scoring contributions per item
        conflicting = {}
        for item in items:
            cur.execute(
                """
                SELECT pm.display_token, c.score, c.reasoning
                FROM delphi_contribution c
                JOIN delphi_panel_member pm ON pm.id = c.panel_member_id
                WHERE c.item_id = %s
                ORDER BY c.score ASC
                """,
                (item["item_id"],),
            )
            contribs = [dict(r) for r in cur.fetchall()]
            if contribs:
                conflicting[item["item_id"]] = {
                    "lowest": contribs[0],
                    "highest": contribs[-1],
                    "spread": round(float(contribs[-1]["score"]) - float(contribs[0]["score"]), 4),
                }

        panel_size = self._panel_size(cur, study_id)
        cur.close()
        return {
            "study_id": study_id,
            "title": study["title"],
            "status": study["status"],
            "panel_size": panel_size,
            "items": items,
            "conflicting_viewpoints": conflicting,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _panel_size(self, cur, study_id: str) -> int:
        cur.execute(
            "SELECT COUNT(*) AS n FROM delphi_panel_member WHERE study_id = %s",
            (study_id,),
        )
        row = cur.fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # Stopping evaluation
    # ------------------------------------------------------------------

    def check_stopping(self, study_id: str) -> Dict[str, Any]:
        """Evaluate stopping criteria across all items."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        study = self.get_study(study_id)
        stopping = study["stopping_criteria"]
        if isinstance(stopping, str):
            stopping = json.loads(stopping)
        opened_at = study.get("opened_at")
        now = datetime.now(timezone.utc)

        cur.execute(
            """
            SELECT dc.item_id, dc.median, dc.iqr, dc.participant_count
            FROM delphi_consensus dc
            WHERE dc.study_id = %s
            """,
            (study_id,),
        )
        snapshots = [dict(r) for r in cur.fetchall()]

        item_results = []
        for snap in snapshots:
            # previous history
            cur.execute(
                """
                SELECT median, iqr, participant_count
                FROM delphi_consensus_history
                WHERE item_id = %s
                ORDER BY computed_at DESC
                LIMIT 1
                OFFSET 1
                """,
                (snap["item_id"],),
            )
            prev = cur.fetchone()
            prev_dict = dict(prev) if prev else None

            should_stop, detail = self._calculator.evaluate_stopping(
                stopping, snap, prev_dict, opened_at, now
            )
            item_results.append({
                "item_id": snap["item_id"],
                "should_stop": should_stop,
                "detail": detail,
            })

        cur.close()
        return {
            "study_id": study_id,
            "should_stop": bool(item_results) and all(r["should_stop"] for r in item_results),
            "items": item_results,
            "evaluated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # Recommendation (draft only)
    # ------------------------------------------------------------------

    def draft_recommendation(
        self,
        study_id: str,
        recommendation_text: str,
        summary: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a draft recommendation. Must be human-approved to publish."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        rec_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO delphi_recommendation
                (id, study_id, summary, recommendation_text, status, created_by)
            VALUES (%s, %s, %s, %s, 'draft', %s)
            RETURNING *
            """,
            (rec_id, study_id, summary, recommendation_text, created_by),
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result

    def approve_recommendation(
        self,
        recommendation_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:
        """Human approval of a draft recommendation."""
        if not approved_by:
            raise ValueError("approved_by is required for human oversight")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            UPDATE delphi_recommendation
            SET status = 'approved', approved_by = %s, approved_at = NOW()
            WHERE id = %s AND status = 'draft'
            RETURNING *
            """,
            (approved_by, recommendation_id),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError(f"Recommendation {recommendation_id} not found")
        conn.commit()
        cur.close()
        return dict(row)

    def list_recommendations(self, study_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM delphi_recommendation WHERE study_id = %s ORDER BY created_at DESC",
            (study_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results
