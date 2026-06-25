-- ============================================================
-- Pilot Farm Seed Data: DAO & Governance
-- Kokonut Adelphi — Gnosis/Moloch DAO governance
-- ============================================================

-- Governance Events
INSERT INTO governance_event (id, wallet_id, protocol_id, chain, event_type, proposal_id, proposal_title, vote_choice, amount, token, tx_hash, block_number, block_timestamp, metadata) VALUES
('a0000000-0000-0000-0000-000000000200', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_created', 'P001', 'Fund Adelphi syntropic bed buildout', NULL, 500.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000001', 38000001, '2025-10-15 09:00:00+00', '{"proposer": "Adelphi Farm Lead", "venue": "daohaus", "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000201', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'vote_cast', 'P001', 'Fund Adelphi syntropic bed buildout', 'for', 3.0, 'vKKN', '0xdddd000000000000000000000000000000000000000000000000000000000002', 38000002, '2025-10-18 10:00:00+00', '{"voter": "treasury", "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000202', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_executed', 'P001', 'Fund Adelphi syntropic bed buildout', NULL, 500.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000003', 38000003, '2025-10-20 14:00:00+00', '{"result": "approved", "votes_for": 3, "votes_against": 0, "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000203', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_created', 'P002', 'Allocate funds for biofactory and nursery maintenance', NULL, 1000.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000004', 38000004, '2025-11-01 09:00:00+00', '{"proposer": "Community Operations Lead", "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000204', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'vote_cast', 'P002', 'Allocate funds for biofactory and nursery maintenance', 'for', 3.0, 'vKKN', '0xdddd000000000000000000000000000000000000000000000000000000000005', 38000005, '2025-11-04 10:00:00+00', '{"voter": "treasury", "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000205', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_executed', 'P002', 'Allocate funds for biofactory and nursery maintenance', NULL, 1000.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000006', 38000006, '2025-11-06 14:00:00+00', '{"result": "approved", "votes_for": 2, "votes_against": 0, "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000206', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_created', 'P003', 'Fund community field worker stipends', NULL, 2400.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000007', 38000007, '2025-12-01 09:00:00+00', '{"proposer": "Nursery Steward", "duration_months": 3, "governance_layer": "moloch_v2"}'),
('a0000000-0000-0000-0000-000000000207', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'gnosis', 'proposal_executed', 'P003', 'Fund community field worker stipends', NULL, 2400.0, 'USDC', '0xdddd000000000000000000000000000000000000000000000000000000000008', 38000008, '2025-12-10 14:00:00+00', '{"result": "approved", "votes_for": 4, "votes_against": 0, "governance_layer": "moloch_v2"}')
ON CONFLICT (id) DO UPDATE SET
    wallet_id = EXCLUDED.wallet_id,
    protocol_id = EXCLUDED.protocol_id,
    chain = EXCLUDED.chain,
    event_type = EXCLUDED.event_type,
    proposal_id = EXCLUDED.proposal_id,
    proposal_title = EXCLUDED.proposal_title,
    vote_choice = EXCLUDED.vote_choice,
    amount = EXCLUDED.amount,
    token = EXCLUDED.token,
    tx_hash = EXCLUDED.tx_hash,
    block_number = EXCLUDED.block_number,
    block_timestamp = EXCLUDED.block_timestamp,
    metadata = EXCLUDED.metadata;

