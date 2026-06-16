"""
Soil Carbon Delta Calculator

Formula: latest.carbon_tonnes_per_ha - baseline.carbon_tonnes_per_ha
Definition: Soil carbon after intervention minus baseline
"""

from typing import Dict, Any, Optional

import psycopg2
import psycopg2.extras


def compute_soil_carbon_delta(
    conn, location_id: str,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get all soil carbon measurements for this location, grouped by plot
    cur.execute("""
        SELECT
            sc.plot_id,
            p.name as plot_name,
            sc.measurement_date,
            sc.carbon_tonnes_per_ha,
            sc.is_baseline
        FROM soil_carbon_measurement sc
        LEFT JOIN plot p ON sc.plot_id = p.id
        WHERE sc.location_id = %s
        ORDER BY sc.plot_id, sc.measurement_date
    """, (location_id,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not rows:
        return {
            "value": 0.0,
            "computation_method": "latest - baseline per plot",
            "source_record_ids": [],
            "metadata": {"plots": 0, "measurements": 0},
        }

    # Group by plot
    by_plot: Dict[str, list] = {}
    for row in rows:
        pid = str(row["plot_id"])
        by_plot.setdefault(pid, []).append(row)

    plot_deltas = []
    total_baseline = 0.0
    total_latest = 0.0

    for pid, measurements in by_plot.items():
        if len(measurements) < 2:
            continue
        baseline = measurements[0]["carbon_tonnes_per_ha"]
        latest = measurements[-1]["carbon_tonnes_per_ha"]
        delta = float(latest) - float(baseline)
        total_baseline += float(baseline)
        total_latest += float(latest)
        plot_deltas.append({
            "plot_id": pid,
            "plot_name": measurements[0].get("plot_name"),
            "baseline": float(baseline),
            "latest": float(latest),
            "delta": round(delta, 4),
        })

    overall_delta = total_latest - total_baseline if plot_deltas else 0.0
    pct_change = (
        (overall_delta / total_baseline * 100) if total_baseline > 0 else 0.0
    )

    return {
        "value": round(overall_delta, 4),
        "computation_method": "latest.carbon_tonnes_per_ha - baseline.carbon_tonnes_per_ha (per plot, then summed)",
        "source_record_ids": [],
        "metadata": {
            "plots_measured": len(plot_deltas),
            "total_measurements": len(rows),
            "overall_delta": round(overall_delta, 4),
            "pct_change": round(pct_change, 2),
            "per_plot": plot_deltas,
        },
    }
