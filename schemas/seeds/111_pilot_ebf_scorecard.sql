-- ============================================================
-- 111_pilot_ebf_scorecard.sql -- Adelphi EBF draft fixture
-- ============================================================

-- This is a governed draft shell, not a scored or public EBF result. The
-- source records establish that Adelphi is a pilot, but do not by themselves
-- provide a calibrated seven-pillar scorecard or public-safe evidence set.
INSERT INTO ebf_scorecard (
    id, location_id, farm_id, period_start, period_end, overall_score,
    overall_confidence, status, rubric_version, calibration_report_required,
    evidence_maturity_level, public_claim_allowed, reviewer_notes, metadata
) VALUES (
    'a0000000-0000-0000-0000-000001110001',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    '2025-10-01',
    '2026-03-31',
    NULL,
    'insufficient_evidence',
    'draft',
    '2026.1',
    TRUE,
    1,
    FALSE,
    'Draft fixture pending governed pillar scoring, evidence linkage, and calibration review.',
    '{"source":"pilot_seed","source_id":"adelphi-ebf-draft-2026-1","fixture":"draft_shell_only","public_claim_allowed":false}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    location_id = EXCLUDED.location_id,
    farm_id = EXCLUDED.farm_id,
    period_start = EXCLUDED.period_start,
    period_end = EXCLUDED.period_end,
    overall_score = EXCLUDED.overall_score,
    overall_confidence = EXCLUDED.overall_confidence,
    status = EXCLUDED.status,
    rubric_version = EXCLUDED.rubric_version,
    calibration_report_required = EXCLUDED.calibration_report_required,
    evidence_maturity_level = EXCLUDED.evidence_maturity_level,
    public_claim_allowed = EXCLUDED.public_claim_allowed,
    reviewer_notes = EXCLUDED.reviewer_notes,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Do not seed ebf_score or ebf_score_evidence rows here. Those records require
-- actual pillar-level evidence and human review before they can be created.
