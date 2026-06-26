-- ============================================================
-- 029_pilot_impact_accountability.sql — Adelphi social impact layer
-- ============================================================

INSERT INTO stakeholder_feedback (
    id, location_id, farm_id, feedback_type, stakeholder_group, stakeholder_name,
    feedback_date, feedback_text, language, sentiment, themes, suggested_improvements,
    consent_given, consent_scope, consent_notes, is_public, public_summary,
    evidence_maturity, status, source_system, source_id, source_raw
) VALUES
(
    'a0000000-0000-0000-0000-000000000900',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'farmer_feedback',
    'farm_operator',
    'Adelphi Farm Lead',
    '2026-03-05',
    'The biofactory and syntropic beds are useful because they reduce input purchases and make the work easier to explain to visitors. We still need clearer monthly summaries in Spanish.',
    'es',
    'mixed',
    '["bioinputs", "operator_learning", "reporting_accessibility"]'::jsonb,
    '["Publish a simple monthly Spanish-language operator summary"]'::jsonb,
    TRUE,
    'public_summary',
    'Operator approved a summarized public version; raw wording remains private evidence.',
    TRUE,
    'Adelphi operators report that biofactory and syntropic-bed work reduced input dependence and improved learning, while asking for simpler Spanish-language monthly summaries.',
    3,
    'published',
    'pilot_seed',
    'adelphi-feedback-operator-2026-03',
    '{"record_type":"stakeholder_feedback","privacy":"public_summary_private_raw"}'::jsonb
),
(
    'a0000000-0000-0000-0000-000000000901',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'local_resident_feedback',
    'local_resident',
    NULL,
    '2026-03-07',
    'Residents appreciate visible farm activity and local food production. Privacy around household-level observations should remain protected.',
    'es',
    'positive',
    '["local_food", "privacy", "community_trust"]'::jsonb,
    '["Keep household-level survey notes private by default"]'::jsonb,
    FALSE,
    'private_review',
    'No public consent granted; record retained for private review only.',
    FALSE,
    NULL,
    2,
    'verified',
    'pilot_seed',
    'adelphi-feedback-resident-2026-03',
    '{"record_type":"stakeholder_feedback","privacy":"private"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    feedback_text = EXCLUDED.feedback_text,
    sentiment = EXCLUDED.sentiment,
    themes = EXCLUDED.themes,
    suggested_improvements = EXCLUDED.suggested_improvements,
    consent_given = EXCLUDED.consent_given,
    consent_scope = EXCLUDED.consent_scope,
    consent_notes = EXCLUDED.consent_notes,
    is_public = EXCLUDED.is_public,
    public_summary = EXCLUDED.public_summary,
    evidence_maturity = EXCLUDED.evidence_maturity,
    status = EXCLUDED.status,
    source_system = EXCLUDED.source_system,
    source_id = EXCLUDED.source_id,
    source_raw = EXCLUDED.source_raw,
    updated_at = NOW();

INSERT INTO stakeholder_feedback_review (
    id, feedback_id, reviewer_id, action, response_text, escalation_level, due_at, resolved_at, metadata
) VALUES
(
    'a0000000-0000-0000-0000-000000000902',
    'a0000000-0000-0000-0000-000000000900',
    NULL,
    'published_summary',
    'Public summary approved with raw feedback retained privately.',
    'none',
    '2026-03-12 00:00:00+00',
    '2026-03-08 12:00:00+00',
    '{"review_type":"privacy_and_public_summary"}'::jsonb
),
(
    'a0000000-0000-0000-0000-000000000903',
    'a0000000-0000-0000-0000-000000000901',
    NULL,
    'acknowledged',
    'Feedback acknowledged and retained privately because public consent was not granted.',
    'none',
    '2026-03-14 00:00:00+00',
    '2026-03-08 12:00:00+00',
    '{"review_type":"private_feedback"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    action = EXCLUDED.action,
    response_text = EXCLUDED.response_text,
    escalation_level = EXCLUDED.escalation_level,
    due_at = EXCLUDED.due_at,
    resolved_at = EXCLUDED.resolved_at,
    metadata = EXCLUDED.metadata;

INSERT INTO stakeholder_outcome (
    id, location_id, farm_id, outcome_name, outcome_description,
    stakeholder_group, stakeholder_description, importance, importance_perspective,
    is_underserved, framework_key, sdg_number, capital_key, pillar_key,
    evidence_maturity, status, metadata
) VALUES
(
    'a0000000-0000-0000-0000-000000000910',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'Improved farm operator capability',
    'Operators gain practical capacity to manage syntropic beds, bioinputs, and monthly evidence-backed summaries.',
    'farm_operator',
    'Farm workers and operators directly involved in Adelphi implementation.',
    'high',
    'operator feedback and Kokonut advisor review',
    FALSE,
    'sdg',
    8,
    'human',
    'who',
    3,
    'published',
    '{"cids_class":"StakeholderOutcome","source_feedback_id":"a0000000-0000-0000-0000-000000000900"}'::jsonb
),
(
    'a0000000-0000-0000-0000-000000000911',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'Protected community trust and privacy',
    'Local residents benefit when public farm reporting keeps household-level evidence private by default.',
    'local_resident',
    'Residents near Kokonut Adelphi and surrounding community members.',
    'high',
    'private stakeholder feedback and advisor review',
    FALSE,
    'sdg',
    16,
    'social',
    'risk',
    3,
    'published',
    '{"cids_class":"StakeholderOutcome","source_feedback_id":"a0000000-0000-0000-0000-000000000901"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    outcome_name = EXCLUDED.outcome_name,
    outcome_description = EXCLUDED.outcome_description,
    importance = EXCLUDED.importance,
    importance_perspective = EXCLUDED.importance_perspective,
    evidence_maturity = EXCLUDED.evidence_maturity,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO impact_claim (
    id, location_id, farm_id, stakeholder_outcome_id, metric_id,
    claim_type, claim_category, claim_date, period_start, period_end,
    claim_text, claim_value, claim_unit, source_record_ids,
    evidence_cid, evidence_hash, evidence_maturity, attestation_uid,
    public_claim, confidence_level, confidence_notes, methodology_ref,
    external_verifier, review_date, review_notes, status, metadata
) VALUES
(
    'a0000000-0000-0000-0000-000000000920',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000000910',
    NULL,
    'published_record',
    'social',
    '2026-03-10',
    '2025-10-01',
    '2026-03-31',
    'Adelphi operators report improved practical capacity around syntropic beds and bioinput operations, with a need for simpler Spanish monthly summaries.',
    NULL,
    NULL,
    ARRAY['a0000000-0000-0000-0000-000000000900']::uuid[],
    NULL,
    NULL,
    3,
    NULL,
    TRUE,
    'medium',
    'Public social claim is reviewed stakeholder feedback, not externally verified.',
    'Common Foundations stakeholder involvement and sense-making review',
    NULL,
    '2026-03-10',
    'Approved for public summary because consent is public_summary and raw text remains private.',
    'published',
    '{"public_interest":"includes operator voice and limitation"}'::jsonb
),
(
    'a0000000-0000-0000-0000-000000000921',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000010',
    NULL,
    NULL,
    'third_party_verified_claim',
    'carbon',
    '2026-03-10',
    '2025-10-01',
    '2026-03-31',
    'Kokonut Adelphi is modeled as a net-sequestering pilot for the 2025-2026 period based on externally reviewed carbon-balance evidence.',
    56.84,
    'tCO2e',
    ARRAY['a0000000-0000-0000-0000-000000000850']::uuid[],
    'bafybeiadolphicarbonframeworkreview',
    'd6b8172cf6e886c1c5d3374510f0f4c2d8b9e2c09b2a78147a14c3c90debf001',
    6,
    NULL,
    TRUE,
    'medium',
    'External review is represented for public-claim gating; credit issuance remains separate and not claimed here.',
    'IPCC 2006 GHG Guidelines; Kokonut Carbon Framework v1; allometric coconut tree carbon model',
    'External MRV reviewer (pilot evidence review)',
    '2026-03-10',
    'Approved only as a public carbon-balance evidence claim, not a carbon credit issuance claim.',
    'published',
    '{"claim_scope":"carbon_balance_not_credit_issuance","requires_external_review_before_production":true}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    claim_type = EXCLUDED.claim_type,
    claim_category = EXCLUDED.claim_category,
    claim_text = EXCLUDED.claim_text,
    claim_value = EXCLUDED.claim_value,
    claim_unit = EXCLUDED.claim_unit,
    source_record_ids = EXCLUDED.source_record_ids,
    evidence_cid = EXCLUDED.evidence_cid,
    evidence_hash = EXCLUDED.evidence_hash,
    evidence_maturity = EXCLUDED.evidence_maturity,
    public_claim = EXCLUDED.public_claim,
    confidence_level = EXCLUDED.confidence_level,
    confidence_notes = EXCLUDED.confidence_notes,
    methodology_ref = EXCLUDED.methodology_ref,
    external_verifier = EXCLUDED.external_verifier,
    review_date = EXCLUDED.review_date,
    review_notes = EXCLUDED.review_notes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO metric_proposal (
    id, location_id, proposed_by, proposed_by_role, proposal_date,
    metric_name, metric_description, unit_of_measure, category, rationale,
    data_source, collection_method, frequency, stakeholder_groups,
    discussion_notes, status, implementation_date, metric_definition_id, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000000930',
    'a0000000-0000-0000-0000-000000000001',
    'Adelphi Farm Lead',
    'farm_operator',
    '2026-03-05',
    'Spanish monthly operator summary delivered',
    'Tracks whether a simple Spanish-language monthly summary was delivered to farm operators after each reporting cycle.',
    'count',
    'social',
    'Operator feedback requested simpler Spanish summaries to make impact data useful at the farm level.',
    'report_snapshot, stakeholder_feedback',
    'Advisor confirms summary delivery and operator acknowledgement.',
    'monthly',
    ARRAY['farm_operator'],
    '[{"date":"2026-03-08","note":"Metric accepted as a low-overhead operator-usefulness check."}]'::jsonb,
    'approved',
    NULL,
    NULL,
    '{"source_feedback_id":"a0000000-0000-0000-0000-000000000900"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    metric_description = EXCLUDED.metric_description,
    rationale = EXCLUDED.rationale,
    discussion_notes = EXCLUDED.discussion_notes,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

UPDATE mrv_claim
SET evidence_maturity = 6,
    public_claim = TRUE,
    external_verifier = 'External MRV reviewer (pilot evidence review)',
    methodology_ref = 'IPCC 2006 GHG Guidelines; Kokonut Carbon Framework v1'
WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
  AND claim_type IN ('carbon', 'carbon_credit', 'carbon_balance', 'climate_impact', 'soil_carbon', 'tree_carbon')
  AND status IN ('verified', 'published');
