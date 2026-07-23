"""Meta-Learning Layer — learns which adaptation strategies work best.

Tracks which strategies succeed in which contexts, learns effectiveness
over time, and recommends the best strategy for new situations.
The system learns how to learn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


class MetaLearningEngine:
    """Learns which adaptation strategies work best for which situations."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.database import get_db
            self._conn = get_db()
        return self._conn

    def select_strategy(
        self,
        context_type: str,
        context_data: Dict[str, Any],
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Select the best strategy for a given context based on historical effectiveness."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["ms.enabled = TRUE", "ms.strategy_type = %s"]
        params: list = [context_type]

        if domain:
            conditions.append("(ms.domain IS NULL OR ms.domain = %s)")
            params.append(domain)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT ms.*
            FROM meta_learning_strategy ms
            WHERE {where_clause}
            ORDER BY ms.effectiveness_score DESC, ms.applications_count DESC
            LIMIT 10
        """, params)

        strategies = [dict(r) for r in cur.fetchall()]
        cur.close()

        if not strategies:
            return {
                "selected": None,
                "reason": "no_strategies_available",
                "candidates": [],
            }

        # Select best strategy by effectiveness
        best = strategies[0]

        return {
            "selected": {
                "id": best["id"],
                "name": best["strategy_name"],
                "type": best["strategy_type"],
                "effectiveness_score": float(best["effectiveness_score"] or 0),
                "applications_count": best["applications_count"] or 0,
            },
            "candidates": [
                {
                    "id": s["id"],
                    "name": s["strategy_name"],
                    "effectiveness_score": float(s["effectiveness_score"] or 0),
                }
                for s in strategies
            ],
            "context_type": context_type,
            "domain": domain,
        }

    def record_application(
        self,
        strategy_id: str,
        location_id: Optional[str],
        context: Dict[str, Any],
        outcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record that a strategy was applied and optionally its outcome."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        application_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        cur.execute("""
            INSERT INTO meta_learning_application (
                id, strategy_id, location_id, context, outcome,
                applied_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            application_id, strategy_id, location_id,
            psycopg2.extras.Json(context),
            outcome, now, now,
        ))

        # Update strategy application count
        cur.execute("""
            UPDATE meta_learning_strategy
            SET applications_count = applications_count + 1,
                last_applied_at = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (now, strategy_id))

        conn.commit()
        cur.close()

        return {
            "application_id": application_id,
            "strategy_id": strategy_id,
            "outcome": outcome,
        }

    def update_effectiveness(self, strategy_id: str) -> Dict[str, Any]:
        """Recompute effectiveness score for a strategy based on outcomes."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE outcome = 'success') as successes,
                COUNT(*) FILTER (WHERE outcome = 'partial') as partials,
                COUNT(*) FILTER (WHERE outcome = 'failure') as failures
            FROM meta_learning_application
            WHERE strategy_id = %s
        """, (strategy_id,))

        row = cur.fetchone()

        if not row or row["total"] == 0:
            cur.close()
            return {
                "strategy_id": strategy_id,
                "effectiveness_score": 0.0,
                "applications_count": 0,
            }

        total = row["total"]
        successes = row["successes"] or 0
        partials = row["partials"] or 0

        # Effectiveness: successes + 0.5 * partials, normalized to 0-100
        score = round(((successes + partials * 0.5) / total) * 100, 2)

        cur.execute("""
            UPDATE meta_learning_strategy
            SET effectiveness_score = %s,
                successes_count = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (score, successes, strategy_id))

        conn.commit()
        cur.close()

        return {
            "strategy_id": strategy_id,
            "effectiveness_score": score,
            "applications_count": total,
            "successes": successes,
            "partials": partials,
            "failures": row["failures"] or 0,
        }

    def get_strategy_rankings(
        self,
        strategy_type: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get strategies ranked by effectiveness."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        conditions = ["enabled = TRUE"]
        params: list = []

        if strategy_type:
            conditions.append("strategy_type = %s")
            params.append(strategy_type)
        if domain:
            conditions.append("(domain IS NULL OR domain = %s)")
            params.append(domain)

        where_clause = " AND ".join(conditions)

        cur.execute(f"""
            SELECT id, strategy_name, strategy_type, domain,
                   effectiveness_score, applications_count,
                   successes_count, last_applied_at
            FROM meta_learning_strategy
            WHERE {where_clause}
            ORDER BY effectiveness_score DESC, applications_count DESC
        """, params)

        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of what the system has learned about learning."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) as total_strategies,
                COUNT(*) FILTER (WHERE effectiveness_score > 50) as effective_strategies,
                COUNT(*) FILTER (WHERE effectiveness_score > 0 AND applications_count > 0) as tested_strategies,
                AVG(effectiveness_score) as avg_effectiveness,
                SUM(applications_count) as total_applications,
                SUM(successes_count) as total_successes
            FROM meta_learning_strategy
            WHERE enabled = TRUE
        """)
        summary = dict(cur.fetchone())

        # Best strategy by type
        cur.execute("""
            SELECT strategy_type, strategy_name, effectiveness_score
            FROM meta_learning_strategy
            WHERE enabled = TRUE AND applications_count > 0
            ORDER BY effectiveness_score DESC
        """)
        best_by_type = {}
        for r in cur.fetchall():
            r = dict(r)
            st = r["strategy_type"]
            if st not in best_by_type:
                best_by_type[st] = {
                    "name": r["strategy_name"],
                    "score": float(r["effectiveness_score"] or 0),
                }

        cur.close()

        return {
            "total_strategies": summary["total_strategies"] or 0,
            "tested_strategies": summary["tested_strategies"] or 0,
            "effective_strategies": summary["effective_strategies"] or 0,
            "avg_effectiveness": round(float(summary["avg_effectiveness"] or 0), 2),
            "total_applications": summary["total_applications"] or 0,
            "total_successes": summary["total_successes"] or 0,
            "best_by_type": best_by_type,
        }

    def recommend_strategy(
        self,
        situation_type: str,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Recommend the best strategy for a given situation type."""
        result = self.select_strategy(situation_type, {}, domain)

        if not result["selected"]:
            return {
                "situation_type": situation_type,
                "recommendation": None,
                "reason": "no_matching_strategies",
            }

        return {
            "situation_type": situation_type,
            "recommendation": result["selected"],
            "all_candidates": result["candidates"],
            "domain": domain,
        }
