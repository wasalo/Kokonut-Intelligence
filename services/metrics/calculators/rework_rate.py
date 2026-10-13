"""Rework rate calculator (VSM).

Percentage of lifecycle entities that reached `published` in the period and
required at least one `rejected` transition (i.e. needed rework). Complement
of first-time-through yield at the published-set level.
Sources: lifecycle_transition ledger.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

_ENTITY_LOC = """
    SELECT 'data_stream_post' AS et, id, location_id FROM data_stream_post WHERE location_id = %(loc)s
    UNION ALL SELECT 'ai_summary', id, subject_id FROM ai_summary WHERE subject_type = 'location' AND subject_id = %(loc)s
    UNION ALL SELECT 'impact_claim', id, location_id FROM impact_claim WHERE location_id = %(loc)s
    UNION ALL SELECT 'report_snapshot', id, location_id FROM report_snapshot WHERE location_id = %(loc)s
    UNION ALL SELECT 'stakeholder_feedback', id, location_id FROM stakeholder_feedback WHERE location_id = %(loc)s
    UNION ALL SELECT 'farm_activity', id, location_id FROM farm_activity
        WHERE location_id = %(loc)s
          AND farm_activity_source_eligible_for_use(source_system, source_id, source_raw, location_id)
    UNION ALL SELECT 'harvest_event', id, location_id FROM harvest_event WHERE location_id = %(loc)s
    UNION ALL SELECT 'agent_task', id, subject_id FROM agent_task WHERE subject_type = 'location' AND subject_id = %(loc)s
"""


def _normalize_id_array(value: Any) -> List[str]:
    """Normalize psycopg2 UUID/text arrays, including unparsed PG literals."""
    if isinstance(value, str):
        literal = value.strip()
        if literal.startswith("{") and literal.endswith("}"):
            literal = literal[1:-1]
        return [part.strip().strip('"') for part in literal.split(",") if part.strip()]
    return [str(item) for item in (value or [])]


def compute_rework_rate(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    ps = period_start or "1970-01-01"
    pe = period_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    params = {"loc": location_id, "ps": ps, "pe": pe}
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(f"""
        WITH entity_loc AS ({_ENTITY_LOC}),
        pub AS (
            SELECT DISTINCT lt.entity_type, lt.entity_id
            FROM lifecycle_transition lt
            JOIN entity_loc el ON el.et = lt.entity_type AND el.id = lt.entity_id
            WHERE lt.to_status = 'published'
              AND lt.transitioned_at >= %(ps)s::date
              AND lt.transitioned_at < (%(pe)s::date + INTERVAL '1 day')
        ),
        rej AS (
            SELECT DISTINCT entity_type, entity_id
            FROM lifecycle_transition
            WHERE to_status = 'rejected'
        )
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE r.entity_type IS NOT NULL) AS reworked,
               ARRAY(
                   SELECT source.entity_id::text
                   FROM pub AS source
                   ORDER BY source.entity_id
                   LIMIT 101
               ) AS source_ids,
               ARRAY(
                   SELECT source.entity_id::text
                   FROM pub AS source
                   JOIN rej AS rejected USING (entity_type, entity_id)
                   ORDER BY source.entity_id
                   LIMIT 101
               ) AS reworked_source_ids
        FROM pub p
        LEFT JOIN rej r USING (entity_type, entity_id)
        """, params)
        row = cur.fetchone() or {"total": 0, "reworked": 0}
    finally:
        cur.close()

    total = int(row.get("total") or 0)
    reworked = int(row.get("reworked") or 0)
    value = round(reworked / total * 100.0, 2) if total > 0 else None
    source_ids = _normalize_id_array(row.get("source_ids"))
    reworked_source_ids = _normalize_id_array(row.get("reworked_source_ids"))

    return {
        "value": value,
        "unit": "percent",
        "computation_method": "published_with_rejection / published * 100",
        "source_record_ids": source_ids[:100],
        "metadata": {
            "published_count": total,
            "reworked_count": reworked,
            "source_record_ids_truncated": total > 100,
            "reworked_source_record_ids": reworked_source_ids[:100],
            "reworked_source_record_ids_truncated": reworked > 100,
            "period_start": ps,
            "period_end": pe,
        },
    }
