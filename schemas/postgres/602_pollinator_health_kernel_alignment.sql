-- 602_pollinator_health_kernel_alignment.sql
-- Align the pollinator service contract with migrations 154/155 while retaining
-- structured source fields and location-bound inspection history.

BEGIN;

ALTER TABLE pollinator_observation
    ADD COLUMN IF NOT EXISTS temperature_c NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS source_system VARCHAR(100),
    ADD COLUMN IF NOT EXISTS source_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS hive_record_id UUID;

ALTER TABLE pollinator_habitat
    ADD COLUMN IF NOT EXISTS bloom_start_month SMALLINT,
    ADD COLUMN IF NOT EXISTS bloom_end_month SMALLINT,
    ADD COLUMN IF NOT EXISTS water_source BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS nesting_sites TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.pollinator_habitat'::regclass
           AND conname = 'chk_pollinator_habitat_bloom_months'
    ) THEN
        ALTER TABLE public.pollinator_habitat
            ADD CONSTRAINT chk_pollinator_habitat_bloom_months CHECK (
                (bloom_start_month IS NULL OR bloom_start_month BETWEEN 1 AND 12)
                AND (bloom_end_month IS NULL OR bloom_end_month BETWEEN 1 AND 12)
            );
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_pollinator_obs_location_hive_date
    ON pollinator_observation (location_id, hive_record_id, observation_date DESC)
    WHERE hive_record_id IS NOT NULL;

ALTER TABLE pesticide_impact_log
    ADD COLUMN IF NOT EXISTS application_rate NUMERIC(14,6),
    ADD COLUMN IF NOT EXISTS rate_unit VARCHAR(32),
    ADD COLUMN IF NOT EXISTS area_treated_m2 NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS pollinator_distance_m NUMERIC(10,2);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.pesticide_impact_log'::regclass
           AND conname = 'chk_pesticide_application_measurements_nonnegative'
    ) THEN
        ALTER TABLE public.pesticide_impact_log
            ADD CONSTRAINT chk_pesticide_application_measurements_nonnegative CHECK (
                (application_rate IS NULL OR application_rate >= 0)
                AND (area_treated_m2 IS NULL OR area_treated_m2 >= 0)
                AND (pollinator_distance_m IS NULL OR pollinator_distance_m >= 0)
            );
    END IF;
END;
$$;

ALTER TABLE hive_record
    ADD COLUMN IF NOT EXISTS hive_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS frame_count INTEGER,
    ADD COLUMN IF NOT EXISTS queen_year SMALLINT,
    ADD COLUMN IF NOT EXISTS colony_strength_score SMALLINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.hive_record'::regclass
           AND conname = 'chk_hive_record_strength_score'
    ) THEN
        ALTER TABLE public.hive_record
            ADD CONSTRAINT chk_hive_record_strength_score CHECK (
                colony_strength_score IS NULL OR colony_strength_score BETWEEN 0 AND 10
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.hive_record'::regclass
           AND conname = 'chk_hive_record_frame_count_nonnegative'
    ) THEN
        ALTER TABLE public.hive_record
            ADD CONSTRAINT chk_hive_record_frame_count_nonnegative CHECK (
                frame_count IS NULL OR frame_count >= 0
            );
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_hive_record_location_id
    ON hive_record (location_id, id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public.pollinator_observation'::regclass
           AND conname = 'fk_pollinator_observation_hive_location'
    ) THEN
        ALTER TABLE public.pollinator_observation
            ADD CONSTRAINT fk_pollinator_observation_hive_location
            FOREIGN KEY (location_id, hive_record_id)
            REFERENCES public.hive_record (location_id, id) ON DELETE SET NULL (hive_record_id);
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS pollinator_hive_inspection (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id             UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    hive_record_id          UUID NOT NULL,
    inspection_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    colony_strength         VARCHAR(50)
        CHECK (colony_strength IN ('strong', 'moderate', 'weak', 'dead')),
    colony_strength_score   SMALLINT
        CHECK (colony_strength_score BETWEEN 0 AND 10),
    queen_status            VARCHAR(50)
        CHECK (queen_status IN ('present', 'absent', 'replaced', 'unknown')),
    queen_seen              BOOLEAN,
    varroa_count            INTEGER CHECK (varroa_count IS NULL OR varroa_count >= 0),
    brood_pattern           VARCHAR(100),
    honey_stores            TEXT,
    disease_signs           TEXT,
    temperament             VARCHAR(100),
    population_estimate     INTEGER
        CHECK (population_estimate IS NULL OR population_estimate >= 0),
    swarm_cells             BOOLEAN NOT NULL DEFAULT FALSE,
    notes                   TEXT,
    status                  VARCHAR(50) NOT NULL DEFAULT 'recorded'
        CHECK (status IN ('recorded', 'verified', 'reviewed', 'dismissed')),
    metadata                JSONB NOT NULL DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_pollinator_inspection_hive_location
        FOREIGN KEY (location_id, hive_record_id)
        REFERENCES hive_record (location_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pollinator_hive_inspection_location_date
    ON pollinator_hive_inspection (location_id, inspection_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_hive_inspection_hive_date
    ON pollinator_hive_inspection (location_id, hive_record_id, inspection_date DESC);
CREATE INDEX IF NOT EXISTS idx_pollinator_hive_inspection_status_date
    ON pollinator_hive_inspection (location_id, status, inspection_date DESC);

COMMENT ON TABLE pollinator_hive_inspection IS
    'Location-bound history of managed hive inspections; status is a review state and is independent of hive health.';

COMMIT;
