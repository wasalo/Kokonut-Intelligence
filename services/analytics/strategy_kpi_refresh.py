"""Refresh strategy KPIs from verified metric values."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def _variance(value: Optional[float], target: Optional[float], direction: str) -> str:
    if value is None or target is None:
        return "not_measurable"
    if direction == "gte":
        ratio = float(value) / float(target) if target else 1
    elif direction == "lte":
        ratio = float(target) / float(value) if value else 1
    else:
        ratio = 1 if value == target else 0
    return "on_track" if ratio >= 1 else "at_risk" if ratio >= 0.8 else "breach"


def refresh_objective_kpis(conn, objective_id: str) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT ok.*, o.location_id, md.metric_key FROM objective_kpi ok
            JOIN objective o ON o.id = ok.objective_id
            LEFT JOIN metric_definition md ON md.id = ok.metric_definition_id OR md.metric_key = ok.metric_key
            WHERE ok.objective_id = %s::uuid FOR UPDATE OF ok""", (objective_id,))
        kpis = cur.fetchall()
        results = []
        for kpi in kpis:
            cur.execute("""SELECT mv.* FROM metric_value mv
                JOIN metric_definition md ON md.id = mv.metric_id
                WHERE (md.metric_key = %s OR mv.metric_id = %s::uuid)
                  AND mv.verified = TRUE
                  AND mv.location_id IS NOT DISTINCT FROM %s::uuid
                ORDER BY mv.computed_at DESC LIMIT 1""", (kpi["metric_key"], kpi["metric_definition_id"], kpi["location_id"]))
            measured = cur.fetchone()
            previous = kpi["current_value_snapshot"]
            value = measured["value"] if measured else None
            source_status = "verified" if measured else "missing"
            variance_status = _variance(value, kpi["target_value"], kpi["direction"])
            cur.execute("""UPDATE objective_kpi SET current_value_snapshot = %s,
                source_status = %s, source_measured_at = %s, source_metric_value_id = %s::uuid,
                variance_status = %s, refreshed_at = NOW(), updated_at = NOW()
                WHERE id = %s::uuid RETURNING *""", (value, source_status, measured["computed_at"] if measured else None, measured["id"] if measured else None, variance_status, kpi["id"]))
            updated = cur.fetchone()
            review_task_id = None
            if variance_status == "breach" and kpi["variance_status"] != "breach":
                cur.execute("""SELECT sm.strategy_plan_id FROM strategy_map sm
                    WHERE sm.objective_id = %s::uuid AND sm.strategy_plan_id IS NOT NULL
                    ORDER BY sm.updated_at DESC LIMIT 1""", (objective_id,))
                plan = cur.fetchone()
                if plan:
                    cur.execute("""SELECT id FROM strategy_review_task
                        WHERE strategy_plan_id = %s::uuid AND review_type = 'kpi_breach'
                          AND status IN ('pending', 'in_progress', 'overdue')
                          AND evidence ->> 'objective_kpi_id' = %s
                        LIMIT 1""", (plan["strategy_plan_id"], str(kpi["id"])))
                    open_task = cur.fetchone()
                    if open_task:
                        review_task_id = open_task["id"]
                    else:
                        cur.execute("""INSERT INTO strategy_review_task
                            (strategy_plan_id, review_type, due_at, evidence)
                            VALUES (%s::uuid, 'kpi_breach', %s, %s::jsonb) RETURNING id""", (plan["strategy_plan_id"], datetime.now(timezone.utc) + timedelta(days=7), '{"source":"verified_metric","objective_kpi_id":"' + str(kpi["id"]) + '"}'))
                        review_task_id = cur.fetchone()["id"]
            cur.execute("""INSERT INTO strategy_kpi_refresh_log
                (objective_kpi_id, metric_value_id, previous_value, refreshed_value, variance_status, source_status, review_task_id)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::uuid) RETURNING *""", (kpi["id"], measured["id"] if measured else None, previous, value, variance_status, source_status, review_task_id))
            results.append(_clean(updated))
        conn.commit()
        return results
