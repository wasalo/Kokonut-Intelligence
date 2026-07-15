-- Migration 202: Pitch & Presentation — audience-segmented pitch templates
--
-- Tables:
--   pitch_template  – configurable pitch content per audience segment
--
-- Views:
--   v_pitch_audience_summary

BEGIN;

-- ============================================================
-- 1. pitch_template — audience-segmented pitch configurations
-- ============================================================
CREATE TABLE IF NOT EXISTS pitch_template (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    audience VARCHAR(50) NOT NULL UNIQUE
        CHECK (audience IN (
            'funders', 'operators', 'developers', 'refi', 'impact', 'elevator'
        )),
    hook TEXT NOT NULL,
    problem TEXT NOT NULL,
    solution TEXT NOT NULL,
    proof_headline TEXT NOT NULL,
    cta_label TEXT NOT NULL,
    cta_url TEXT NOT NULL,
    sections JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pt_audience ON pitch_template(audience);

-- ============================================================
-- 2. v_pitch_audience_summary — quick template overview
-- ============================================================
CREATE OR REPLACE VIEW v_pitch_audience_summary AS
SELECT
    id,
    audience,
    hook,
    cta_label,
    cta_url,
    created_at,
    updated_at
FROM pitch_template
ORDER BY audience;

COMMIT;
