"""Header-backed backcasting plans with normalized milestone dependencies."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras

from services.common.logging import get_logger

logger = get_logger(__name__)


class Backcaster:
    """Creates and manages backcasting plans from threat narratives."""

    VALID_STATUSES = {"pending", "in_progress", "completed", "skipped", "blocked"}

    def __init__(self, conn=None):
        self._conn = conn

    def _get_conn(self):
        if self._conn is None:
            from services.common.env import get_db
            self._conn = get_db()
        return self._conn

    @staticmethod
    def _prepare_milestones(milestones: List[Dict[str, Any]]):
        if not milestones:
            raise ValueError("At least one milestone is required")
        ids = [str(uuid.uuid4()) for _ in milestones]
        orders = [m.get("order") for m in milestones]
        if any(not isinstance(order, int) or order <= 0 for order in orders):
            raise ValueError("Milestone order must be a positive integer")
        if len(set(orders)) != len(orders):
            raise ValueError("Milestone order must be unique")

        key_to_id: Dict[str, str] = {}
        for milestone, milestone_id in zip(milestones, ids):
            key = milestone.get("key")
            if key is not None:
                if not isinstance(key, str) or not key or key in key_to_id:
                    raise ValueError("Milestone key must be a unique non-empty string")
                key_to_id[key] = milestone_id

        known_ids = set(ids)
        dependencies: Dict[str, List[str]] = {}
        for milestone, milestone_id in zip(milestones, ids):
            refs = milestone.get("depends_on", milestone.get("dependencies", [])) or []
            resolved = []
            for ref in refs:
                dependency_id = key_to_id.get(str(ref), str(ref))
                if dependency_id not in known_ids:
                    raise ValueError(f"Unknown milestone dependency: {ref}")
                if dependency_id == milestone_id:
                    raise ValueError("Milestone cannot depend on itself")
                if dependency_id not in resolved:
                    resolved.append(dependency_id)
            dependencies[milestone_id] = resolved

        state: Dict[str, int] = {}

        def visit(node: str):
            if state.get(node) == 1:
                raise ValueError("Milestone dependencies contain a cycle")
            if state.get(node) == 2:
                return
            state[node] = 1
            for dependency in dependencies[node]:
                visit(dependency)
            state[node] = 2

        for milestone_id in ids:
            visit(milestone_id)
        return ids, dependencies

    def create_plan(self, narrative_id: str, location_id: str, plan_name: str,
                    future_state_description: str, current_gap_analysis: str,
                    milestones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create one header and its complete milestone DAG atomically."""
        milestone_ids, dependencies = self._prepare_milestones(milestones)
        plan_id = str(uuid.uuid4())
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        created = []
        try:
            cur.execute(
                """SELECT threat.location_id
                   FROM threat_narrative narrative
                   JOIN threat ON threat.id = narrative.threat_id
                   WHERE narrative.id = %s""",
                (narrative_id,),
            )
            narrative = cur.fetchone()
            if not narrative:
                raise ValueError(f"Narrative {narrative_id} not found")
            if str(narrative["location_id"]) != str(location_id):
                raise ValueError("Narrative does not belong to the requested location")
            cur.execute(
                """INSERT INTO backcast_plan
                   (id, narrative_id, location_id, plan_name, future_state_description,
                    current_gap_analysis) VALUES (%s, %s, %s, %s, %s, %s)""",
                (plan_id, narrative_id, location_id, plan_name,
                 future_state_description, current_gap_analysis),
            )
            for milestone, milestone_id in zip(milestones, milestone_ids):
                cur.execute(
                    """INSERT INTO threat_backcast_plan
                       (id, plan_id, narrative_id, location_id, plan_name,
                        future_state_description, current_gap_analysis, milestone_order,
                        milestone_description, milestone_target_date, dependencies,
                        responsible_party, resource_requirements)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING *""",
                    (milestone_id, plan_id, narrative_id, location_id, plan_name,
                     future_state_description, current_gap_analysis, milestone["order"],
                     milestone["description"], milestone.get("target_date"),
                     dependencies[milestone_id], milestone.get("responsible_party"),
                     milestone.get("resource_requirements")),
                )
                row = dict(cur.fetchone())
                row["plan_id"] = plan_id
                created.append(row)
            for milestone_id, dependency_ids in dependencies.items():
                for dependency_id in dependency_ids:
                    cur.execute(
                        """INSERT INTO backcast_milestone_dependency
                           (plan_id, milestone_id, depends_on_milestone_id)
                           VALUES (%s, %s, %s)""",
                        (plan_id, milestone_id, dependency_id),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
        logger.info("Created backcast plan %s with %d milestones", plan_id, len(created))
        return created

    def _resolve_plan_id(self, identifier: str, cur=None) -> str:
        own_cursor = cur is None
        cur = cur or self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """SELECT id FROM backcast_plan WHERE id = %s
                   UNION ALL SELECT plan_id FROM threat_backcast_plan WHERE id = %s
                   UNION ALL SELECT id FROM backcast_plan WHERE narrative_id = %s""",
                (identifier, identifier, identifier),
            )
            ids = list(dict.fromkeys(str(row["id"]) for row in cur.fetchall()))
            if not ids:
                raise ValueError(f"Backcast plan {identifier} not found")
            if len(ids) != 1:
                raise ValueError(f"Narrative {identifier} has multiple backcast plans; use a plan ID")
            return ids[0]
        finally:
            if own_cursor:
                cur.close()

    def get_plan_header(self, identifier: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            try:
                plan_id = self._resolve_plan_id(identifier, cur)
            except ValueError as exc:
                if "not found" in str(exc):
                    return None
                raise
            cur.execute("SELECT * FROM backcast_plan WHERE id = %s", (plan_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()

    def get_plan(self, milestone_id: str) -> Optional[Dict[str, Any]]:
        cur = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM threat_backcast_plan WHERE id = %s", (milestone_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()

    def get_plans_by_narrative(self, narrative_id: str) -> List[Dict[str, Any]]:
        cur = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM threat_backcast_plan WHERE narrative_id = %s ORDER BY milestone_order", (narrative_id,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()

    def get_plans_by_location(self, location_id: str) -> List[Dict[str, Any]]:
        cur = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """SELECT bp.*, n.title AS narrative_title, n.narrative_type, t.threat_name
                   FROM threat_backcast_plan bp JOIN threat_narrative n ON n.id = bp.narrative_id
                   JOIN threat t ON t.id = n.threat_id WHERE bp.location_id = %s
                   ORDER BY bp.plan_name, bp.milestone_order""", (location_id,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()

    @staticmethod
    def _graph_details(milestones, dependency_rows):
        by_id = {str(m["id"]): m for m in milestones}
        deps = {milestone_id: [] for milestone_id in by_id}
        for row in dependency_rows:
            deps[str(row["milestone_id"])].append(str(row["depends_on_milestone_id"]))
        order = []
        seen = set()

        def visit(node):
            if node in seen:
                return
            for dependency in deps[node]:
                visit(dependency)
            seen.add(node)
            order.append(node)

        for node in sorted(by_id, key=lambda item: (by_id[item]["milestone_order"], item)):
            visit(node)
        completed = {node for node, row in by_id.items() if row["milestone_status"] in ("completed", "skipped")}
        blocked_by = {node: [dep for dep in deps[node] if dep not in completed] for node in by_id}
        ready = {node: not blockers for node, blockers in blocked_by.items()}

        # Target dates define elapsed work; missing dates use milestone order as a deterministic proxy.
        dated = [m["milestone_target_date"] for m in milestones if m.get("milestone_target_date")]
        origin = min(dated) if dated else None
        duration = {}
        for node, row in by_id.items():
            target = row.get("milestone_target_date")
            duration[node] = max(1, (target - origin).days + 1) if target and origin else max(1, row["milestone_order"])
        score, paths = {}, {}
        for node in order:
            parent = max(deps[node], key=lambda dep: score[dep], default=None)
            score[node] = duration[node] + (score[parent] if parent else 0)
            paths[node] = (paths[parent] if parent else []) + [node]
        critical_path = paths[max(order, key=lambda node: score[node])] if order else []
        return order, blocked_by, ready, critical_path

    def get_progress(self, identifier: str) -> Dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            plan_id = self._resolve_plan_id(identifier, cur)
            cur.execute("SELECT * FROM backcast_plan WHERE id = %s", (plan_id,))
            header = dict(cur.fetchone())
            cur.execute("SELECT * FROM threat_backcast_plan WHERE plan_id = %s ORDER BY milestone_order", (plan_id,))
            milestones = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT milestone_id, depends_on_milestone_id FROM backcast_milestone_dependency WHERE plan_id = %s", (plan_id,))
            dependency_rows = [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()
        order, blocked_by, ready, critical_path = self._graph_details(milestones, dependency_rows)
        by_id = {str(m["id"]): m for m in milestones}
        for milestone_id, milestone in by_id.items():
            milestone["blocked_by"] = blocked_by[milestone_id]
            milestone["dependency_ready"] = ready[milestone_id]
        total = len(milestones)
        counts = {status: sum(m["milestone_status"] == status for m in milestones) for status in self.VALID_STATUSES}
        today = datetime.now(timezone.utc).date()
        overdue = [m for m in milestones if m.get("milestone_target_date") and m["milestone_target_date"] < today and m["milestone_status"] not in ("completed", "skipped")]
        next_ready = next((by_id[node] for node in order if ready[node] and by_id[node]["milestone_status"] == "pending"), None)
        return {"plan_id": plan_id, "narrative_id": header["narrative_id"], "plan_name": header["plan_name"],
                "total": total, "completed": counts["completed"], "in_progress": counts["in_progress"],
                "blocked": counts["blocked"], "pending": counts["pending"],
                "progress_pct": round(counts["completed"] / total * 100, 1) if total else 0,
                "overdue_count": len(overdue), "overdue_milestones": overdue,
                "next_milestone": next_ready, "topological_order": order,
                "critical_path": critical_path, "milestones": milestones,
                "advisory_only": True, "gaps": [f"Milestone {m['milestone_order']} blocked" for m in milestones if blocked_by[str(m["id"])] or m["milestone_status"] == "blocked"]}

    def update_milestone(self, milestone_id: str, status: Optional[str] = None,
                         completion_evidence: Optional[str] = None,
                         responsible_party: Optional[str] = None) -> Dict[str, Any]:
        if status is not None and status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid milestone status: {status}")
        if status is None and completion_evidence is None and responsible_party is None:
            raise ValueError("No milestone changes supplied")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM threat_backcast_plan WHERE id = %s FOR UPDATE", (milestone_id,))
            existing = cur.fetchone()
            if not existing:
                raise ValueError(f"Milestone {milestone_id} not found")
            if status == existing["milestone_status"] and completion_evidence is None and responsible_party is None:
                raise ValueError("Milestone update would make no changes")
            if status in ("in_progress", "completed"):
                cur.execute(
                    """SELECT d.depends_on_milestone_id FROM backcast_milestone_dependency d
                       JOIN threat_backcast_plan dependency ON dependency.id = d.depends_on_milestone_id
                       WHERE d.milestone_id = %s AND dependency.milestone_status NOT IN ('completed', 'skipped')""",
                    (milestone_id,),
                )
                unmet = [str(row["depends_on_milestone_id"]) for row in cur.fetchall()]
                if unmet:
                    raise ValueError(f"Milestone dependencies are unmet: {', '.join(unmet)}")
            updates, values = [], []
            for column, value in (("milestone_status", status), ("completion_evidence", completion_evidence), ("responsible_party", responsible_party)):
                if value is not None:
                    updates.append(f"{column} = %s")
                    values.append(value)
            cur.execute(f"UPDATE threat_backcast_plan SET {', '.join(updates)}, updated_at = NOW() WHERE id = %s RETURNING *", values + [milestone_id])
            result = dict(cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def delete_plan(self, identifier: str) -> bool:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            plan_id = self._resolve_plan_id(identifier, cur)
            cur.execute("DELETE FROM backcast_plan WHERE id = %s", (plan_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            return deleted
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def challenge_assumption(self, plan_id: str, narrative_id: str,
                             original_assumption: str, challenged_assumption: str,
                             reason: Optional[str] = None) -> Dict[str, Any]:
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            canonical_id = self._resolve_plan_id(plan_id, cur)
            cur.execute("SELECT narrative_id FROM backcast_plan WHERE id = %s", (canonical_id,))
            header = cur.fetchone()
            if str(header["narrative_id"]) != str(narrative_id):
                raise ValueError("Narrative does not match the backcast plan")
            challenge_id = str(uuid.uuid4())
            if plan_id != canonical_id:
                legacy_milestone_id = plan_id
            else:
                cur.execute(
                    "SELECT id FROM threat_backcast_plan WHERE plan_id = %s ORDER BY milestone_order LIMIT 1",
                    (canonical_id,),
                )
                milestone = cur.fetchone()
                if not milestone:
                    raise ValueError("Assumption challenges require at least one plan milestone")
                legacy_milestone_id = milestone["id"]
            cur.execute(
                """INSERT INTO backcast_assumption_challenge
                   (id, backcast_plan_id, plan_id, narrative_id, original_assumption,
                    challenged_assumption, challenge_reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (challenge_id, canonical_id, legacy_milestone_id, narrative_id,
                 original_assumption, challenged_assumption, reason),
            )
            result = dict(cur.fetchone())
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def list_challenges(self, plan_id: str) -> List[Dict[str, Any]]:
        cur = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            canonical_id = self._resolve_plan_id(plan_id, cur)
            cur.execute(
                """SELECT bac.*, nt.title AS narrative_title FROM backcast_assumption_challenge bac
                   JOIN threat_narrative nt ON nt.id = bac.narrative_id
                   WHERE bac.backcast_plan_id = %s ORDER BY bac.created_at DESC""", (canonical_id,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            cur.close()

    def resolve_challenge(self, challenge_id: str, outcome: str, approved_by: str,
                          revised_milestone_id: Optional[str] = None,
                          impact_on_principles: Optional[str] = None) -> Dict[str, Any]:
        if outcome not in ("confirmed", "modified", "rejected"):
            raise ValueError(f"Invalid outcome: {outcome}. Must be confirmed, modified, or rejected")
        if not approved_by:
            raise ValueError("approved_by is required for human oversight")
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute(
                """UPDATE backcast_assumption_challenge SET outcome = %s, approved_by = %s,
                   approved_at = NOW(), revised_milestone_id = %s, impact_on_principles = %s,
                   resolved_at = NOW() WHERE id = %s RETURNING *""",
                (outcome, approved_by, revised_milestone_id, impact_on_principles, challenge_id))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Challenge {challenge_id} not found")
            conn.commit()
            return dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    def get_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        cur = self._get_conn().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute("SELECT * FROM backcast_assumption_challenge WHERE id = %s", (challenge_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            cur.close()
