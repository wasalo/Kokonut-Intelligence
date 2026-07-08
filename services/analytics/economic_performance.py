"""Economic performance analytics: revenue per acre, ROI by block, revenue stream contribution."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_revenue_per_acre(conn, location_id: str) -> dict[str, Any]:
    """Compute revenue per acre/hectare by crop cycle."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cc.id, c.name AS crop_name, cc.cycle_name,
               cc.area_planted, cc.area_unit,
               COALESCE(SUM(re.amount_usd), 0) AS total_revenue_usd,
               COALESCE(SUM(ee.amount), 0) AS total_expenses_usd
        FROM crop_cycle cc
        JOIN crop c ON c.id = cc.crop_id
        LEFT JOIN revenue_event re ON re.crop_cycle_id = cc.id AND re.status IN ('verified', 'published')
        LEFT JOIN expense_event ee ON ee.crop_cycle_id = cc.id AND ee.status IN ('verified', 'published')
        WHERE cc.location_id = %s AND cc.status IN ('completed', 'harvested', 'active')
        GROUP BY cc.id, c.name, cc.cycle_name, cc.area_planted, cc.area_unit
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    cycles = []
    for row in rows:
        area = float(row[3] or 0)
        revenue = float(row[5] or 0)
        expenses = float(row[6] or 0)
        area_acres = area * 2.47105 if row[4] == "hectares" else area
        revenue_per_acre = revenue / area_acres if area_acres > 0 else 0
        roi = ((revenue - expenses) / expenses * 100) if expenses > 0 else 0
        cycles.append({
            "cycle_id": str(row[0]),
            "crop_name": row[1],
            "cycle_name": row[2],
            "area": area,
            "area_unit": row[4],
            "total_revenue_usd": round(revenue, 2),
            "total_expenses_usd": round(expenses, 2),
            "revenue_per_acre_usd": round(revenue_per_acre, 2),
            "roi_pct": round(roi, 2),
        })
    total_revenue = sum(c["total_revenue_usd"] for c in cycles)
    total_expenses = sum(c["total_expenses_usd"] for c in cycles)
    return {
        "location_id": location_id,
        "cycles": cycles,
        "total_revenue_usd": round(total_revenue, 2),
        "total_expenses_usd": round(total_expenses, 2),
        "overall_roi_pct": round(((total_revenue - total_expenses) / total_expenses * 100) if total_expenses > 0 else 0, 2),
    }


def compute_revenue_stream_contribution(conn, location_id: str) -> dict[str, Any]:
    """Compute revenue stream contribution to net profitability."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT stream_name, stream_category,
               SUM(gross_revenue) AS total_gross,
               SUM(direct_costs) AS total_direct,
               SUM(allocated_costs) AS total_allocated,
               SUM(net_contribution) AS total_net,
               AVG(contribution_pct) AS avg_contribution_pct,
               COUNT(*) AS record_count
        FROM revenue_stream_contribution
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY stream_name, stream_category
        ORDER BY total_net DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    streams = []
    for row in rows:
        streams.append({
            "stream_name": row[0],
            "stream_category": row[1],
            "total_gross_revenue": round(float(row[2] or 0), 2),
            "total_direct_costs": round(float(row[3] or 0), 2),
            "total_allocated_costs": round(float(row[4] or 0), 2),
            "total_net_contribution": round(float(row[5] or 0), 2),
            "avg_contribution_pct": round(float(row[6] or 0), 2),
            "record_count": row[7],
        })
    total_gross = sum(s["total_gross_revenue"] for s in streams)
    total_net = sum(s["total_net_contribution"] for s in streams)
    return {
        "location_id": location_id,
        "streams": streams,
        "total_gross_revenue": round(total_gross, 2),
        "total_net_contribution": round(total_net, 2),
        "most_profitable_stream": streams[0]["stream_name"] if streams else None,
        "stream_count": len(streams),
    }


def compute_training_impact(conn, location_id: str) -> dict[str, Any]:
    """Compute training participation and improvement metrics."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT session_topic, session_type,
               COUNT(*) AS session_count,
               COUNT(DISTINCT participant_name) AS unique_participants,
               SUM(duration_hours) AS total_hours,
               AVG(pre_score) AS avg_pre_score,
               AVG(post_score) AS avg_post_score,
               AVG(improvement_pct) AS avg_improvement_pct,
               MIN(session_date) AS first_session,
               MAX(session_date) AS last_session
        FROM training_session
        WHERE location_id = %s AND status IN ('verified', 'published')
        GROUP BY session_topic, session_type
        ORDER BY avg_improvement_pct DESC
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    topics = []
    for row in rows:
        topics.append({
            "session_topic": row[0],
            "session_type": row[1],
            "session_count": row[2],
            "unique_participants": row[3],
            "total_hours": round(float(row[4] or 0), 2),
            "avg_pre_score": round(float(row[5] or 0), 2),
            "avg_post_score": round(float(row[6] or 0), 2),
            "avg_improvement_pct": round(float(row[7] or 0), 2),
            "first_session": str(row[8]) if row[8] else None,
            "last_session": str(row[9]) if row[9] else None,
        })
    total_participants = sum(t["unique_participants"] for t in topics)
    total_hours = sum(t["total_hours"] for t in topics)
    avg_improvement = (
        sum(t["avg_improvement_pct"] * t["session_count"] for t in topics)
        / max(sum(t["session_count"] for t in topics), 1)
    )
    return {
        "location_id": location_id,
        "topics": topics,
        "total_unique_participants": total_participants,
        "total_training_hours": round(total_hours, 2),
        "weighted_avg_improvement_pct": round(avg_improvement, 2),
        "topic_count": len(topics),
    }
