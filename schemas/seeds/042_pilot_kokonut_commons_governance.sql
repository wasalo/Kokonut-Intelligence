-- ============================================================
-- 042_pilot_kokonut_commons_governance.sql — Adelphi commons governance examples
-- ============================================================

INSERT INTO anti_capture_governance_policy (
    id, location_id, policy_name, governance_body, policy_scope, voting_method,
    voting_cap_pct, quadratic_or_conviction_enabled, one_person_one_vote_enabled,
    sybil_resistance_method, worker_or_operator_veto_enabled, community_veto_enabled,
    delegation_limits, enforcement_mode, policy_summary, public_summary,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001600',
    'a0000000-0000-0000-0000-000000000001',
    'Adelphi anti-capture review policy',
    'Farm operators, Guild reviewers, and DAO treasury stewards',
    'farm',
    'hybrid',
    20.0000,
    FALSE,
    FALSE,
    'Registry-backed farm/operator records plus human steward review; one-person-one-vote and quadratic voting are not yet enforced on-chain.',
    TRUE,
    TRUE,
    'No single funder or token holder can publish farm impact claims without operator/Guild review; delegation rules remain offchain policy.',
    'manual_review',
    'Adelphi anti-capture safeguards document voting-cap guidance, operator and community veto/rework rights, and manual review boundaries while avoiding unsupported claims of on-chain quadratic or one-person-one-vote enforcement.',
    'Adelphi has an offchain anti-capture review policy with voting-cap guidance, operator/community veto rights, and manual review; stronger one-person-one-vote or quadratic enforcement remains future work.',
    3,
    'published',
    '{"claim_boundary":"anti-capture policy evidence, not smart-contract enforcement","unsupported_claims_excluded":["catgirl anarchist mandated representation","quadratic voting enforced onchain"]}'::jsonb,
    'pilot_seed',
    'adelphi-anti-capture-policy-2026',
    '{"record_type":"anti_capture_governance_policy","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    policy_name = EXCLUDED.policy_name,
    voting_cap_pct = EXCLUDED.voting_cap_pct,
    policy_summary = EXCLUDED.policy_summary,
    public_summary = EXCLUDED.public_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO commons_redistribution_policy (
    id, location_id, policy_name, scenario_name, policy_scope, policy_status,
    revenue_basis, commons_allocation_pct, local_cooperative_allocation_pct,
    operator_allocation_pct, digital_commons_allocation_pct, reserve_allocation_pct,
    trigger_conditions, enforcement_mode, audit_cadence, policy_summary,
    public_summary, evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES
(
    'a0000000-0000-0000-0000-000000001610',
    'a0000000-0000-0000-0000-000000000001',
    'Adelphi current public-goods allocation policy',
    'current_2026_transition_plan',
    'farm',
    'active',
    'net_profit',
    10.0000,
    0.0000,
    20.0000,
    0.0000,
    70.0000,
    ARRAY['published financial sustainability plan', 'quarterly Finance Guild review', 'positive NOI scenario'],
    'reporting_policy',
    'quarterly',
    'This policy mirrors Adelphi current published planning evidence: 10% public-goods allocation and 20% reinvestment target, with remaining surplus held for operating continuity and risk reserves.',
    'Adelphi current policy routes 10% of net-profit planning surplus to public goods and targets 20% reinvestment; this is flexible per scenario and not a majority-commons commitment.',
    3,
    'published',
    '{"source_plan_id":"a0000000-0000-0000-0000-000000001000","claim_boundary":"current policy scenario"}'::jsonb,
    'pilot_seed',
    'adelphi-current-redistribution-policy-2026',
    '{"record_type":"commons_redistribution_policy","privacy":"public_summary"}'::jsonb
),
(
    'a0000000-0000-0000-0000-000000001611',
    'a0000000-0000-0000-0000-000000000001',
    'Adelphi surplus-year higher-commons scenario',
    'surplus_year_example',
    'scenario',
    'proposed',
    'surplus',
    35.0000,
    15.0000,
    25.0000,
    10.0000,
    15.0000,
    ARRAY['runway above 12 months', 'risk register residual high risks resolved', 'operator review approves surplus distribution', 'no private capital covenant conflict'],
    'manual_review',
    'scenario_review',
    'This flexible scenario shows how surplus-year allocation could increase commons and local cooperative shares while preserving operator and reserve allocations; it is not active policy.',
    'A proposed surplus-year scenario could route 35% to commons, 15% to local cooperatives, 25% to operators, 10% to digital commons, and 15% to reserves if runway and risk gates pass.',
    3,
    'published',
    '{"claim_boundary":"scenario only, adaptable case by case","unsupported_claims_excluded":["51% committed allocation","AMUSA allocation"]}'::jsonb,
    'pilot_seed',
    'adelphi-flexible-surplus-redistribution-scenario',
    '{"record_type":"commons_redistribution_policy","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    policy_name = EXCLUDED.policy_name,
    scenario_name = EXCLUDED.scenario_name,
    policy_status = EXCLUDED.policy_status,
    commons_allocation_pct = EXCLUDED.commons_allocation_pct,
    local_cooperative_allocation_pct = EXCLUDED.local_cooperative_allocation_pct,
    operator_allocation_pct = EXCLUDED.operator_allocation_pct,
    digital_commons_allocation_pct = EXCLUDED.digital_commons_allocation_pct,
    reserve_allocation_pct = EXCLUDED.reserve_allocation_pct,
    trigger_conditions = EXCLUDED.trigger_conditions,
    public_summary = EXCLUDED.public_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO federation_protocol (
    id, protocol_name, target_region, federation_scope, permissionless_forking_enabled,
    local_adaptation_rights, mutual_aid_commitments, shared_infrastructure,
    onboarding_requirements, anti_extractive_safeguards, conflict_resolution_path,
    protocol_status, public_summary, evidence_maturity, status, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000001620',
    'Kokonut farm federation starter protocol',
    'Dominican Republic pilot cluster',
    'open_source_framework',
    TRUE,
    'Communities may fork schemas, dashboards, and playbooks while adapting governance, language, crop, and stewardship practices locally.',
    ARRAY['operator onboarding templates', 'public-safe dashboard reuse', 'evidence maturity coaching', 'risk-register review before claims'],
    ARRAY['PostgreSQL schemas', 'Metabase SQL dashboards', 'CIDS export mapping', 'report generators'],
    ARRAY['local registry record', 'public-safe community governance mechanism', 'adoption barrier assessment', 'financial sustainability plan'],
    ARRAY['no live-farm claims without registry records', 'no private cultural knowledge publication', 'no token-holder override of operator review', 'local conflict escalation path required'],
    'Escalate disputes through farm operators, relevant Guild, and publication review before public claims expand.',
    'pilot',
    'The federation starter protocol supports permissionless reuse while requiring local adaptation, registry-backed claims, mutual-aid onboarding, and anti-extractive safeguards before expansion claims.',
    3,
    'published',
    '{"claim_boundary":"federation protocol, not unlimited scaling guarantee"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    protocol_name = EXCLUDED.protocol_name,
    permissionless_forking_enabled = EXCLUDED.permissionless_forking_enabled,
    mutual_aid_commitments = EXCLUDED.mutual_aid_commitments,
    anti_extractive_safeguards = EXCLUDED.anti_extractive_safeguards,
    public_summary = EXCLUDED.public_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO algorithmic_redistribution_mechanism (
    id, location_id, mechanism_name, mechanism_type, beneficiary_scope,
    allocation_formula, funding_source, eligibility_criteria, privacy_safeguards,
    implementation_status, enforcement_mode, mechanism_summary, public_summary,
    evidence_maturity, status, metadata, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000001630',
    'a0000000-0000-0000-0000-000000000001',
    'Operator-support matching pool scenario',
    'operator_support',
    'farm_operator',
    'Allocate a reviewed share of public-goods or surplus pool to operator support based on approved participation, training, and stewardship needs; no protected-class targeting is published.',
    'public_goods_allocation',
    ARRAY['published farm registry record', 'operator or steward role confirmed by governed records', 'human approval before payout', 'no public exposure of private identity or household data'],
    ARRAY['aggregate public summaries only', 'private eligibility review stays off public dashboards', 'no protected-class targeting in public records'],
    'proposed',
    'manual_review',
    'This proposed mechanism models redistribution to operators through a reviewed matching pool. It does not implement airdrops, progressive gas fees, or automatic payments in this repository.',
    'A proposed operator-support matching pool could route reviewed public-goods funds to eligible operators while preserving privacy and requiring human approval before any payout.',
    3,
    'published',
    '{"claim_boundary":"proposed mechanism, no onchain payout implementation","unsupported_claims_excluded":["airdrop implemented","progressive gas fees implemented"]}'::jsonb,
    'pilot_seed',
    'adelphi-operator-support-matching-scenario',
    '{"record_type":"algorithmic_redistribution_mechanism","privacy":"public_summary"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    mechanism_name = EXCLUDED.mechanism_name,
    allocation_formula = EXCLUDED.allocation_formula,
    implementation_status = EXCLUDED.implementation_status,
    public_summary = EXCLUDED.public_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

INSERT INTO participatory_signal_experiment (
    id, experiment_name, signal_type, governance_scope, decision_binding,
    experiment_status, participation_rules, moderation_policy, safety_boundaries,
    public_summary, evidence_maturity, status, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000001640',
    'Advisory meme and vibes check for public-good priorities',
    'vibes_check',
    'publication_review',
    'advisory',
    'proposed',
    'Participants may submit public-safe memes, short stories, or ranked sentiment on public-good priorities; results are advisory and require human review before governance action.',
    'Reject harassment, private identity exposure, protected-class targeting, financial promises, or claims that bypass evidence maturity gates.',
    ARRAY['advisory only', 'no private stakeholder data', 'no binding treasury action', 'human moderation required', 'evidence maturity gates still apply'],
    'A proposed advisory vibes check can collect public-safe cultural signals for publication review without replacing formal governance, treasury controls, or evidence requirements.',
    3,
    'published',
    '{"claim_boundary":"advisory participatory signal, not binding governance"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET
    experiment_name = EXCLUDED.experiment_name,
    participation_rules = EXCLUDED.participation_rules,
    safety_boundaries = EXCLUDED.safety_boundaries,
    public_summary = EXCLUDED.public_summary,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();
