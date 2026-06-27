SELECT
    pillar_name,
    location_count,
    scorecard_count,
    avg_score,
    high_confidence_count,
    moderate_confidence_count,
    low_confidence_count,
    insufficient_evidence_count,
    latest_evidence_linked_at,
    caveat
FROM v_public_ebf_pillar_summary
ORDER BY pillar_name;
