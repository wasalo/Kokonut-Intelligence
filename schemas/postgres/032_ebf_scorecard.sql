-- ============================================================
-- 032_ebf_scorecard.sql — EBF scorecard foundation
-- ============================================================

CREATE TABLE IF NOT EXISTS ebf_pillar (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pillar_key VARCHAR(50) NOT NULL UNIQUE,
    pillar_name VARCHAR(100) NOT NULL,
    description TEXT,
    framework_id UUID REFERENCES impact_framework(id) ON DELETE RESTRICT,
    dimension_id UUID REFERENCES impact_dimension(id) ON DELETE RESTRICT,
    sort_order INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ebf_pillar_framework ON ebf_pillar(framework_id);
CREATE INDEX IF NOT EXISTS idx_ebf_pillar_dimension ON ebf_pillar(dimension_id);
CREATE INDEX IF NOT EXISTS idx_ebf_pillar_status ON ebf_pillar(status);

ALTER TABLE ebf_pillar DROP CONSTRAINT IF EXISTS chk_ebf_pillar_status;
ALTER TABLE ebf_pillar ADD CONSTRAINT chk_ebf_pillar_status CHECK (status IN ('active', 'inactive'));

CREATE TABLE IF NOT EXISTS ebf_rubric_band (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pillar_id UUID NOT NULL REFERENCES ebf_pillar(id) ON DELETE CASCADE,
    pillar_key VARCHAR(50) NOT NULL REFERENCES ebf_pillar(pillar_key) ON DELETE CASCADE,
    score_value INTEGER NOT NULL CHECK (score_value BETWEEN 0 AND 10),
    band_min NUMERIC(3,1) NOT NULL CHECK (band_min >= 0 AND band_min <= 10),
    band_max NUMERIC(3,1) NOT NULL CHECK (band_max >= 0 AND band_max <= 10),
    band_label VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    required_practices TEXT[] DEFAULT '{}',
    evidence_requirements TEXT[] DEFAULT '{}',
    rubric_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pillar_id, score_value, rubric_version)
);

CREATE INDEX IF NOT EXISTS idx_ebf_rubric_band_pillar ON ebf_rubric_band(pillar_id);
CREATE INDEX IF NOT EXISTS idx_ebf_rubric_band_version ON ebf_rubric_band(rubric_version);

ALTER TABLE ebf_rubric_band DROP CONSTRAINT IF EXISTS chk_ebf_rubric_band_range;
ALTER TABLE ebf_rubric_band ADD CONSTRAINT chk_ebf_rubric_band_range CHECK (band_min <= band_max);

CREATE TABLE IF NOT EXISTS ebf_scorecard (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE RESTRICT,
    farm_id UUID REFERENCES farm(id) ON DELETE RESTRICT,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    overall_score NUMERIC(3,1) CHECK (overall_score IS NULL OR (overall_score >= 0 AND overall_score <= 10)),
    overall_confidence VARCHAR(30),
    status VARCHAR(50) DEFAULT 'draft',
    rubric_version VARCHAR(50) NOT NULL,
    calibration_report_required BOOLEAN DEFAULT TRUE,
    calibration_report_url TEXT,
    calibration_report_hash VARCHAR(64),
    calibration_method VARCHAR(50),
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    public_claim_allowed BOOLEAN DEFAULT FALSE,
    reviewer_notes TEXT,
    metadata JSONB DEFAULT '{}',
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(location_id, period_start, period_end, rubric_version)
);

CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_location ON ebf_scorecard(location_id);
CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_farm ON ebf_scorecard(farm_id);
CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_period ON ebf_scorecard(period_start, period_end);
CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_status ON ebf_scorecard(status);
CREATE INDEX IF NOT EXISTS idx_ebf_scorecard_maturity ON ebf_scorecard(evidence_maturity_level);

ALTER TABLE ebf_scorecard DROP CONSTRAINT IF EXISTS chk_ebf_scorecard_lifecycle;
ALTER TABLE ebf_scorecard ADD CONSTRAINT chk_ebf_scorecard_lifecycle CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected'));

ALTER TABLE ebf_scorecard DROP CONSTRAINT IF EXISTS chk_ebf_scorecard_period;
ALTER TABLE ebf_scorecard ADD CONSTRAINT chk_ebf_scorecard_period CHECK (period_start <= period_end);

