SELECT
    location_name,
    scorecard_id,
    pillar_name,
    normalized_score,
    confidence_level,
    evidence_maturity_label,
    evidence_count,
    public_safe_evidence_count,
    gap_status
FROM v_ebf_evidence_gap_summary
ORDER BY location_name, scorecard_id, pillar_key;
