"""Aggregate-only preflight for location-bound landscape habitat references.

The query intentionally returns global counts only. It never selects location,
habitat, corridor, or monitoring-row identifiers or descriptive fields.
Callers must use a dedicated connection because the function starts a
repeatable-read, read-only transaction and leaves transaction completion to the
caller.
"""

from __future__ import annotations

from typing import Any

REFERENCE_TYPES = (
    "corridor_source",
    "corridor_target",
    "buffer_habitat",
)

def get_location_reference_mismatch_counts(connection: Any) -> dict[str, Any]:
    """Return safe global counts from a new, dedicated database connection.

    The first statement makes the transaction repeatable-read and read-only.
    No transaction is committed here so that connection ownership and cleanup
    remain explicit at the CLI boundary.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute("SET LOCAL lock_timeout = '2s'")
        cursor.execute("SET LOCAL statement_timeout = '30s'")
        cursor.execute(
            """
            SELECT 'corridor_source' AS reference_type, COUNT(*)::bigint AS mismatch_count
            FROM public.wildlife_corridor AS corridor
            WHERE corridor.source_habitat_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.habitat_zone AS habitat
                  WHERE habitat.id = corridor.source_habitat_id
                    AND habitat.location_id = corridor.location_id
              )
            UNION ALL
            SELECT 'corridor_target' AS reference_type, COUNT(*)::bigint AS mismatch_count
            FROM public.wildlife_corridor AS corridor
            WHERE corridor.target_habitat_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.habitat_zone AS habitat
                  WHERE habitat.id = corridor.target_habitat_id
                    AND habitat.location_id = corridor.location_id
              )
            UNION ALL
            SELECT 'buffer_habitat' AS reference_type, COUNT(*)::bigint AS mismatch_count
            FROM public.buffer_zone_monitoring AS monitoring
            WHERE monitoring.habitat_zone_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.habitat_zone AS habitat
                  WHERE habitat.id = monitoring.habitat_zone_id
                    AND habitat.location_id = monitoring.location_id
              )
            ORDER BY reference_type
            """
        )
        rows = cursor.fetchall()

    counts = {reference_type: 0 for reference_type in REFERENCE_TYPES}
    seen: set[str] = set()
    for reference_type, mismatch_count in rows:
        if reference_type not in counts:
            raise ValueError("preflight query returned an unknown reference category")
        if reference_type in seen:
            raise ValueError("preflight query returned a duplicate reference category")
        if type(mismatch_count) is not int or mismatch_count < 0:
            raise ValueError("preflight query returned an invalid aggregate count")
        seen.add(reference_type)
        counts[reference_type] = mismatch_count
    if seen != set(REFERENCE_TYPES):
        raise ValueError("preflight query did not return every reference category")

    total = sum(counts.values())
    return {
        "scope": "all_locations_global_aggregate",
        "location_reference_mismatch_counts": counts,
        "total_location_reference_mismatch_count": total,
        "status": "mismatches_present" if total else "no_mismatches",
    }
