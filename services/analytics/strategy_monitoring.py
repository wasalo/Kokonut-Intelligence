"""Convert material competitive signals into durable strategy review tasks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from psycopg2.extras import RealDictCursor


def _clean(row):
    return {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in dict(row).items()}


def process_material_signals(conn, *, due_in_days: int = 7) -> List[Dict[str, Any]]:
    due_at = datetime.now(timezone.utc) + timedelta(days=due_in_days)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT cs.id, cs.content, cs.materiality, cl.strategy_plan_id
            FROM competitive_signal cs JOIN competitive_landscape cl ON cl.id = cs.landscape_id
            LEFT JOIN competitive_signal_trigger cst ON cst.signal_id = cs.id
            WHERE cs.materiality IN ('high', 'critical') AND cst.id IS NULL
              AND cl.status IN ('submitted', 'verified', 'published')""")
        signals = cur.fetchall()
        created = []
        for signal in signals:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"competitive-signal:{signal['id']}",))
            cur.execute("SELECT id FROM competitive_signal_trigger WHERE signal_id = %s::uuid", (signal["id"],))
            if cur.fetchone():
                continue
            cur.execute("""INSERT INTO strategy_review_task
                (strategy_plan_id, review_type, due_at, evidence)
                VALUES (%s::uuid, 'competitive_change', %s, %s::jsonb) RETURNING *""", (signal["strategy_plan_id"], due_at, '{"source":"competitive_signal"}'))
            task = cur.fetchone()
            cur.execute("""INSERT INTO competitive_signal_trigger (signal_id, review_task_id, trigger_reason)
                VALUES (%s::uuid, %s::uuid, %s) RETURNING *""", (signal["id"], task["id"], f"{signal['materiality']} competitive signal: {signal['content']}"))
            created.append(_clean(task))
        conn.commit()
        return created


def monitor_summary(conn, strategy_plan_id: str) -> Dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT COUNT(*) AS signal_count,
            COUNT(*) FILTER (WHERE materiality IN ('high', 'critical') AND reviewed_at IS NULL) AS unreviewed_material_count
            FROM competitive_signal cs JOIN competitive_landscape cl ON cl.id = cs.landscape_id
            WHERE cl.strategy_plan_id = %s::uuid""", (strategy_plan_id,))
        signals = dict(cur.fetchone())
        cur.execute("""SELECT COUNT(*) AS open_review_count FROM strategy_review_task
            WHERE strategy_plan_id = %s::uuid AND review_type = 'competitive_change'
              AND status IN ('pending', 'in_progress', 'overdue')""", (strategy_plan_id,))
        reviews = dict(cur.fetchone())
        return {"strategy_plan_id": strategy_plan_id, "signal_count": signals["signal_count"], "unreviewed_material_signal_count": signals["unreviewed_material_count"], "open_competitive_review_count": reviews["open_review_count"]}
