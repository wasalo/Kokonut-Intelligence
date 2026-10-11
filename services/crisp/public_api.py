"""Conservative public reads of published CRISP assessments."""

from __future__ import annotations

from services.common.database import get_connection


def latest_published_assessment(location_id: str) -> dict | None:
    """Read persisted public results without computing or publishing scores."""
    with get_connection(connect_timeout=3) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        return connection.execute(
            """SELECT assessment.id AS assessment_id, assessment.location_id,
                      assessment.period_start, assessment.period_end,
                      assessment.methodology_version, assessment.composite_score,
                      assessment.rating, assessment.confidence_level,
                      assessment.evidence_maturity_level, assessment.score_computed_at,
                      assessment.status
               FROM public.crisp_risk_assessment assessment
               JOIN public.v_public_farm_summary location
                 ON location.location_id = assessment.location_id
               WHERE assessment.location_id = :location_id
                 AND assessment.status = 'published'
               ORDER BY assessment.period_end DESC,
                        assessment.score_computed_at DESC NULLS LAST,
                        assessment.id DESC
               LIMIT 1""",
            {"location_id": location_id},
        ).first()
