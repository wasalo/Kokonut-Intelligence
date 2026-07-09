-- ============================================================
-- 076_crisp_risk_scoring.sql — Seed data for CRISP risk dimensions
-- ============================================================

-- CRISP risk dimension definitions
INSERT INTO crisp_risk_dimension (dimension_key, dimension_name, description, default_weight, data_sources, scoring_methodology, status) VALUES
('carbon_yield', 'Carbon Yield Risk', 'Likelihood of meeting carbon/biomass yield targets based on scenario modeling across tree inventory, soil carbon, harvest data, and remote sensing.', 0.40, ARRAY['tree_inventory', 'soil_carbon_measurement', 'harvest_event', 'remote_sensing_observation', 'carbon_benchmark'], 'Three-scenario modeling (minimum/realistic/optimistic) with NDVI-based vegetation density adjustment and mortality likelihood. Adapted from SW-CRISP Annexure 1.', 'active'),
('climate', 'Climate Catastrophe Risk', 'Probability of drought, flood, extreme heat, fire, storm, and water stress disrupting farm operations and carbon sequestration.', 0.25, ARRAY['weather_observation', 'emergency_incident', 'risk_mitigation_register', 'remote_sensing_observation'], 'Per-hazard scoring (0-3 each, max 15) based on historical weather patterns, emergency incident frequency/severity, and mitigation factor from active climate risk measures. Adapted from SW-CRISP Annexure 2.', 'active'),
('policy', 'Policy & Legal Risk', 'Risks from certification gaps, regulatory barriers, unclear carbon rights, weak land tenure, and poor community alignment.', 0.15, ARRAY['organic_certification_record', 'adoption_barrier_assessment', 'land_stewardship_commitment', 'governance_inclusion_observation', 'stakeholder_feedback'], 'Sub-factor scoring (0-1 each) for national policy strength, carbon rights clarity, land tenure security, community alignment, and certification risk. Adapted from SW-CRISP Annexure 3.', 'active'),
('financial', 'Financial Viability Risk', 'Ability to sustain operations through the carbon farming cycle, including revenue diversity, cost structure, liquidity, and market price exposure.', 0.10, ARRAY['financial_sustainability_plan', 'farm_launch_unit_economics', 'revenue_event', 'expense_event'], 'Composite risk factor from revenue risk (grant dependency, volatility, stream diversity), cost risk (payback, cost concentration), liquidity risk (runway), and market price risk. Adapted from SW-CRISP Section 4.', 'active'),
('implementation', 'Implementation Risk', 'Farm operator capability including track record, team strength, network, community alignment, and transparency.', 0.10, ARRAY['farm_onboarding_profile', 'regenerative_practice_checklist', 'governance_inclusion_observation', 'stakeholder_feedback', 'training_event'], 'Sub-factor scoring (0-1 each) for track record, team strength, network strength, community alignment, and transparency. Adapted from SW-CRISP Annexure 4.', 'active')
ON CONFLICT (dimension_key) DO UPDATE SET
    dimension_name = EXCLUDED.dimension_name,
    description = EXCLUDED.description,
    default_weight = EXCLUDED.default_weight,
    data_sources = EXCLUDED.data_sources,
    scoring_methodology = EXCLUDED.scoring_methodology,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Adelphi pilot: all 5 CRISP dimensions mapped
INSERT INTO farm_impact_mapping (location_id, framework_key, dimension_key, sdg_number, capital_key, pillar_key, claim, evidence_path, evidence_maturity, reporting_period, status, metadata) VALUES
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_operational', NULL, NULL, NULL,
 'Operational risk is managed through farm onboarding, training events, regenerative practice checklists, and stakeholder feedback loops.',
 'farm_onboarding_profile + training_event + regenerative_practice_checklist', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_climate', NULL, NULL, NULL,
 'Climate risk is assessed through weather observation patterns, emergency incident tracking, and active mitigation measures in the risk register.',
 'weather_observation + emergency_incident + risk_mitigation_register', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_market', NULL, NULL, NULL,
 'Market risk is tracked through revenue diversity, buyer demand signals, price volatility monitoring, and financial sustainability planning.',
 'revenue_event + buyer_demand_signal + financial_sustainability_plan', 'measured', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_policy', NULL, NULL, NULL,
 'Policy risk is managed through organic certification tracking, adoption barrier assessment, and land tenure stewardship commitments.',
 'organic_certification_record + adoption_barrier_assessment + land_stewardship_commitment', 'verified', '2025-2026', 'published', '{}'::jsonb),
('a0000000-0000-0000-0000-000000000001', 'crisp', 'crisp_evidence', NULL, NULL, NULL,
 'Evidence quality risk is reduced by source lineage, payload hashes, CIDs, and Celo attestation metadata.',
 'mrv_event + attestation_request', 'verified', '2025-2026', 'published', '{}'::jsonb)
ON CONFLICT (location_id, framework_key, dimension_key) DO UPDATE SET
    claim = EXCLUDED.claim,
    evidence_path = EXCLUDED.evidence_path,
    evidence_maturity = EXCLUDED.evidence_maturity,
    status = EXCLUDED.status,
    updated_at = NOW();
