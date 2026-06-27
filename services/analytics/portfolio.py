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


def ebf_portfolio_summary(conn) -> dict[str, Any]:
    """Summarize EBF scorecards as a messy roll-up, not a farm ranking."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            pillar_key,
            pillar_name,
            COUNT(DISTINCT location_id) AS location_count,
            COUNT(DISTINCT scorecard_id) AS scorecard_count,
            ROUND(AVG(normalized_score)::numeric, 2) AS avg_score,
            ROUND(AVG(score_evidence_maturity_level)::numeric, 2) AS avg_evidence_maturity,
            COUNT(*) FILTER (WHERE confidence_level = 'high') AS high_confidence_count,
            COUNT(*) FILTER (WHERE confidence_level = 'moderate') AS moderate_confidence_count,
            COUNT(*) FILTER (WHERE confidence_level = 'low') AS low_confidence_count,
            COUNT(*) FILTER (WHERE confidence_level = 'insufficient_evidence') AS insufficient_evidence_count,
            COUNT(*) FILTER (WHERE score_evidence_maturity_level >= 4) AS public_safe_score_count,
            COUNT(*) FILTER (WHERE pillar_key = 'carbon_sequestration' AND score_evidence_maturity_level = 6) AS level6_carbon_score_count
        FROM v_public_ebf_scorecard
        GROUP BY pillar_key, pillar_name
        ORDER BY pillar_name
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()

    pillars = []
    for row in rows:
        avg_maturity = float(row.get("avg_evidence_maturity") or 0)
        row["portfolio_confidence_label"] = confidence_label(
            avg_maturity,
            int(row.get("scorecard_count") or 0),
            int(row.get("location_count") or 0),
        )
        row["comparison_mode"] = "messy_rollup"
        row["caveat"] = "Use pillar distributions, maturity, and confidence context; do not rank farms."
        pillars.append(row)

    return {
        "summary_type": "ebf_portfolio_messy_rollup",
        "pillar_count": len(pillars),
        "pillars": pillars,
        "portfolio_caveat": "EBF portfolio comparison is a messy roll-up by pillar, confidence, and maturity; farms are not interchangeable units.",
    }
