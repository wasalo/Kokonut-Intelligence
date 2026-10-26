-- ============================================================
-- 528_location_scoped_stakeholder_landscape.sql
-- Keep canonical party identity network-wide while scoping operational
-- relationship, interest, identifier, and salience aggregates by location.
-- ============================================================

CREATE OR REPLACE VIEW v_stakeholder_landscape_by_location
WITH (security_invoker = true)
AS
WITH scoped_interests AS (
    SELECT
        si.id AS interest_id,
        si.scope_id AS location_id,
        si.party_id,
        si.status,
        si.updated_at
    FROM stakeholder_interest si
    JOIN location l ON l.id = si.scope_id
    WHERE si.scope_type IN ('location', 'farm')
),
scoped_party_locations AS (
    SELECT l.id AS location_id, pi.party_id
    FROM party_identifier pi
    JOIN location l
      ON pi.identifier_type = 'location_id'
     AND pi.identifier_value = l.id::text
     AND pi.verification_status = 'verified'

    UNION

    SELECT pr.scope_id AS location_id, pr.from_party_id AS party_id
    FROM party_relationship pr
    JOIN location l ON l.id = pr.scope_id
    WHERE pr.scope_type IN ('location', 'farm')

    UNION

    SELECT pr.scope_id AS location_id, pr.to_party_id AS party_id
    FROM party_relationship pr
    JOIN location l ON l.id = pr.scope_id
    WHERE pr.scope_type IN ('location', 'farm')

    UNION

    SELECT si.scope_id AS location_id, si.party_id
    FROM stakeholder_interest si
    JOIN location l ON l.id = si.scope_id
    WHERE si.scope_type IN ('location', 'farm')
),
location_identifier_counts AS (
    SELECT l.id AS location_id, pi.party_id, COUNT(*) AS identifier_count
    FROM party_identifier pi
    JOIN location l
      ON pi.identifier_type = 'location_id'
     AND pi.identifier_value = l.id::text
     AND pi.verification_status = 'verified'
    GROUP BY l.id, pi.party_id
),
scoped_relationships AS (
    SELECT pr.scope_id AS location_id, pr.from_party_id AS party_id,
           pr.status, pr.updated_at
    FROM party_relationship pr
    JOIN location l ON l.id = pr.scope_id
    WHERE pr.scope_type IN ('location', 'farm')

    UNION ALL

    SELECT pr.scope_id AS location_id, pr.to_party_id AS party_id,
           pr.status, pr.updated_at
    FROM party_relationship pr
    JOIN location l ON l.id = pr.scope_id
    WHERE pr.scope_type IN ('location', 'farm')
),
location_relationship_counts AS (
    SELECT location_id, party_id,
           COUNT(*) FILTER (WHERE status = 'active') AS active_relationship_count,
           MAX(updated_at) AS last_relationship_updated_at
    FROM scoped_relationships
    GROUP BY location_id, party_id
),
location_interest_counts AS (
    SELECT location_id, party_id,
           COUNT(*) FILTER (WHERE status NOT IN ('retired', 'met')) AS open_interest_count,
           MAX(updated_at) AS last_interest_updated_at
    FROM scoped_interests
    GROUP BY location_id, party_id
),
latest_location_salience AS (
    SELECT DISTINCT ON (si.location_id, si.party_id)
           si.location_id,
           si.party_id,
           ssa.advisory_score,
           ssa.review_status,
           ssa.assessed_at
    FROM scoped_interests si
    JOIN stakeholder_salience_assessment ssa
      ON ssa.interest_id = si.interest_id
     AND ssa.party_id = si.party_id
     AND ssa.is_current = TRUE
    ORDER BY si.location_id, si.party_id, ssa.assessed_at DESC, ssa.id DESC
)
SELECT
    spl.location_id,
    p.id AS party_id,
    p.party_type,
    p.display_name,
    p.status AS party_status,
    p.privacy_level,
    COALESCE(lic.identifier_count, 0) AS identifier_count,
    COALESCE(lrc.active_relationship_count, 0) AS active_relationship_count,
    COALESCE(lici.open_interest_count, 0) AS open_interest_count,
    salience.advisory_score,
    salience.review_status AS salience_review_status,
    GREATEST(
        p.updated_at,
        COALESCE(salience.assessed_at, p.updated_at),
        COALESCE(lrc.last_relationship_updated_at, p.updated_at),
        COALESCE(lici.last_interest_updated_at, p.updated_at)
    ) AS last_updated_at
FROM scoped_party_locations spl
JOIN party p ON p.id = spl.party_id
LEFT JOIN location_identifier_counts lic
  ON lic.location_id = spl.location_id AND lic.party_id = spl.party_id
LEFT JOIN location_relationship_counts lrc
  ON lrc.location_id = spl.location_id AND lrc.party_id = spl.party_id
LEFT JOIN location_interest_counts lici
  ON lici.location_id = spl.location_id AND lici.party_id = spl.party_id
LEFT JOIN latest_location_salience salience
  ON salience.location_id = spl.location_id AND salience.party_id = spl.party_id;

COMMENT ON VIEW v_stakeholder_landscape_by_location IS
    'Internal stakeholder landscape with explicit location lineage; only location-scoped identifiers, relationships, interests, and salience contribute to aggregates.';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        EXECUTE 'GRANT SELECT ON v_stakeholder_landscape_by_location TO kokonut_runtime';
    END IF;
END;
$$;
