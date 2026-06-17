-- Public Aggregate Dashboard — non-sensitive, aggregate data for public view
-- FR9: Public dashboards use aggregate or non-sensitive data

CREATE OR REPLACE VIEW v_public_farm_summary AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    l.country,
    l.region,
    COUNT(DISTINCT f.id) AS farm_count,
    COUNT(DISTINCT p.id) AS plot_count,
    ROUND(COALESCE(SUM(DISTINCT f.total_area), 0)::numeric, 2) AS total_area_ha,
    l.status
FROM location l
LEFT JOIN farm f ON f.location_id = l.id
LEFT JOIN plot p ON p.farm_id = f.id
WHERE l.status = 'active'
GROUP BY l.id, l.name, l.country, l.region, l.status;

CREATE OR REPLACE VIEW v_public_metric_summary AS
SELECT
    mv.location_id,
    l.name AS location_name,
    md.metric_key,
    md.display_name,
    md.unit,
    mv.value AS latest_value,
    mv.computed_at
FROM metric_value mv
JOIN metric_definition md ON mv.metric_id = md.id
JOIN location l ON mv.location_id = l.id
WHERE md.active = TRUE
  AND mv.verified = TRUE
  AND mv.computed_at = (
      SELECT MAX(mv2.computed_at)
      FROM metric_value mv2
      WHERE mv2.metric_id = mv.metric_id
        AND mv2.location_id = mv.location_id
        AND mv2.verified = TRUE
  );

CREATE OR REPLACE VIEW v_public_attestation_summary AS
SELECT
    l.id AS location_id,
    l.name AS location_name,
    ar.claim_type,
    ar.chain,
    COUNT(*) AS total_attestations,
    COUNT(*) FILTER (WHERE ar.status = 'published') AS published_count,
    MIN(ar.attested_at) AS first_attestation,
    MAX(ar.attested_at) AS latest_attestation
FROM attestation_record ar
JOIN location l ON ar.subject_type = 'location' AND ar.subject_id = l.id
WHERE ar.status IN ('verified', 'published')
GROUP BY l.id, l.name, ar.claim_type, ar.chain;
