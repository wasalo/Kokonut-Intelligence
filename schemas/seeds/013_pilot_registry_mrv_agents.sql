-- ============================================================
-- Pilot Farm Seed Data: Registry, MRV Events, Attestation Requests, Agents
-- ============================================================

INSERT INTO farm_registry_record (
    id, farm_id, location_id, registry_slug, project_date, forecasted_budget,
    land_size_m2, project_location, source_of_funding, revenue_streams,
    governance_mechanism, token_allocation, public_goods_allocation_pct,
    project_summary, local_problem, proposed_solution, target_market,
    record_hash, status, schema_version, source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000500',
    'a0000000-0000-0000-0000-000000000010',
    'a0000000-0000-0000-0000-000000000001',
    'kokonut-demo-farm-kisumu',
    '2025-09-01',
    85000.00,
    120000.0000,
    '{"coordinates":"-0.100000,34.750000","region":"Kisumu County","country":"Kenya"}',
    'Kokonut DAO pilot allocation / partner sponsorship seed data',
    ARRAY['maize', 'cassava', 'beans', 'sweet_potato', 'bioinputs'],
    'cooperative',
    '70% farm operators, 20% DAO/community contributors, 10% public goods reserve',
    10.000,
    'Kokonut Demo Farm in Kisumu models mixed-crop regenerative production, bioinput production, MRV-ready ecological tracking, and DAO-linked value flows.',
    'Smallholder farms in the region face unstable crop income, degraded soil health, and limited access to transparent working capital.',
    'The pilot combines governed crop economics, bioinputs, ecological monitoring, partner sales, and verifiable reporting to improve farm resilience and capital access.',
    ARRAY['local_processors', 'direct_buyers', 'partner_sponsors'],
    '8a1a0b424633cd82e26b405d4fc92e8c5adf6d3467ca8fbfb4b571cc66f3832a',
    'published',
    'common-data-schema-v1',
    'pilot_seed',
    'kokonut-demo-farm-kisumu',
    '{"source":"pilot seed","schema":"common-data-schema-v1"}'
)
ON CONFLICT (registry_slug) DO UPDATE SET
    status = EXCLUDED.status,
    updated_at = NOW();

