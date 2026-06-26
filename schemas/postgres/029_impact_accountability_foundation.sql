-- ============================================================
-- 029_impact_accountability_foundation.sql — CIDS/Common Foundations layer
-- ============================================================

-- Evidence maturity applies across claims, feedback, and reports.
-- Level 6 is reserved for externally verified public claims.
CREATE TABLE IF NOT EXISTS evidence_maturity_level (
    level INTEGER PRIMARY KEY CHECK (level BETWEEN 0 AND 6),
    level_key VARCHAR(50) NOT NULL UNIQUE,
    label VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    public_claim_allowed BOOLEAN DEFAULT FALSE,
    requires_external_verification BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO evidence_maturity_level (level, level_key, label, description, public_claim_allowed, requires_external_verification)
VALUES
    (0, 'narrative_only', 'Narrative only', 'Unstructured narrative without source record or structured evidence.', FALSE, FALSE),
    (1, 'self_reported', 'Self-reported record', 'Self-reported observation or feedback captured with minimal structure.', FALSE, FALSE),
    (2, 'structured_record', 'Structured record', 'Structured data record with required fields and source lineage.', FALSE, FALSE),
    (3, 'reviewed_record', 'Reviewed record', 'Record reviewed by an authorized human reviewer.', FALSE, FALSE),
    (4, 'evidence_linked', 'Evidence-linked record', 'Reviewed record linked to evidence hashes, URLs, or CIDs.', TRUE, FALSE),
    (5, 'attested_record', 'Attested record', 'Evidence-linked record with an onchain or offchain attestation.', TRUE, FALSE),
    (6, 'externally_verified', 'Externally verified record', 'Claim verified by an external verifier or third party with methodology reference.', TRUE, TRUE)
ON CONFLICT (level) DO UPDATE SET
    level_key = EXCLUDED.level_key,
    label = EXCLUDED.label,
    description = EXCLUDED.description,
    public_claim_allowed = EXCLUDED.public_claim_allowed,
    requires_external_verification = EXCLUDED.requires_external_verification;

ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS evidence_maturity INTEGER DEFAULT 1 REFERENCES evidence_maturity_level(level);
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS external_verifier TEXT;
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS methodology_ref TEXT;
ALTER TABLE mrv_claim ADD COLUMN IF NOT EXISTS public_claim BOOLEAN DEFAULT FALSE;

ALTER TABLE farm_impact_mapping ADD COLUMN IF NOT EXISTS evidence_maturity_level INTEGER REFERENCES evidence_maturity_level(level);

ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS public_interest_summary TEXT;
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS uncertainty_notes TEXT;
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS negative_findings JSONB DEFAULT '[]';
ALTER TABLE report_snapshot ADD COLUMN IF NOT EXISTS affected_community_voice TEXT;

ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS for_stakeholder_group VARCHAR(100);
ALTER TABLE metric_definition ADD COLUMN IF NOT EXISTS participatory BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_mrv_claim_evidence_maturity ON mrv_claim(evidence_maturity);
CREATE INDEX IF NOT EXISTS idx_mrv_claim_public_claim ON mrv_claim(public_claim);

-- Public carbon claims require Level 6 external verification. EAS attestation
-- alone is Level 5 and is not enough for public carbon claims.
ALTER TABLE mrv_claim DROP CONSTRAINT IF EXISTS chk_mrv_public_carbon_level6;
ALTER TABLE mrv_claim ADD CONSTRAINT chk_mrv_public_carbon_level6 CHECK (
    NOT (
        public_claim = TRUE
        AND claim_type IN ('carbon', 'carbon_credit', 'carbon_balance', 'climate_impact', 'soil_carbon', 'tree_carbon')
    )
    OR (
        evidence_maturity = 6
        AND NULLIF(TRIM(COALESCE(external_verifier, '')), '') IS NOT NULL
        AND NULLIF(TRIM(COALESCE(methodology_ref, '')), '') IS NOT NULL
    )
);

-- Database-level agent safety for existing agent-generated narratives and tasks.
-- Agents can draft or submit, but cannot verify/publish their own outputs.
ALTER TABLE ai_summary DROP CONSTRAINT IF EXISTS chk_ai_summary_agent_draft_only;
ALTER TABLE ai_summary ADD CONSTRAINT chk_ai_summary_agent_draft_only CHECK (
    created_by IS NULL OR status IN ('draft', 'submitted', 'rejected')
);

ALTER TABLE agent_task DROP CONSTRAINT IF EXISTS chk_agent_task_draft_submit_only;
UPDATE agent_task
SET review_status = 'submitted'
WHERE review_status IN ('verified', 'published');
ALTER TABLE agent_task ADD CONSTRAINT chk_agent_task_draft_submit_only CHECK (
    review_status IN ('draft', 'submitted', 'rejected')
);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('impact-accountability-foundation-v1', 'Evidence maturity, public carbon claim safety, and DB-level agent safety', 'schema 029')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
