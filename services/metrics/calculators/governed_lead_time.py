"""Governed lead-time calculator (VSM).

Average elapsed time (days) from a record's first `draft` transition to its
`published` transition, for lifecycle entities belonging to a location.
Sources: lifecycle_transition ledger (populated by triggers on the governed
pipeline tables).
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
    UNION ALL SELECT 'farm_activity', id, location_id FROM farm_activity WHERE location_id = %(loc)s
    UNION ALL SELECT 'harvest_event', id, location_id FROM harvest_event WHERE location_id = %(loc)s
    UNION ALL SELECT 'agent_task', id, subject_id FROM agent_task WHERE subject_type = 'location' AND subject_id = %(loc)s
"""


def compute_governed_lead_time(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    ps = period_start or "1970-01-01"
    pe = period_end or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    params = {"loc": location_id, "ps": ps, "pe": pe}
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        WITH entity_loc AS ({_ENTITY_LOC}),
        pub AS (
            SELECT lt.entity_type, lt.entity_id, lt.transitioned_at AS published_at
            FROM lifecycle_transition lt
            JOIN entity_loc el ON el.et = lt.entity_type AND el.id = lt.entity_id
            WHERE lt.to_status = 'published'
              AND lt.transitioned_at >= %(ps)s AND lt.transitioned_at <= %(pe)s
        ),
        start AS (
            SELECT entity_type, entity_id, MIN(transitioned_at) AS start_at
            FROM lifecycle_transition
            WHERE from_status = 'draft' OR to_status = 'draft'
            GROUP BY entity_type, entity_id
        )
        SELECT AVG(EXTRACT(EPOCH FROM (p.published_at - s.start_at)) / 86400.0) AS avg_lead_days,
               COUNT(*) AS n
        FROM pub p
        JOIN start s USING (entity_type, entity_id)
    """, params)
    row = cur.fetchone() or {"avg_lead_days": None, "n": 0}

    avg_days = row.get("avg_lead_days")
    n = int(row.get("n") or 0)
    value = round(float(avg_days), 4) if avg_days is not None else None

    return {
        "value": value,
        "unit": "days",
        "computation_method": "avg(draft->published seconds)/86400 over location lifecycle entities",
        "source_record_ids": [],
        "metadata": {"published_count": n, "period_start": ps, "period_end": pe},
    }