-- Metric Definitions (16 governed metrics from PRD Section 12)
INSERT INTO metric_definition (id, metric_key, display_name, description, formula, source_tables, inclusion_rules, exclusion_rules, unit, data_type, owner, version, update_frequency, active) VALUES
('a0000000-0000-0000-0000-000000000210', 'crop_revenue', 'Crop Revenue', 'Gross crop sales recognized for a crop and period', 'SUM(sales_event.total_amount) WHERE status=''published''', ARRAY['sales_event', 'crop_cycle'], 'All published crop sales by crop and period', 'Returns, discounts, and rejected sales excluded', 'USD', 'currency', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000211', 'net_crop_revenue', 'Net Crop Revenue', 'Crop revenue minus returns, discounts, and rejected sales', 'crop_revenue - returns - discounts', ARRAY['sales_event', 'crop_cycle'], 'All published crop sales minus adjustments', 'Rejected sales fully excluded', 'USD', 'currency', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000212', 'direct_crop_cost', 'Direct Crop Cost', 'Costs directly attributable to a crop/cycle', 'SUM(expense_event.amount) WHERE is_direct=true', ARRAY['expense_event', 'crop_cycle'], 'Expenses with direct allocation to crop', 'Shared/allocated costs excluded', 'USD', 'currency', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000213', 'allocated_shared_cost', 'Allocated Shared Cost', 'Shared costs allocated using governed allocation rules', 'SUM(crop_cost_allocation.allocated_amount)', ARRAY['crop_cost_allocation'], 'All allocated shared costs', 'Unallocated shared costs excluded', 'USD', 'currency', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000214', 'crop_noi', 'Crop NOI', 'Net crop revenue minus direct crop costs minus allocated shared operating costs', 'net_crop_revenue - direct_crop_cost - allocated_shared_cost', ARRAY['noi_snapshot', 'crop_cycle'], 'All crop cycles with verified financial data', 'Incomplete cycles excluded until data is published', 'USD', 'currency', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000215', 'loss_rate_pct', 'Loss Rate %', '1 - saleable output / harvested output', '1 - (net_harvest / gross_harvest) * 100', ARRAY['harvest_event'], 'All harvest events with recorded losses', 'Pre-harvest field losses excluded', '%', 'percentage', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000216', 'operating_margin_pct', 'Operating Margin %', 'Operating income / net sales', '(crop_noi / net_crop_revenue) * 100', ARRAY['noi_snapshot'], 'All crop cycles with positive net revenue', 'Zero-revenue cycles excluded', '%', 'percentage', 'platform', 1, 'daily', TRUE),
('a0000000-0000-0000-0000-000000000217', 'baseline_revenue', 'Baseline Revenue', 'Revenue before Kokonut intervention or onboarding', 'location.baseline_revenue', ARRAY['location'], 'All active locations with baseline data', 'Locations without baseline excluded', 'USD', 'currency', 'platform', 1, 'once', TRUE),
('a0000000-0000-0000-0000-000000000218', 'baseline_asset_value', 'Baseline Asset Value', 'Estimated starting asset or productive value', 'location.baseline_asset_value', ARRAY['location'], 'All active locations with baseline data', 'Locations without baseline excluded', 'USD', 'currency', 'platform', 1, 'once', TRUE),
('a0000000-0000-0000-0000-000000000219', 'baseline_cash_flow', 'Baseline Cash Flow', 'Pre-intervention net cash flow', 'location.baseline_cash_flow', ARRAY['location'], 'All active locations with baseline data', 'Locations without baseline excluded', 'USD', 'currency', 'platform', 1, 'once', TRUE),
('a0000000-0000-0000-0000-000000000220', 'baseline_cost', 'Baseline Cost', 'Pre-intervention operating costs', 'location.baseline_cost', ARRAY['location'], 'All active locations with baseline data', 'Locations without baseline excluded', 'USD', 'currency', 'platform', 1, 'once', TRUE),
('a0000000-0000-0000-0000-00000000021a', 'value_flowed', 'Value Flowed', 'Verified value attributable to Kokonut activity, excluding failed rounds, returned funds, and excluded fees', 'SUM(verified, non-excluded flows)', ARRAY['value_flow_event'], 'All verified and non-excluded value flow events', 'Failed rounds, returned funds, excluded protocol fees, and unverified flows excluded', 'USD', 'currency', 'platform', 1, 'weekly', TRUE),
('a0000000-0000-0000-0000-00000000021b', 'wallet_retention', 'Wallet Retention', 'Wallet active in current period and at least one prior defined period', 'Active wallets in current AND prior period / total wallets', ARRAY['wallet_activity_event'], 'All wallets active in the measurement period', 'Dormant and one-time wallets excluded', '%', 'percentage', 'platform', 1, 'monthly', TRUE),
('a0000000-0000-0000-0000-00000000021c', 'digital_lego_usage', 'Digital Lego Usage', 'Verified interaction with tracked Web3 components', 'COUNT(DISTINCT verified protocols)', ARRAY['digital_lego_usage'], 'All verified digital lego interactions', 'Unverified and excluded interactions excluded', 'count', 'count', 'platform', 1, 'weekly', TRUE),
('a0000000-0000-0000-0000-00000000021d', 'soil_carbon_delta', 'Soil Carbon Delta', 'Soil carbon after intervention minus baseline', 'after_carbon - baseline_carbon', ARRAY['soil_carbon_measurement'], 'All plots with baseline and follow-up measurements', 'Plots with only baseline or only follow-up excluded', 'tonnes/ha', 'numeric', 'platform', 1, 'quarterly', TRUE),
('a0000000-0000-0000-0000-00000000021e', 'biodiversity_delta', 'Biodiversity Delta', 'Species count after intervention minus baseline', 'after_count - baseline_count', ARRAY['species_observation'], 'All locations with baseline and follow-up observations', 'Locations with only baseline or only follow-up excluded', 'count', 'count', 'platform', 1, 'quarterly', TRUE),
('a0000000-0000-0000-0000-00000000021f', 'attestation_coverage', 'Attestation Coverage', 'Published attestations / eligible publishable claims', '(published / eligible) * 100', ARRAY['attestation_record'], 'All eligible publishable claims', 'Draft and rejected claims excluded', '%', 'percentage', 'platform', 1, 'monthly', TRUE)
ON CONFLICT (metric_key) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    formula = EXCLUDED.formula,
    source_tables = EXCLUDED.source_tables,
    inclusion_rules = EXCLUDED.inclusion_rules,
    exclusion_rules = EXCLUDED.exclusion_rules,
    unit = EXCLUDED.unit,
    data_type = EXCLUDED.data_type,
    owner = EXCLUDED.owner,
    version = EXCLUDED.version,
    update_frequency = EXCLUDED.update_frequency,
    active = EXCLUDED.active,
    updated_at = NOW();

