SELECT
    location_name,
    farm_name,
    period_start,
    period_end,
    pillar_name,
    normalized_score,
    confidence_level,
    trend_direction,
    score_evidence_maturity_label,
    evidence_summary,
    uncertainty_notes
FROM v_public_ebf_scorecard
ORDER BY period_end DESC, location_name, pillar_key;
