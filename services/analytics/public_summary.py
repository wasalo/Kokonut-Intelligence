"""Public location roll-up over existing governed projections."""

from __future__ import annotations

from services.common.database import get_connection


def location_summary(location_id: str) -> dict | None:
    with get_connection(connect_timeout=3) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        location = connection.execute(
            """SELECT location_id AS id, location_name AS name, country, region, status
               FROM public.v_public_farm_summary WHERE location_id = :location_id""",
            {"location_id": location_id},
        ).first()
        if location is None:
            return None
        metrics = connection.execute(
            """SELECT COUNT(DISTINCT metric_key) AS metric_count,
                      MAX(computed_at) AS latest_computed_at
               FROM public.v_public_metric_summary WHERE location_id = :location_id""",
            {"location_id": location_id},
        ).first()
        attestations = connection.execute(
            """SELECT COALESCE(SUM(total_attestations), 0) AS total_attestations,
                      COALESCE(SUM(published_count), 0) AS published_count,
                      MAX(latest_attestation) AS latest_attestation
               FROM public.v_public_attestation_summary WHERE location_id = :location_id""",
            {"location_id": location_id},
        ).first()
        return {"summary_type": "public_location_summary", "location_id": location_id,
                "location": location, "metrics": metrics, "attestations": attestations}
