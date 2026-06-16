"""
Attestation Coverage Calculator

Formula: COUNT(published) / COUNT(eligible) * 100
Definition: Percentage of publishable claims attested
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_attestation_coverage(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    date_filter = ""
    params = [location_id]
    if period_start:
        date_filter += " AND created_at >= %s"
        params.append(period_start)
    if period_end:
        date_filter += " AND created_at <= %s"
        params.append(period_end)

    # All attestation records for this location
    cur.execute(f"""
        SELECT
            status,
            COUNT(*) as count
        FROM attestation_record
        WHERE subject_id = %s
          AND subject_type = 'location'
          {date_filter}
        GROUP BY status
    """, params)
    status_counts = {r["status"]: r["count"] for r in cur.fetchall()}

    # MRV claims for this location
    cur.execute(f"""
        SELECT
            status,
            COUNT(*) as count
        FROM mrv_claim
        WHERE location_id = %s
          {date_filter}
        GROUP BY status
    """, params)
    mrv_counts = {r["status"]: r["count"] for r in cur.fetchall()}

    # Eligible = not draft, not rejected (submitted + verified + published)
    eligible_attestations = sum(
        status_counts.get(s, 0) for s in ("submitted", "verified", "published")
    )
    published_attestations = status_counts.get("published", 0)

    eligible_mrv = sum(
        mrv_counts.get(s, 0) for s in ("submitted", "verified", "published")
    )
    published_mrv = mrv_counts.get("published", 0)

    total_eligible = eligible_attestations + eligible_mrv
    total_published = published_attestations + published_mrv
    coverage = (total_published / total_eligible * 100) if total_eligible > 0 else 0.0

    cur.close()

    return {
        "value": round(coverage, 2),
        "computation_method": "COUNT(published) / COUNT(eligible) * 100",
        "source_record_ids": [],
        "metadata": {
            "attestation_status_counts": status_counts,
            "mrv_claim_status_counts": mrv_counts,
            "total_eligible": total_eligible,
            "total_published": total_published,
        },
    }