ALTER TABLE ebf_scorecard DROP CONSTRAINT IF EXISTS chk_ebf_scorecard_confidence;
ALTER TABLE ebf_scorecard ADD CONSTRAINT chk_ebf_scorecard_confidence CHECK (
    overall_confidence IS NULL OR overall_confidence IN ('high', 'moderate', 'low', 'insufficient_evidence')
);

ALTER TABLE ebf_scorecard DROP CONSTRAINT IF EXISTS chk_ebf_scorecard_public_maturity;
ALTER TABLE ebf_scorecard ADD CONSTRAINT chk_ebf_scorecard_public_maturity CHECK (
    status != 'published'
    OR (
        evidence_maturity_level >= 4
        AND public_claim_allowed = TRUE
    )
);

ALTER TABLE ebf_scorecard DROP CONSTRAINT IF EXISTS chk_ebf_scorecard_calibration_report;
ALTER TABLE ebf_scorecard ADD CONSTRAINT chk_ebf_scorecard_calibration_report CHECK (
    status NOT IN ('verified', 'published')
    OR calibration_report_required = FALSE
    OR NULLIF(TRIM(COALESCE(calibration_report_url, '')), '') IS NOT NULL
    OR NULLIF(TRIM(COALESCE(calibration_report_hash, '')), '') IS NOT NULL
);

CREATE TABLE IF NOT EXISTS ebf_score (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scorecard_id UUID NOT NULL REFERENCES ebf_scorecard(id) ON DELETE CASCADE,
    pillar_id UUID NOT NULL REFERENCES ebf_pillar(id) ON DELETE RESTRICT,
    pillar_key VARCHAR(50) NOT NULL REFERENCES ebf_pillar(pillar_key) ON DELETE RESTRICT,
    metric_value_id UUID REFERENCES metric_value(id) ON DELETE SET NULL,
    impact_claim_id UUID REFERENCES impact_claim(id) ON DELETE SET NULL,
    raw_value NUMERIC(15,4),
    raw_unit VARCHAR(50),
    normalized_score NUMERIC(3,1) NOT NULL CHECK (normalized_score >= 0 AND normalized_score <= 10),
    rubric_band_id UUID REFERENCES ebf_rubric_band(id) ON DELETE SET NULL,
    trend_direction VARCHAR(30),
    confidence_level VARCHAR(30),
    evidence_maturity_level INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level),
    public_score_allowed BOOLEAN DEFAULT FALSE,
    evidence_summary TEXT,
    uncertainty_notes TEXT,
    reviewer_notes TEXT,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(scorecard_id, pillar_id)
);

