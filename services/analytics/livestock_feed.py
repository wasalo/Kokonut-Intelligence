"""Livestock feed analytics: feed intake, conversion ratio, per-animal consumption."""

from __future__ import annotations

from typing import Any

from services.common.logging import get_logger

logger = get_logger(__name__)


def compute_feed_intake_summary(conn, location_id: str) -> dict[str, Any]:
    """Compute feed intake summary per livestock group."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT lg.id, lg.group_name, lg.species, lg.breed, lg.animal_count,
               lg.feed_type AS group_feed_type,
               COUNT(fir.id) AS record_count,
               SUM(fir.quantity_kg) AS total_feed_kg,
               AVG(fir.quantity_kg) AS avg_feed_per_record,
               AVG(fir.per_animal_kg) AS avg_per_animal_kg,
               MIN(fir.record_date) AS first_record,
               MAX(fir.record_date) AS last_record
        FROM livestock_group lg
        LEFT JOIN feed_intake_record fir ON fir.livestock_group_id = lg.id
            AND fir.status IN ('verified', 'published')
        WHERE lg.location_id = %s AND lg.status = 'active'
        GROUP BY lg.id, lg.group_name, lg.species, lg.breed, lg.animal_count, lg.feed_type
        ORDER BY total_feed_kg DESC NULLS LAST
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    groups = []
    for row in rows:
        groups.append({
            "group_id": str(row[0]),
            "group_name": row[1],
            "species": row[2],
            "breed": row[3],
            "animal_count": row[4],
            "group_feed_type": row[5],
            "record_count": row[6],
            "total_feed_kg": round(float(row[7] or 0), 3),
            "avg_feed_per_record_kg": round(float(row[8] or 0), 3),
            "avg_per_animal_kg": round(float(row[9] or 0), 4),
            "first_record": str(row[10]) if row[10] else None,
            "last_record": str(row[11]) if row[11] else None,
        })
    total_feed = sum(g["total_feed_kg"] for g in groups)
    total_animals = sum(g["animal_count"] or 0 for g in groups)
    return {
        "location_id": location_id,
        "groups": groups,
        "total_groups": len(groups),
        "total_animals": total_animals,
        "total_feed_kg": round(total_feed, 3),
    }


def compute_feed_conversion_ratio(conn, location_id: str) -> dict[str, Any]:
    """Compute feed conversion ratio (kg feed per kg weight gain) per livestock group."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT lg.id, lg.group_name, lg.species,
               lg.animal_count, lg.average_weight_kg,
               SUM(fir.quantity_kg) AS total_feed_kg,
               COUNT(fir.id) AS feeding_days,
               AVG(fir.per_animal_kg) AS avg_daily_per_animal_kg
        FROM livestock_group lg
        JOIN feed_intake_record fir ON fir.livestock_group_id = lg.id
            AND fir.status IN ('verified', 'published')
        WHERE lg.location_id = %s AND lg.status = 'active'
        GROUP BY lg.id, lg.group_name, lg.species, lg.animal_count, lg.average_weight_kg
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()
    ratios = []
    for row in rows:
        total_feed = float(row[5] or 0)
        animals = row[3] or 0
        avg_weight = float(row[4] or 0)
        days = row[6] or 0
        daily_per_animal = float(row[7] or 0)
        daily_total = daily_per_animal * animals if daily_per_animal and animals else 0
        ratios.append({
            "group_id": str(row[0]),
            "group_name": row[1],
            "species": row[2],
            "animal_count": animals,
            "average_weight_kg": round(avg_weight, 2),
            "total_feed_kg": round(total_feed, 3),
            "feeding_days": days,
            "avg_daily_per_animal_kg": round(daily_per_animal, 4),
            "daily_total_feed_kg": round(daily_total, 3),
        })
    return {
        "location_id": location_id,
        "groups": ratios,
    }
