-- 603_location_bound_landscape_references.sql
-- Prevent cross-location habitat references and make legacy projections
-- location-aware without rewriting or rejecting historical mismatches.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_habitat_zone_location_id
    ON habitat_zone (location_id, id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.wildlife_corridor'::regclass
           AND conname = 'fk_corridor_source_habitat_location'
    ) THEN
        ALTER TABLE public.wildlife_corridor
            ADD CONSTRAINT fk_corridor_source_habitat_location
            FOREIGN KEY (location_id, source_habitat_id)
            REFERENCES public.habitat_zone (location_id, id)
            ON DELETE SET NULL (source_habitat_id) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.wildlife_corridor'::regclass
           AND conname = 'fk_corridor_target_habitat_location'
    ) THEN
        ALTER TABLE public.wildlife_corridor
            ADD CONSTRAINT fk_corridor_target_habitat_location
            FOREIGN KEY (location_id, target_habitat_id)
            REFERENCES public.habitat_zone (location_id, id)
            ON DELETE SET NULL (target_habitat_id) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.buffer_zone_monitoring'::regclass
           AND conname = 'fk_buffer_habitat_location'
    ) THEN
        ALTER TABLE public.buffer_zone_monitoring
            ADD CONSTRAINT fk_buffer_habitat_location
            FOREIGN KEY (location_id, habitat_zone_id)
            REFERENCES public.habitat_zone (location_id, id)
            ON DELETE SET NULL (habitat_zone_id) NOT VALID;
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_corridor_location_habitats
    ON wildlife_corridor (location_id, source_habitat_id, target_habitat_id);
CREATE INDEX IF NOT EXISTS idx_buffer_location_habitat
    ON buffer_zone_monitoring (location_id, habitat_zone_id)
    WHERE habitat_zone_id IS NOT NULL;

CREATE OR REPLACE VIEW v_habitat_summary AS
SELECT
    hz.id AS habitat_id,
    hz.location_id,
    l.name AS location_name,
    hz.zone_name,
    hz.habitat_type,
    hz.area_ha,
    hz.perimeter_m,
    hz.biodiversity_value,
    hz.status,
    (SELECT COUNT(*) FROM wildlife_corridor wc
     WHERE wc.location_id = hz.location_id
       AND (wc.source_habitat_id = hz.id OR wc.target_habitat_id = hz.id)
    ) AS corridor_count,
    (SELECT COUNT(*) FROM buffer_zone_monitoring bzm
     WHERE bzm.location_id = hz.location_id
       AND bzm.habitat_zone_id = hz.id AND bzm.compliant = TRUE
    ) AS compliant_buffer_checks,
    (SELECT COUNT(*) FROM buffer_zone_monitoring bzm
     WHERE bzm.location_id = hz.location_id AND bzm.habitat_zone_id = hz.id
    ) AS total_buffer_checks,
    hz.created_at,
    hz.updated_at
FROM habitat_zone hz
JOIN location l ON l.id = hz.location_id;

CREATE OR REPLACE VIEW v_corridor_status AS
SELECT
    wc.id AS corridor_id,
    wc.location_id,
    l.name AS location_name,
    wc.corridor_name,
    src.zone_name AS source_habitat,
    tgt.zone_name AS target_habitat,
    wc.width_m,
    wc.length_m,
    wc.vegetation_type,
    wc.condition,
    wc.last_survey_date,
    wc.status,
    CASE
        WHEN wc.condition IN ('excellent', 'good') THEN 'connected'
        WHEN wc.condition = 'fair' THEN 'partially_connected'
        ELSE 'disconnected'
    END AS connectivity_status,
    wc.created_at,
    wc.updated_at
FROM wildlife_corridor wc
JOIN location l ON l.id = wc.location_id
LEFT JOIN habitat_zone src
       ON src.id = wc.source_habitat_id AND src.location_id = wc.location_id
LEFT JOIN habitat_zone tgt
       ON tgt.id = wc.target_habitat_id AND tgt.location_id = wc.location_id;

CREATE OR REPLACE VIEW v_buffer_compliance AS
SELECT
    bzm.location_id,
    l.name AS location_name,
    bzm.habitat_zone_id,
    hz.zone_name AS habitat_zone_name,
    COUNT(*) AS total_checks,
    COUNT(*) FILTER (WHERE bzm.compliant = TRUE) AS compliant_checks,
    ROUND(
        COUNT(*) FILTER (WHERE bzm.compliant = TRUE)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100, 1
    ) AS compliance_rate_pct,
    AVG(bzm.buffer_width_m) AS avg_buffer_width_m,
    AVG(bzm.minimum_required_m) AS avg_minimum_required_m,
    AVG(bzm.vegetation_coverage_pct) AS avg_vegetation_coverage_pct,
    COUNT(*) FILTER (WHERE bzm.erosion_observed = TRUE) AS erosion_incidents,
    MAX(bzm.check_date) AS last_check_date
FROM buffer_zone_monitoring bzm
JOIN location l ON l.id = bzm.location_id
LEFT JOIN habitat_zone hz
       ON hz.id = bzm.habitat_zone_id AND hz.location_id = bzm.location_id
GROUP BY bzm.location_id, l.name, bzm.habitat_zone_id, hz.zone_name;

COMMIT;