CREATE INDEX IF NOT EXISTS idx_ebf_score_scorecard ON ebf_score(scorecard_id);
CREATE INDEX IF NOT EXISTS idx_ebf_score_pillar ON ebf_score(pillar_id);
CREATE INDEX IF NOT EXISTS idx_ebf_score_metric_value ON ebf_score(metric_value_id);
ALTER TABLE ebf_score ADD COLUMN IF NOT EXISTS impact_claim_id UUID REFERENCES impact_claim(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_ebf_score_impact_claim ON ebf_score(impact_claim_id);
CREATE INDEX IF NOT EXISTS idx_ebf_score_maturity ON ebf_score(evidence_maturity_level);

ALTER TABLE ebf_score DROP CONSTRAINT IF EXISTS chk_ebf_score_confidence;
ALTER TABLE ebf_score ADD CONSTRAINT chk_ebf_score_confidence CHECK (
    confidence_level IS NULL OR confidence_level IN ('high', 'moderate', 'low', 'insufficient_evidence')
);

ALTER TABLE ebf_score DROP CONSTRAINT IF EXISTS chk_ebf_score_trend;
ALTER TABLE ebf_score ADD CONSTRAINT chk_ebf_score_trend CHECK (
    trend_direction IS NULL OR trend_direction IN ('improving', 'stable', 'declining', 'insufficient_data')
);

ALTER TABLE ebf_score DROP CONSTRAINT IF EXISTS chk_ebf_score_public_maturity;
ALTER TABLE ebf_score ADD CONSTRAINT chk_ebf_score_public_maturity CHECK (
    public_score_allowed = FALSE OR evidence_maturity_level >= 4
);

ALTER TABLE ebf_score DROP CONSTRAINT IF EXISTS chk_ebf_score_public_carbon_level6;
ALTER TABLE ebf_score ADD CONSTRAINT chk_ebf_score_public_carbon_level6 CHECK (
    NOT (public_score_allowed = TRUE AND pillar_key = 'carbon_sequestration')
    OR evidence_maturity_level = 6
);

CREATE TABLE IF NOT EXISTS ebf_score_evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    score_id UUID NOT NULL REFERENCES ebf_score(id) ON DELETE CASCADE,
    evidence_type VARCHAR(50) NOT NULL,
    evidence_id UUID NOT NULL,
    evidence_maturity_level INTEGER REFERENCES evidence_maturity_level(level),
    evidence_summary TEXT,
    source_is_public_safe BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(score_id, evidence_type, evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_ebf_score_evidence_score ON ebf_score_evidence(score_id);
CREATE INDEX IF NOT EXISTS idx_ebf_score_evidence_type ON ebf_score_evidence(evidence_type);
CREATE INDEX IF NOT EXISTS idx_ebf_score_evidence_maturity ON ebf_score_evidence(evidence_maturity_level);

ALTER TABLE ebf_score_evidence DROP CONSTRAINT IF EXISTS chk_ebf_score_evidence_type;
ALTER TABLE ebf_score_evidence ADD CONSTRAINT chk_ebf_score_evidence_type CHECK (evidence_type IN (
    'metric_value', 'soil_sample', 'species_observation', 'water_analysis', 'remote_sensing_observation',
    'stakeholder_feedback', 'stakeholder_outcome', 'impact_claim', 'attestation_record', 'report_snapshot', 'file_upload'
));

CREATE OR REPLACE VIEW v_public_ebf_scorecard AS
SELECT
    esc.id AS scorecard_id,
    esc.location_id,
    l.name AS location_name,
    esc.farm_id,
    f.name AS farm_name,
    esc.period_start,
    esc.period_end,
    esc.overall_score,
    esc.overall_confidence,
    esc.rubric_version,
    esc.evidence_maturity_level AS scorecard_evidence_maturity_level,
    em.label AS scorecard_evidence_maturity_label,
    es.id AS score_id,
    ep.pillar_key,
    ep.pillar_name,
    es.normalized_score,
    es.confidence_level,
    es.trend_direction,
    es.evidence_maturity_level AS score_evidence_maturity_level,
    sem.label AS score_evidence_maturity_label,
    es.evidence_summary,
    es.uncertainty_notes
FROM ebf_scorecard esc
JOIN location l ON l.id = esc.location_id
LEFT JOIN farm f ON f.id = esc.farm_id
JOIN ebf_score es ON es.scorecard_id = esc.id
JOIN ebf_pillar ep ON ep.id = es.pillar_id
LEFT JOIN evidence_maturity_level em ON em.level = esc.evidence_maturity_level
LEFT JOIN evidence_maturity_level sem ON sem.level = es.evidence_maturity_level
WHERE esc.status = 'published'
  AND esc.public_claim_allowed = TRUE
  AND esc.evidence_maturity_level >= 4
  AND es.public_score_allowed = TRUE
  AND es.evidence_maturity_level >= 4
  AND (
      ep.pillar_key != 'carbon_sequestration'
      OR (
          es.evidence_maturity_level = 6
          AND EXISTS (
              SELECT 1 FROM impact_claim ic
              WHERE ic.id = es.impact_claim_id
                AND ic.claim_category = 'carbon'
                AND ic.claim_type = 'third_party_verified_claim'
                AND ic.evidence_maturity = 6
                AND ic.status = 'published'
                AND NULLIF(TRIM(COALESCE(ic.external_verifier, '')), '') IS NOT NULL
                AND NULLIF(TRIM(COALESCE(ic.methodology_ref, '')), '') IS NOT NULL
          )
      )
  )
  AND EXISTS (
      SELECT 1 FROM ebf_score_evidence ese
      WHERE ese.score_id = es.id
  )
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = esc.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_public_ebf_scorecard_summary AS
SELECT
    esc.id AS scorecard_id,
    esc.location_id,
    l.name AS location_name,
    esc.farm_id,
    f.name AS farm_name,
    esc.period_start,
    esc.period_end,
    esc.overall_score,
    esc.overall_confidence,
    esc.rubric_version,
    esc.evidence_maturity_level,
    em.label AS evidence_maturity_label,
    COUNT(es.id) AS pillar_count,
    COUNT(es.id) FILTER (WHERE es.evidence_maturity_level >= 4) AS public_safe_pillar_count,
    MIN(es.evidence_maturity_level) AS min_pillar_evidence_maturity,
    MAX(es.evidence_maturity_level) AS max_pillar_evidence_maturity,
    'Public EBF scorecards preserve maturity and confidence context; do not use as farm ranking.' AS caveat
FROM ebf_scorecard esc
JOIN location l ON l.id = esc.location_id
LEFT JOIN farm f ON f.id = esc.farm_id
JOIN ebf_score es ON es.scorecard_id = esc.id
LEFT JOIN evidence_maturity_level em ON em.level = esc.evidence_maturity_level
WHERE esc.status = 'published'
  AND esc.public_claim_allowed = TRUE
  AND esc.evidence_maturity_level >= 4
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = esc.location_id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY esc.id, esc.location_id, l.name, esc.farm_id, f.name, esc.period_start, esc.period_end,
         esc.overall_score, esc.overall_confidence, esc.rubric_version, esc.evidence_maturity_level, em.label
HAVING COUNT(es.id) = 7
   AND COUNT(es.id) = COUNT(es.id) FILTER (WHERE es.public_score_allowed = TRUE AND es.evidence_maturity_level >= 4)
   AND COUNT(es.id) = COUNT(es.id) FILTER (
       WHERE EXISTS (SELECT 1 FROM ebf_score_evidence ese WHERE ese.score_id = es.id)
   )
   AND COUNT(es.id) FILTER (WHERE es.pillar_key = 'carbon_sequestration' AND es.evidence_maturity_level < 6) = 0
   AND COUNT(es.id) FILTER (
       WHERE es.pillar_key = 'carbon_sequestration'
         AND NOT EXISTS (
             SELECT 1 FROM impact_claim ic
             WHERE ic.id = es.impact_claim_id
               AND ic.claim_category = 'carbon'
               AND ic.claim_type = 'third_party_verified_claim'
               AND ic.evidence_maturity = 6
               AND ic.status = 'published'
               AND NULLIF(TRIM(COALESCE(ic.external_verifier, '')), '') IS NOT NULL
               AND NULLIF(TRIM(COALESCE(ic.methodology_ref, '')), '') IS NOT NULL
         )
   ) = 0;

CREATE OR REPLACE VIEW v_public_ebf_pillar_summary AS
SELECT
    ep.pillar_key,
    ep.pillar_name,
    COUNT(DISTINCT esc.location_id) AS location_count,
    COUNT(DISTINCT esc.id) AS scorecard_count,
    ROUND(AVG(es.normalized_score)::numeric, 2) AS avg_score,
    COUNT(*) FILTER (WHERE es.confidence_level = 'high') AS high_confidence_count,
    COUNT(*) FILTER (WHERE es.confidence_level = 'moderate') AS moderate_confidence_count,
    COUNT(*) FILTER (WHERE es.confidence_level = 'low') AS low_confidence_count,
    COUNT(*) FILTER (WHERE es.confidence_level = 'insufficient_evidence') AS insufficient_evidence_count,
    MAX(ese.created_at) AS latest_evidence_linked_at,
    'Aggregate by pillar and evidence context; do not rank farms as interchangeable units.' AS caveat
FROM ebf_score es
JOIN ebf_scorecard esc ON esc.id = es.scorecard_id
JOIN ebf_pillar ep ON ep.id = es.pillar_id
JOIN ebf_score_evidence ese ON ese.score_id = es.id
WHERE esc.status = 'published'
  AND esc.public_claim_allowed = TRUE
  AND esc.evidence_maturity_level >= 4
  AND es.public_score_allowed = TRUE
  AND es.evidence_maturity_level >= 4
  AND (
      ep.pillar_key != 'carbon_sequestration'
      OR (
          es.evidence_maturity_level = 6
          AND EXISTS (
              SELECT 1 FROM impact_claim ic
              WHERE ic.id = es.impact_claim_id
                AND ic.claim_category = 'carbon'
                AND ic.claim_type = 'third_party_verified_claim'
                AND ic.evidence_maturity = 6
                AND ic.status = 'published'
                AND NULLIF(TRIM(COALESCE(ic.external_verifier, '')), '') IS NOT NULL
                AND NULLIF(TRIM(COALESCE(ic.methodology_ref, '')), '') IS NOT NULL
          )
      )
  )
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = esc.location_id
        AND fr.status IN ('verified', 'published')
  )
GROUP BY ep.pillar_key, ep.pillar_name, ep.sort_order
ORDER BY ep.sort_order;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('ebf-scorecard-p0-v1', 'EBF P0 scorecard pillars, rubric bands, scores, evidence links, gates, and public-safe views', 'schema 032')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
