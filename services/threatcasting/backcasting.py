"""Backcaster — works backward from future states to identify necessary milestones."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class Backcaster:
    """Creates and manages backcasting plans from threat narratives."""

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    def create_plan(
        self,
        narrative_id: str,
        location_id: str,
        plan_name: str,
        future_state_description: str,
        current_gap_analysis: str,
        milestones: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Create a backcasting plan with milestones.

        milestones: [{order, description, target_date, dependencies, responsible_party, resource_requirements}]
        """
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        created = []

        for m in milestones:
            plan_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO threat_backcast_plan
                    (id, narrative_id, location_id, plan_name,
                     future_state_description, current_gap_analysis,
                     milestone_order, milestone_description, milestone_target_date,
                     dependencies, responsible_party, resource_requirements)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    plan_id, narrative_id, location_id, plan_name,
                    future_state_description, current_gap_analysis,
                    m["order"], m["description"],
                    m.get("target_date"), m.get("dependencies", []),
                    m.get("responsible_party"), m.get("resource_requirements"),
                ),
            )
            created.append(dict(cur.fetchone()))

        conn.commit()
        cur.close()

        logger.info("Created backcast plan %s with %d milestones", plan_name, len(created))
        return created

    def get_plan(
        self,
        plan_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single backcast plan milestone."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM threat_backcast_plan WHERE id = %s", (plan_id,))
        result = cur.fetchone()
        cur.close()
        return dict(result) if result else None

    def get_plans_by_narrative(
        self,
        narrative_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all milestones for a narrative's backcast plan."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT * FROM threat_backcast_plan
            WHERE narrative_id = %s
            ORDER BY milestone_order
            """,
            (narrative_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def get_plans_by_location(
        self,
        location_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all backcast plans for a location."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            """
            SELECT bp.*, n.title AS narrative_title, n.narrative_type, t.threat_name
            FROM threat_backcast_plan bp
            JOIN threat_narrative n ON n.id = bp.narrative_id
            JOIN threat t ON t.id = n.threat_id
            WHERE bp.location_id = %s
            ORDER BY bp.plan_name, bp.milestone_order
            """,
            (location_id,),
        )
        results = [dict(r) for r in cur.fetchall()]
        cur.close()
        return results

    def update_milestone(
        self,
        plan_id: str,
        status: Optional[str] = None,
        completion_evidence: Optional[str] = None,
        responsible_party: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a milestone's status."""
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        updates = {"updated_at": datetime.now(timezone.utc)}
        if status:
            updates["milestone_status"] = status
        if completion_evidence:
            updates["completion_evidence"] = completion_evidence
        if responsible_party:
            updates["responsible_party"] = responsible_party

        set_parts = [f"{k} = %s" for k in updates if k != "updated_at"]
        set_values = [v for k, v in updates.items() if k != "updated_at"]

        cur.execute(
            f"""
            UPDATE threat_backcast_plan
            SET {', '.join(set_parts)}, updated_at = NOW()
            WHERE id = %s
            RETURNING *
            """,
            set_values + [plan_id],
        )
        result = dict(cur.fetchone())
        conn.commit()
        cur.close()
        return result

    def get_progress(
        self,
        narrative_id: str,
    ) -> Dict[str, Any]:
        """Get backcast plan progress for a narrative."""
        milestones = self.get_plans_by_narrative(narrative_id)
        if not milestones:
            return {"narrative_id": narrative_id, "total": 0, "completed": 0, "progress_pct": 0}

        total = len(milestones)
        completed = sum(1 for m in milestones if m["milestone_status"] == "completed")
        in_progress = sum(1 for m in milestones if m["milestone_status"] == "in_progress")
        blocked = sum(1 for m in milestones if m["milestone_status"] == "blocked")
        pending = sum(1 for m in milestones if m["milestone_status"] == "pending")

        # Find overdue milestones
        now = datetime.now(timezone.utc).date()
        overdue = [
            m for m in milestones
            if m.get("milestone_target_date") and m["milestone_target_date"] < now
            and m["milestone_status"] not in ("completed", "skipped")
        ]

        # Find next milestone (first pending or in_progress)
        next_milestone = None
        for m in milestones:
            if m["milestone_status"] in ("pending", "in_progress"):
                next_milestone = m
                break

        # Identify gaps
        gaps = []
        for m in milestones:
            if m["milestone_status"] == "blocked":
                gaps.append(f"Milestone {m['milestone_order']} blocked: {m.get('resource_requirements') or 'unspecified'}")

        return {
            "narrative_id": narrative_id,
            "plan_name": milestones[0]["plan_name"] if milestones else None,
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "pending": pending,
            "progress_pct": round((completed / total) * 100, 1) if total > 0 else 0,
            "overdue_count": len(overdue),
            "overdue_milestones": overdue,
            "next_milestone": next_milestone,
            "gaps": gaps,
        }

    def delete_plan(self, narrative_id: str) -> bool:
        """Delete all milestones for a narrative."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM threat_backcast_plan WHERE narrative_id = %s", (narrative_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        return deleted