INSERT INTO inventory_event (
    id, location_id, plot_id, crop_cycle_id, event_date, item_name, item_type,
    event_type, quantity, unit, unit_cost, total_cost, currency, supplier,
    storage_location, notes, status, schema_version, source_system, source_id, source_raw
) VALUES
('a0000000-0000-0000-0000-000000000510', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000040', '2025-10-10', 'Compost tea concentrate', 'biofertilizer', 'received', 40.0000, 'litres', 2.00, 80.00, 'USD', 'On-farm biofactory', 'Biofactory shed', 'Bioinput batch prepared for maize cycle.', 'verified', 'inventory-v1', 'pilot_seed', 'inventory-compost-tea-2025-10', '{"batch":"BIO-2025-10-A"}'),
('a0000000-0000-0000-0000-000000000511', 'a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000020', 'a0000000-0000-0000-0000-000000000040', '2025-10-15', 'Compost tea concentrate', 'biofertilizer', 'consumed', 40.0000, 'litres', 2.00, 80.00, 'USD', 'On-farm biofactory', 'Plot A', 'Applied to soil preparation for maize cycle.', 'published', 'inventory-v1', 'pilot_seed', 'inventory-compost-tea-apply-2025-10', '{"application":"soil_preparation"}')
ON CONFLICT (id) DO NOTHING;

INSERT INTO maintenance_event (
    id, location_id, infrastructure_asset_id, maintenance_date, maintenance_type,
    description, issue_description, work_performed, vendor, labor_hours, parts_used, cost,
    currency, downtime_hours, next_service_date, notes, status, schema_version,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000520',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000070',
    '2025-11-05',
    'preventive',
    'Solar pump seasonal inspection before dry period.',
    'Solar pump seasonal inspection before dry period.',
    'Cleaned filters, checked controller, replaced worn pipe coupling.',
    'Kisumu Solar Pumps',
    3.50,
    '[{"part":"pipe coupling","quantity":1}]',
    45.00,
    'USD',
    1.00,
    '2026-02-05',
    'Preventive maintenance funded from pilot operating budget.',
    'verified',
    'maintenance-v1',
    'pilot_seed',
    'maintenance-solar-pump-2025-11',
    '{"work_order":"WO-2025-11-001"}'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO revenue_event (
    id, location_id, crop_cycle_id, partner_id, sales_event_id, revenue_date,
    revenue_type, description, amount, currency, amount_usd, payment_status,
    received_at, public_goods_allocation_amount, status, schema_version,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000530',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000040',
    'a0000000-0000-0000-0000-000000000053',
    'd0000000-0000-0000-0000-000000000001',
    '2025-12-28',
    'sale',
    'Published maize sale linked to partner processor.',
    12735.20,
    'USD',
    12735.20,
    'paid',
    '2026-01-10 10:00:00+00',
    1273.52,
    'published',
    'revenue-v1',
    'pilot_seed',
    'revenue-maize-sale-2025-12',
    '{"sales_event_id":"d0000000-0000-0000-0000-000000000001"}'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO mrv_event (
    id, farm_registry_record_id, location_id, plot_id, crop_cycle_id, mrv_claim_id,
    measurement_type, event_timestamp, ground_data, remote_data, community_data,
    payload_cid, payload_hash, private_payload_hash, source_record_ids,
    is_attested, attestation_uid, attested_at, status, schema_version,
    source_system, source_id, source_raw
) VALUES (
    'a0000000-0000-0000-0000-000000000540',
    'a0000000-0000-0000-0000-000000000500',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000020',
    'a0000000-0000-0000-0000-000000000040',
    'a0000000-0000-0000-0000-000000000380',
    'mixed',
    '2026-03-16 10:00:00+00',
    '{"volumetric_water_content":19.0,"soil_temperature":24.5,"electrical_conductivity":0.72}',
    '{"ndvi":0.62,"ndre":0.45,"source":"sentinel","image_url":"local://sha256/9a61f6"}',
    '{"crop_cycle_stage":"post_harvest","plant_health_notes":"Maize cycle closed with improved canopy cover and soil moisture retention.","disease_flags":[]}',
    'local://sha256/4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6',
    '4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6',
    'ec0362f71fc3233bb5e31ae6ce2aa69e74310bb774e9564c1c05a553a78d912b',
    ARRAY['a0000000-0000-0000-0000-000000000150'::uuid, 'a0000000-0000-0000-0000-000000000121'::uuid],
    TRUE,
    '0xac00000000000000000000000000000000000000000000000000000000000001',
    '2026-03-20 10:00:00+00',
    'published',
    'kokonut-mrv-v1',
    'pilot_seed',
    'mrv-maize-mixed-2026-03',
    '{"privacy":"private evidence stored off-chain; public record stores CID and hashes only"}'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO attestation_request (
    id, subject_type, subject_id, mrv_event_id, mrv_claim_id, schema_id,
    event_type, chain, payload_cid, payload_hash, private_payload_hash,
    attestor_role, execution_status, attestation_uid, tx_hash, status,
    requested_by, reviewed_at, submitted_at, confirmed_at, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000000550',
    'mrv_event',
    'a0000000-0000-0000-0000-000000000540',
    'a0000000-0000-0000-0000-000000000540',
    'a0000000-0000-0000-0000-000000000380',
    'a0000000-0000-0000-0000-0000000001a1',
    'mrv_submission',
    'optimism',
    'local://sha256/4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6',
    '4f24f70db68140c8584b2ad3e8433a260e4f25d7c607b45cbf1dc64ceb9684b6',
    'ec0362f71fc3233bb5e31ae6ce2aa69e74310bb774e9564c1c05a553a78d912b',
    'verifier',
    'confirmed',
    '0xac00000000000000000000000000000000000000000000000000000000000001',
    '0xac10000000000000000000000000000000000000000000000000000000000001',
    'published',
    'a0000000-0000-0000-0000-000000000060',
    '2026-03-18 10:00:00+00',
    '2026-03-20 09:30:00+00',
    '2026-03-20 10:00:00+00',
    '{"source":"pilot seed","sensitive_data_policy":"private payload hash only; no raw private evidence on-chain"}'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO agent_identity (
    id, agent_name, ens_subdomain, operator_wallet, registry_chain,
    erc8004_agent_id, capability_manifest_cid, payment_token, base_rate_usdc,
    marketplace_source, agent_state, metadata
) VALUES (
    'a0000000-0000-0000-0000-000000000560',
    'kokonut-mrv-reporter',
    'mrv-reporter.kokonut.eth',
    '0x0000000000000000000000000000000000000000',
    'base',
    'local-dev-agent-id',
    'local://sha256/0c7bb2fa833f0a7879f9f2aa65f608f4a32ad103639165f7d046b663d5893fd8',
    '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913',
    5.000000,
    'Kokonut-Agentic-Marketplace',
    'active',
    '{"scope":"metadata only; contract/payment logic is external to this repo"}'
)
ON CONFLICT (agent_name) DO UPDATE SET
    capability_manifest_cid = EXCLUDED.capability_manifest_cid,
    updated_at = NOW();

INSERT INTO agent_capability_manifest (
    id, agent_id, version, manifest, manifest_cid, manifest_hash, is_active
) VALUES (
    'a0000000-0000-0000-0000-000000000561',
    'a0000000-0000-0000-0000-000000000560',
    '1.0.0',
    '{"agent_name":"kokonut-mrv-reporter","version":"1.0.0","description":"Submits verified MRV events and prepares EAS attestation requests.","inputs":{"farm_id":{"type":"string","required":true},"period_start":{"type":"string","required":true},"period_end":{"type":"string","required":true}},"outputs":{"mrv_event_id":{"type":"string"},"eas_attestation_uid":{"type":"string"},"ipfs_cid":{"type":"string"}},"marketplace_logic":"Kokonut-Agentic-Marketplace"}',
    'local://sha256/0c7bb2fa833f0a7879f9f2aa65f608f4a32ad103639165f7d046b663d5893fd8',
    '0c7bb2fa833f0a7879f9f2aa65f608f4a32ad103639165f7d046b663d5893fd8',
    TRUE
)
ON CONFLICT (agent_id, version) DO UPDATE SET
    manifest = EXCLUDED.manifest,
    manifest_cid = EXCLUDED.manifest_cid,
    manifest_hash = EXCLUDED.manifest_hash,
    is_active = TRUE;

INSERT INTO agent_task (
    id, agent_id, task_type, subject_type, subject_id, inputs, output,
    output_cid, output_hash, execution_status, review_status,
    attestation_request_id, completed_at
) VALUES (
    'a0000000-0000-0000-0000-000000000562',
    'a0000000-0000-0000-0000-000000000560',
    'mrv_submission',
    'mrv_event',
    'a0000000-0000-0000-0000-000000000540',
    '{"farm_id":"kokonut-demo-farm-kisumu","period_start":"2026-03-01","period_end":"2026-03-20"}',
    '{"mrv_event_id":"a0000000-0000-0000-0000-000000000540","attestation_request_id":"a0000000-0000-0000-0000-000000000550"}',
    'local://sha256/7fbf9853af506723301d455b142a998102503ee7ffb5d4cffba319f20250b85e',
    '7fbf9853af506723301d455b142a998102503ee7ffb5d4cffba319f20250b85e',
    'completed',
    'published',
    'a0000000-0000-0000-0000-000000000550',
    '2026-03-20 10:00:00+00'
)
ON CONFLICT (id) DO NOTHING;
