-- ============================================================
-- 316_stakeholder_analytics_safety.sql
-- Avoid fan-trap multiplication in stakeholder landscape counts.
-- ============================================================

CREATE OR REPLACE VIEW v_stakeholder_landscape AS
WITH identifier_counts AS (
    SELECT party_id, COUNT(*) AS identifier_count
    FROM party_identifier
    GROUP BY party_id
),
relationship_counts AS (
    SELECT party_id, COUNT(*) AS active_relationship_count
    FROM (
        SELECT from_party_id AS party_id, id
        FROM party_relationship
        WHERE status = 'active'
        UNION ALL
        SELECT to_party_id AS party_id, id
        FROM party_relationship
        WHERE status = 'active'
    ) relationships
    GROUP BY party_id
),
interest_counts AS (
    SELECT party_id,
           COUNT(*) FILTER (WHERE status NOT IN ('retired', 'met')) AS open_interest_count
    FROM stakeholder_interest
    GROUP BY party_id
)
SELECT p.id AS party_id,
       p.party_type,
       p.display_name,
       p.status AS party_status,
       p.privacy_level,
       COALESCE(ic.identifier_count, 0) AS identifier_count,
       COALESCE(rc.active_relationship_count, 0) AS active_relationship_count,
       COALESCE(sc.open_interest_count, 0) AS open_interest_count,
       latest.advisory_score,
       latest.review_status AS salience_review_status,
       GREATEST(p.updated_at, COALESCE(latest.assessed_at, p.updated_at)) AS last_updated_at
FROM party p
LEFT JOIN identifier_counts ic ON ic.party_id = p.id
LEFT JOIN relationship_counts rc ON rc.party_id = p.id
LEFT JOIN interest_counts sc ON sc.party_id = p.id
LEFT JOIN LATERAL (
    SELECT advisory_score, review_status, assessed_at
    FROM stakeholder_salience_assessment ssa
    WHERE ssa.party_id = p.id
      AND ssa.is_current = TRUE
    ORDER BY assessed_at DESC, id DESC
    LIMIT 1
) latest ON TRUE;

COMMENT ON VIEW v_stakeholder_landscape IS
    'Fan-trap-safe stakeholder summary using pre-aggregated child relationships';
