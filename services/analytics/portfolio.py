"""Portfolio-level impact summaries with theme and confidence labels."""

from __future__ import annotations

from typing import Any

import psycopg2.extras


def confidence_label(avg_maturity: float, claim_count: int, location_count: int) -> str:
    """Return a conservative confidence label for portfolio roll-ups."""
    if claim_count == 0 or location_count == 0:
        return "insufficient_evidence"
    if avg_maturity >= 5.5 and claim_count >= 2:
        return "high"
    if avg_maturity >= 4:
        return "moderate"
    if avg_maturity >= 2:
        return "emerging"
    return "low"


def portfolio_theme_summary(conn) -> dict[str, Any]:
    """Summarize portfolio impact by SDG/theme without ranking farms."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        WITH theme_claims AS (
            SELECT
                COALESCE(s.name, 'Unmapped theme') AS theme,
                COALESCE(fim.sdg_number::text, 'unmapped') AS theme_key,
                ic.location_id,
                ic.claim_category,
                ic.evidence_maturity,
                ic.public_claim,
                ic.status,
                ic.external_verifier,
                ic.methodology_ref
            FROM impact_claim ic
            LEFT JOIN stakeholder_outcome so ON so.id = ic.stakeholder_outcome_id
            LEFT JOIN farm_impact_mapping fim ON fim.location_id = ic.location_id
                AND (so.sdg_number IS NULL OR fim.sdg_number = so.sdg_number)
                AND fim.status IN ('verified', 'published')
            LEFT JOIN sdg s ON s.sdg_number = COALESCE(so.sdg_number, fim.sdg_number)
            WHERE ic.status IN ('verified', 'published')
        )
        SELECT
            theme_key,
            theme,
            COUNT(DISTINCT location_id) AS location_count,
            COUNT(*) AS claim_count,
            ROUND(AVG(evidence_maturity)::numeric, 2) AS avg_evidence_maturity,
            COUNT(*) FILTER (WHERE public_claim = TRUE) AS public_claim_count,
            COUNT(*) FILTER (
                WHERE public_claim = TRUE
                  AND claim_category = 'carbon'
                  AND evidence_maturity = 6
                  AND external_verifier IS NOT NULL
                  AND methodology_ref IS NOT NULL
            ) AS level6_public_carbon_claim_count
        FROM theme_claims
        GROUP BY theme_key, theme
        ORDER BY claim_count DESC, theme
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    themes = []
    for row in rows:
        avg_maturity = float(row["avg_evidence_maturity"] or 0)
        row["confidence_label"] = confidence_label(
            avg_maturity,
            int(row["claim_count"] or 0),
            int(row["location_count"] or 0),
        )
        row["caveat"] = "Portfolio roll-up preserves theme and maturity context; do not use as farm ranking."
        themes.append(row)

    return {
        "summary_type": "portfolio_theme_summary",
        "theme_count": len(themes),
        "themes": themes,
        "portfolio_caveat": "Compare themes and evidence maturity, not farms as interchangeable units.",
    }