-- Treasury Events (columns: id, location_id, wallet_id, chain, event_date, flow_direction, amount, token, token_amount, usd_value, source, purpose, tx_hash, verified, notes)
INSERT INTO treasury_event (id, location_id, wallet_id, chain, event_date, flow_direction, amount, token, token_amount, usd_value, source, purpose, tx_hash, verified, notes) VALUES
('a0000000-0000-0000-0000-000000000220', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-10-01', 'in', 5000.0, 'USDC', 5000.0, 5000.0, 'Public Nouns', 'Initial Adelphi treasury deposit', '0xcccc111111111111111111111111111111111111111111111111111111111111', TRUE, 'DAO deposit'),
('a0000000-0000-0000-0000-000000000221', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-10-05', 'out', 500.0, 'USDC', 500.0, 500.0, 'Adelphi Bioinputs Network', 'Seedling and input purchase for planting season', '0xcccc222222222222222222222222222222222222222222222222222222222222', TRUE, 'Seed and nursery purchase'),
('a0000000-0000-0000-0000-000000000222', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-10-15', 'out', 200.0, 'USDC', 200.0, 200.0, 'Adelphi Bioinputs Network', 'Bioinput and soil amendment purchase', '0xcccc333333333333333333333333333333333333333333333333333333333333', TRUE, 'Bioinputs'),
('a0000000-0000-0000-0000-000000000223', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-12-20', 'in', 3496.0, 'USDC', 3496.0, 3496.0, 'Dominican Produce Buyers Cooperative', 'Lettuce harvest sales - Cycle 1', '0xcccc444444444444444444444444444444444444444444444444444444444444', TRUE, 'Lettuce sales'),
('a0000000-0000-0000-0000-000000000224', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-12-22', 'out', 300.0, 'USDC', 300.0, 300.0, 'Labor', 'Harvest labor costs', '0xcccc555555555555555555555555555555555555555555555555555555555555', TRUE, 'Labor costs'),
('a0000000-0000-0000-0000-000000000225', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-11-06', 'out', 1000.0, 'USDC', 1000.0, 1000.0, 'Adelphi Bioinputs Network', 'Biofactory and nursery maintenance', '0xcccc666666666666666666666666666666666666666666666666666666666666', TRUE, 'Maintenance'),
('a0000000-0000-0000-0000-000000000226', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-03-20', 'in', 3168.0, 'USDC', 3168.0, 3168.0, 'Dominican Produce Buyers Cooperative', 'Lettuce harvest sales - Cycle 2', '0xcccc777777777777777777777777777777777777777777777777777777777777', TRUE, 'Lettuce sales'),
('a0000000-0000-0000-0000-000000000227', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-03-15', 'in', 2138.0, 'USDC', 2138.0, 2138.0, 'Dominican Produce Buyers Cooperative', 'Passion fruit sales', '0xcccc888888888888888888888888888888888888888888888888888888888888', TRUE, 'Passion fruit sales'),
('a0000000-0000-0000-0000-000000000228', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-11-20', 'in', 2210.0, 'USDC', 2210.0, 2210.0, 'Dominican Produce Buyers Cooperative', 'Coconut nursery sales - Cycle 1', '0xcccc999999999999999999999999999999999999999999999999999999999999', TRUE, 'Coconut sales'),
('a0000000-0000-0000-0000-000000000229', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-01-10', 'out', 250.0, 'USDC', 250.0, 250.0, 'Adelphi Bioinputs Network', 'Lettuce seed and seedling purchase for Cycle 2', '0xcccaaaaa11111111111111111111111111111111111111111111111111111111', TRUE, 'Lettuce seeds'),
('a0000000-0000-0000-0000-00000000022a', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-02-28', 'in', 940.0, 'USDC', 940.0, 940.0, 'Dominican Produce Buyers Cooperative', 'Indian yam harvest sales', '0xcccaaaaa22222222222222222222222222222222222222222222222222222222', TRUE, 'Indian yam sales'),
('a0000000-0000-0000-0000-00000000022b', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-02-28', 'in', 1980.0, 'USDC', 1980.0, 1980.0, 'Dominican Produce Buyers Cooperative', 'Egg production sales', '0xcccaaaaa33333333333333333333333333333333333333333333333333333333', TRUE, 'Egg sales'),
('a0000000-0000-0000-0000-00000000022c', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-11-01', 'out', 150.0, 'USDC', 150.0, 150.0, 'Adelphi Bioinputs Network', 'Indian yam seed material', '0xcccaaaaa44444444444444444444444444444444444444444444444444444444', TRUE, 'Yam seed material'),
('a0000000-0000-0000-0000-00000000022d', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-10-05', 'out', 400.0, 'USDC', 400.0, 400.0, 'Adelphi Bioinputs Network', 'Compost, biochar, and soil amendments', '0xcccaaaaa55555555555555555555555555555555555555555555555555555555', TRUE, 'Bioinputs'),
('a0000000-0000-0000-0000-00000000022e', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2025-12-01', 'out', 100.0, 'USDC', 100.0, 100.0, 'Adelphi Bioinputs Network', 'Organic pest control supplies', '0xcccaaaaa66666666666666666666666666666666666666666666666666666666', TRUE, 'Pest control'),
('a0000000-0000-0000-0000-00000000022f', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-01-05', 'out', 200.0, 'USDC', 200.0, 200.0, 'Adelphi Bioinputs Network', 'Biofactory equipment maintenance', '0xcccaaaaa77777777777777777777777777777777777777777777777777777777', TRUE, 'Equipment maintenance'),
('a0000000-0000-0000-0000-000000000230', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000080', 'gnosis', '2026-02-01', 'out', 150.0, 'USDC', 150.0, 150.0, 'Adelphi Bioinputs Network', 'Water storage and irrigation upkeep', '0xcccaaaaa88888888888888888888888888888888888888888888888888888888', TRUE, 'Irrigation upkeep')
ON CONFLICT (id) DO UPDATE SET
    location_id = EXCLUDED.location_id,
    wallet_id = EXCLUDED.wallet_id,
    chain = EXCLUDED.chain,
    event_date = EXCLUDED.event_date,
    flow_direction = EXCLUDED.flow_direction,
    amount = EXCLUDED.amount,
    token = EXCLUDED.token,
    token_amount = EXCLUDED.token_amount,
    usd_value = EXCLUDED.usd_value,
    source = EXCLUDED.source,
    purpose = EXCLUDED.purpose,
    tx_hash = EXCLUDED.tx_hash,
    verified = EXCLUDED.verified,
    notes = EXCLUDED.notes;
