-- Canonical stakeholder foundation vocabulary and pilot proxy parties.

INSERT INTO party (id, party_type, display_name, description, privacy_level, metadata)
VALUES
    ('a0000000-0000-0000-0000-000000001000', 'organization', 'Kokonut Network', 'Platform and ecosystem steward.', 'public', '{"source":"canonical_platform"}'::jsonb),
    ('a0000000-0000-0000-0000-000000001001', 'organization', 'Kokonut Adelphi', 'Canonical pilot farm and regenerative demonstration site.', 'limited', '{"source":"canonical_pilot"}'::jsonb),
    ('a0000000-0000-0000-0000-000000001002', 'community', 'Adelphi community', 'Community stakeholders connected to the canonical pilot.', 'limited', '{"source":"canonical_pilot"}'::jsonb),
    ('a0000000-0000-0000-0000-000000001003', 'ecosystem', 'Adelphi living systems', 'Ecological systems represented through stewardship evidence and proxies.', 'public', '{"proxy":true,"source":"canonical_pilot"}'::jsonb),
    ('a0000000-0000-0000-0000-000000001004', 'future_generation', 'Future generations', 'Proxy interest-bearer for long-term ecological and social consequences.', 'public', '{"proxy":true,"source":"stakeholder_theory"}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    party_type = EXCLUDED.party_type,
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    privacy_level = EXCLUDED.privacy_level,
    metadata = EXCLUDED.metadata;

INSERT INTO party_identifier
    (id, party_id, identifier_type, identifier_value, source_system, source_id, verification_status, confidence, evidence)
VALUES
    ('a0000000-0000-0000-0000-000000001010', 'a0000000-0000-0000-0000-000000001000', 'platform_key', 'kokonut-network', 'kokonut', 'kokonut-network', 'verified', 1.0, '[{"source":"canonical_platform"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000001011', 'a0000000-0000-0000-0000-000000001001', 'location_id', 'a0000000-0000-0000-0000-000000000001', 'kokonut', 'adelphi-location', 'verified', 1.0, '[{"source":"canonical_pilot"}]'::jsonb)
ON CONFLICT (identifier_type, identifier_value, source_system) DO UPDATE SET
    party_id = EXCLUDED.party_id,
    verification_status = EXCLUDED.verification_status,
    confidence = EXCLUDED.confidence,
    evidence = EXCLUDED.evidence;

INSERT INTO party_relationship
    (id, from_party_id, to_party_id, relationship_type, scope_type, scope_id, legitimacy, status, confidence, evidence, notes)
VALUES
    ('a0000000-0000-0000-0000-000000001020', 'a0000000-0000-0000-0000-000000001000', 'a0000000-0000-0000-0000-000000001001', 'stewards', 'network', NULL, 'derivative', 'active', 1.0, '[{"source":"canonical_platform"}]'::jsonb, 'Kokonut Network stewards the shared platform supporting the pilot.'),
    ('a0000000-0000-0000-0000-000000001021', 'a0000000-0000-0000-0000-000000001002', 'a0000000-0000-0000-0000-000000001001', 'affected_by', 'network', NULL, 'normative', 'active', 0.8, '[{"source":"stakeholder_mapping"}]'::jsonb, 'Community interests are represented without treating the community as a single voice.'),
    ('a0000000-0000-0000-0000-000000001022', 'a0000000-0000-0000-0000-000000001003', 'a0000000-0000-0000-0000-000000001001', 'depends_on', 'network', NULL, 'proxy', 'active', 0.9, '[{"source":"ecological_modeling"}]'::jsonb, 'Living systems are represented through ecological evidence and stewardship proxies.'),
    ('a0000000-0000-0000-0000-000000001023', 'a0000000-0000-0000-0000-000000001004', 'a0000000-0000-0000-0000-000000001001', 'holds_interest_in', 'network', NULL, 'proxy', 'active', 0.9, '[{"source":"stakeholder_theory"}]'::jsonb, 'Long-term effects are reviewed through governed ecological and social targets.')
ON CONFLICT (id) DO UPDATE SET
    relationship_type = EXCLUDED.relationship_type,
    legitimacy = EXCLUDED.legitimacy,
    status = EXCLUDED.status,
    confidence = EXCLUDED.confidence,
    evidence = EXCLUDED.evidence,
    notes = EXCLUDED.notes;

INSERT INTO stakeholder_consent (
    id, party_id, event_type, data_category, purpose, scope_type, scope_id,
    recipient_type, consent_method, legal_basis, consent_version, effective_at,
    evidence, source_system, source_record_id, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000001090',
    'a0000000-0000-0000-0000-000000001001',
    'grant', 'stakeholder_feedback', 'public_summary', 'location',
    'a0000000-0000-0000-0000-000000000001', 'system', 'system_migration',
    'consent', '1.0', '2026-03-01 00:00:00+00',
    '[{"source":"canonical_pilot","basis":"operator-approved public summary"}]'::jsonb,
    'pilot_seed', 'adelphi-feedback-public-summary-consent-2026-03',
    '{"scope":"public_summary","raw_feedback":"private"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    party_id = EXCLUDED.party_id,
    event_type = EXCLUDED.event_type,
    data_category = EXCLUDED.data_category,
    purpose = EXCLUDED.purpose,
    scope_type = EXCLUDED.scope_type,
    scope_id = EXCLUDED.scope_id,
    recipient_type = EXCLUDED.recipient_type,
    consent_method = EXCLUDED.consent_method,
    legal_basis = EXCLUDED.legal_basis,
    consent_version = EXCLUDED.consent_version,
    effective_at = EXCLUDED.effective_at,
    evidence = EXCLUDED.evidence,
    source_system = EXCLUDED.source_system,
    source_record_id = EXCLUDED.source_record_id,
    metadata = EXCLUDED.metadata;

INSERT INTO stakeholder_interest
    (id, party_id, interest_type, title, description, legitimacy, priority, scope_type, scope_id, status, evidence)
VALUES
    ('a0000000-0000-0000-0000-000000001030', 'a0000000-0000-0000-0000-000000001002', 'need', 'Participate in decisions affecting the pilot', 'Community stakeholders need accessible, safe channels to influence decisions that affect local livelihoods and wellbeing.', 'normative', 5, 'location', 'a0000000-0000-0000-0000-000000000001', 'validated', '[{"source":"stakeholder_mapping"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000001031', 'a0000000-0000-0000-0000-000000001003', 'stewardship', 'Maintain ecological integrity', 'Living systems require monitoring and decisions that protect soil, water, biodiversity, and regenerative capacity.', 'proxy', 5, 'location', 'a0000000-0000-0000-0000-000000000001', 'validated', '[{"source":"ecological_modeling"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000001032', 'a0000000-0000-0000-0000-000000001004', 'obligation', 'Protect long-term options', 'Future generations require decisions that preserve ecological, social, and economic options beyond the current planning horizon.', 'proxy', 5, 'network', NULL, 'validated', '[{"source":"stakeholder_theory"}]'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    legitimacy = EXCLUDED.legitimacy,
    priority = EXCLUDED.priority,
    status = EXCLUDED.status,
    evidence = EXCLUDED.evidence;

INSERT INTO stakeholder_salience_assessment
    (id, party_id, interest_id, power_score, legitimacy_score, urgency_score, vulnerability_score, harm_exposure_score, representation_score, rationale, review_status, evidence)
VALUES
    ('a0000000-0000-0000-0000-000000001040', 'a0000000-0000-0000-0000-000000001002', 'a0000000-0000-0000-0000-000000001030', 5, 9, 7, 7, 8, 4, 'Advisory assessment prioritizes legitimate community interests while recognizing representation is incomplete.', 'advisory', '[{"source":"stakeholder_mapping"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000001041', 'a0000000-0000-0000-0000-000000001003', 'a0000000-0000-0000-0000-000000001031', 2, 10, 8, 8, 10, 3, 'Ecological interests have high legitimacy and harm exposure even without conventional organizational power.', 'advisory', '[{"source":"ecological_modeling"}]'::jsonb),
    ('a0000000-0000-0000-0000-000000001042', 'a0000000-0000-0000-0000-000000001004', 'a0000000-0000-0000-0000-000000001032', 1, 10, 6, 9, 9, 2, 'Future-generation interests are proxy-assessed and require explicit long-term review.', 'advisory', '[{"source":"stakeholder_theory"}]'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    power_score = EXCLUDED.power_score,
    legitimacy_score = EXCLUDED.legitimacy_score,
    urgency_score = EXCLUDED.urgency_score,
    vulnerability_score = EXCLUDED.vulnerability_score,
    harm_exposure_score = EXCLUDED.harm_exposure_score,
    representation_score = EXCLUDED.representation_score,
    rationale = EXCLUDED.rationale,
    review_status = EXCLUDED.review_status,
    evidence = EXCLUDED.evidence;
