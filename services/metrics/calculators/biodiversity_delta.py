"""
Biodiversity Delta Calculator

Formula: after_observation.species_count - baseline.species_count
Definition: Species count after intervention minus baseline
"""

import math
from typing import Dict, Any, Optional, List

import psycopg2
import psycopg2.extras


def _shannon_index(counts: List[int]) -> float:
    """Compute Shannon diversity index H = -sum(p_i * ln(p_i))."""
    total = sum(counts)
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            h -= p * math.log(p)
    return h


def compute_biodiversity_delta(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            species_name,
            species_category,
            observation_date,
            COUNT(*) as observation_count,
            SUM(count) as total_count
        FROM species_observation
        WHERE location_id = %s
        GROUP BY species_name, species_category, observation_date
        ORDER BY observation_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {
            "value": 0,
            "computation_method": "latest species_count - baseline species_count",
            "source_record_ids": [],
            "metadata": {"species_observed": 0},
        }

    # Split into baseline (earliest date) and latest (most recent date)
    dates = sorted(set(str(r["observation_date"]) for r in rows))
    baseline_date = dates[0]
    latest_date = dates[-1]

    baseline_species = set()
    latest_species = set()
    baseline_counts = []
    latest_counts = []

    for r in rows:
        d = str(r["observation_date"])
        if d == baseline_date:
            baseline_species.add(r["species_name"])
            baseline_counts.append(int(r["total_count"] or 1))
        if d == latest_date:
            latest_species.add(r["species_name"])
            latest_counts.append(int(r["total_count"] or 1))

    baseline_count = len(baseline_species)
    latest_count = len(latest_species)
    delta = latest_count - baseline_count
    baseline_h = _shannon_index(baseline_counts)
    latest_h = _shannon_index(latest_counts)

    return {
        "value": delta,
        "computation_method": "latest species_count - baseline species_count",
        "source_record_ids": [],
        "metadata": {
            "baseline_date": baseline_date,
            "latest_date": latest_date,
            "baseline_species_count": baseline_count,
            "latest_species_count": latest_count,
            "baseline_shannon_index": round(baseline_h, 4),
            "latest_shannon_index": round(latest_h, 4),
            "shannon_delta": round(latest_h - baseline_h, 4),
            "baseline_species": sorted(baseline_species),
            "latest_species": sorted(latest_species),
        },
    }
