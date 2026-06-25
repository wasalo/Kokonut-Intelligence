-- ============================================================
-- Pilot Farm Seed Data: Web3 & On-Chain
-- Kokonut Adelphi — Web3 & On-Chain
-- ============================================================

-- Protocols (must exist before digital_lego_usage)
INSERT INTO protocol (id, name, slug, chain, protocol_type, category, contract_address, description, metadata) VALUES
('a0000000-0000-0000-0000-000000000170', 'Kokonut Treasury', 'kokonut-treasury', 'gnosis', 'dao', 'treasury', '0xeb55b75328a8dffd45bbf34b7e7efc431a179085', 'Kokonut Moloch DAO treasury on Gnosis Chain', '{"chain_id":100,"contract_type":"moloch_v2"}'::jsonb),
('a0000000-0000-0000-0000-000000000171', 'Public Nouns', 'public-nouns', 'ethereum', 'dao', 'public_goods', NULL, 'Public goods funding context for Kokonut Adelphi', '{"funding_context":"Nouns #69"}'::jsonb),
('a0000000-0000-0000-0000-000000000172', 'Celo EAS', 'celo-eas', 'celo', 'attestation', 'impact', NULL, 'Ethereum Attestation Service on Celo for Kokonut MRV and impact attestations', '{"chain_id":42220,"primary_attestation_chain":true}'::jsonb)
ON CONFLICT (id) DO UPDATE SET
    slug = EXCLUDED.slug,
    name = EXCLUDED.name,
    chain = EXCLUDED.chain,
    protocol_type = EXCLUDED.protocol_type,
    category = EXCLUDED.category,
    contract_address = EXCLUDED.contract_address,
    description = EXCLUDED.description,
    metadata = EXCLUDED.metadata;

UPDATE digital_lego_usage
SET verified = TRUE
WHERE location_id = 'a0000000-0000-0000-0000-000000000001';

-- Wallet Activity Events (all addresses must be exactly 42 chars: 0x + 40 hex)
INSERT INTO wallet_activity_event (id, wallet_id, chain, tx_hash, block_number, block_timestamp, activity_type, from_address, to_address, value, token, token_amount, gas_used, status) VALUES
('a0000000-0000-0000-0000-000000000180', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa111111111111111111111111111111111111111111111111111111111111', 18500000, '2025-10-01 10:00:00+00', 'transfer', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0x1234567890abcdef1234567890abcdef12345678', 5.0, 'ETH', 5.0, 21000, 'success'),
('a0000000-0000-0000-0000-000000000181', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa222222222222222222222222222222222222222222222222222222222222', 18501000, '2025-10-05 14:30:00+00', 'deposit', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0x1234567890abcdef1234567890abcdef12345678', 2.0, 'ETH', 2.0, 45000, 'success'),
('a0000000-0000-0000-0000-000000000182', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb111111111111111111111111111111111111111111111111111111111111', 12000000, '2025-10-10 09:00:00+00', 'transfer', '0x1234567890abcdef1234567890abcdef12345678', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 1000.0, 'USDC', 1000.0, 35000, 'success'),
('a0000000-0000-0000-0000-000000000183', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb222222222222222222222222222222222222222222222222222222222222', 12001000, '2025-10-15 11:00:00+00', 'swap', '0x1234567890abcdef1234567890abcdef12345678', '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 1000.0, 'USDC', 1000.0, 65000, 'success'),
('a0000000-0000-0000-0000-000000000184', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb333333333333333333333333333333333333333333333333333333333333', 12002000, '2025-11-01 10:00:00+00', 'deposit', '0x1234567890abcdef1234567890abcdef12345678', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 500.0, 'USDC', 500.0, 40000, 'success'),
('a0000000-0000-0000-0000-000000000185', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa333333333333333333333333333333333333333333333333333333333333', 18550000, '2025-11-15 16:00:00+00', 'vote', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0x0000000000000000000000000000000000000000', 0.0, 'ETH', 0.0, 80000, 'success'),
('a0000000-0000-0000-0000-000000000186', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb444444444444444444444444444444444444444444444444444444444444', 12003000, '2025-12-01 09:00:00+00', 'withdraw', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '0x1234567890abcdef1234567890abcdef12345678', 300.0, 'USDC', 300.0, 42000, 'success'),
('a0000000-0000-0000-0000-000000000187', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa444444444444444444444444444444444444444444444444444444444444', 18600000, '2025-12-15 12:00:00+00', 'transfer', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0x1234567890abcdef1234567890abcdef12345678', 1.0, 'ETH', 1.0, 21000, 'success'),
('a0000000-0000-0000-0000-000000000188', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb555555555555555555555555555555555555555555555555555555555555', 12004000, '2026-01-05 10:00:00+00', 'deposit', '0x1234567890abcdef1234567890abcdef12345678', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 750.0, 'USDC', 750.0, 38000, 'success'),
('a0000000-0000-0000-0000-000000000189', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb666666666666666666666666666666666666666666666666666666666666', 12005000, '2026-01-20 14:00:00+00', 'swap', '0x1234567890abcdef1234567890abcdef12345678', '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 750.0, 'USDC', 750.0, 62000, 'success'),
('a0000000-0000-0000-0000-00000000018a', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb777777777777777777777777777777777777777777777777777777777777', 12006000, '2026-02-01 09:00:00+00', 'deposit', '0x1234567890abcdef1234567890abcdef12345678', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 400.0, 'USDC', 400.0, 36000, 'success'),
('a0000000-0000-0000-0000-00000000018b', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa555555555555555555555555555555555555555555555555555555555555', 18650000, '2026-02-15 11:00:00+00', 'stake', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0xcccccccccccccccccccccccccccccccccccccccc', 3.0, 'ETH', 3.0, 95000, 'success'),
('a0000000-0000-0000-0000-00000000018c', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb888888888888888888888888888888888888888888888888888888888888', 12007000, '2026-02-28 10:00:00+00', 'withdraw', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '0x1234567890abcdef1234567890abcdef12345678', 200.0, 'USDC', 200.0, 41000, 'success'),
('a0000000-0000-0000-0000-00000000018d', 'a0000000-0000-0000-0000-000000000081', 'optimism', '0xbbbb999999999999999999999999999999999999999999999999999999999999', 12008000, '2026-03-01 09:00:00+00', 'deposit', '0x1234567890abcdef1234567890abcdef12345678', '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 600.0, 'USDC', 600.0, 37000, 'success'),
('a0000000-0000-0000-0000-00000000018e', 'a0000000-0000-0000-0000-000000000080', 'ethereum', '0xaaaa666666666666666666666666666666666666666666666666666666666666', 18700000, '2026-03-10 15:00:00+00', 'transfer', '0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18', '0x1234567890abcdef1234567890abcdef12345678', 0.5, 'ETH', 0.5, 21000, 'success')
ON CONFLICT (id) DO UPDATE SET
    wallet_id = EXCLUDED.wallet_id,
    chain = EXCLUDED.chain,
    tx_hash = EXCLUDED.tx_hash,
    block_number = EXCLUDED.block_number,
    block_timestamp = EXCLUDED.block_timestamp,
    activity_type = EXCLUDED.activity_type,
    from_address = EXCLUDED.from_address,
    to_address = EXCLUDED.to_address,
    value = EXCLUDED.value,
    token = EXCLUDED.token,
    token_amount = EXCLUDED.token_amount,
    gas_used = EXCLUDED.gas_used,
    status = EXCLUDED.status;

-- Digital Lego Usage
INSERT INTO digital_lego_usage (id, wallet_id, protocol_id, location_id, usage_date, action_type, amount, token, chain, value_attributed, attribution_method, notes) VALUES
('a0000000-0000-0000-0000-000000000190', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'a0000000-0000-0000-0000-000000000001', '2025-10-10', 'deposit', 1000.0, 'USDC', 'gnosis', 1000.00, 'direct', 'Initial treasury deposit for Adelphi operations'),
('a0000000-0000-0000-0000-000000000191', 'a0000000-0000-0000-0000-000000000080', 'a0000000-0000-0000-0000-000000000171', 'a0000000-0000-0000-0000-000000000001', '2025-11-15', 'lend', 3.0, 'ETH', 'ethereum', 4500.00, 'direct', 'Green bond lending for irrigation upgrade'),
('a0000000-0000-0000-0000-000000000192', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000172', 'a0000000-0000-0000-0000-000000000001', '2025-12-01', 'attest', 1.0, 'CELO', 'celo', 250.00, 'proportional', 'Ecological impact attestation for syntropic beds'),
('a0000000-0000-0000-0000-000000000193', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000170', 'a0000000-0000-0000-0000-000000000001', '2026-01-05', 'withdraw', 500.0, 'USDC', 'gnosis', 500.00, 'direct', 'Seedling purchase withdrawal'),
('a0000000-0000-0000-0000-000000000194', 'a0000000-0000-0000-0000-000000000081', 'a0000000-0000-0000-0000-000000000172', 'a0000000-0000-0000-0000-000000000001', '2026-02-15', 'attest', 1.0, 'CELO', 'celo', 250.00, 'proportional', 'Carbon and biodiversity co-benefit attestation for Adelphi')
ON CONFLICT (id) DO UPDATE SET
    wallet_id = EXCLUDED.wallet_id,
    protocol_id = EXCLUDED.protocol_id,
    location_id = EXCLUDED.location_id,
    usage_date = EXCLUDED.usage_date,
    action_type = EXCLUDED.action_type,
    amount = EXCLUDED.amount,
    token = EXCLUDED.token,
    chain = EXCLUDED.chain,
    value_attributed = EXCLUDED.value_attributed,
    attribution_method = EXCLUDED.attribution_method,
    notes = EXCLUDED.notes;

-- Attestation Schemas (use unique schema_uids not already in DB)
INSERT INTO attestation_schema (id, schema_uid, name, description, schema_text, chain, version, active) VALUES
('a0000000-0000-0000-0000-0000000001a0', '0x5555555555555555555555555555555555555555555555555555555555555555', 'Kokonut Pilot MRV', 'MRV attestation schema for pilot farm operations', 'string locationId, string cropType, string activityType, string date, uint256 quantity, string unit, string evidenceHash', 'optimism', 1, TRUE),
('a0000000-0000-0000-0000-0000000001a1', '0x6666666666666666666666666666666666666666666666666666666666666666', 'Kokonut Pilot Impact', 'Impact attestation schema for pilot farm ecological outcomes', 'string locationId, string metric, uint256 value, string unit, string period, string evidenceHash', 'optimism', 1, TRUE)
ON CONFLICT (id) DO NOTHING;

-- Attestation Records
INSERT INTO attestation_record (id, attestation_uid, schema_id, claim_type, subject_id, subject_type, claim_data, status, chain, tx_hash, attested_at) VALUES
('a0000000-0000-0000-0000-0000000001b0', '0xab00000000000000000000000000000000000000000000000000000000000001', 'a0000000-0000-0000-0000-0000000001a0', 'mrv', 'a0000000-0000-0000-0000-000000000040', 'crop_cycle', '{"locationId":"a0000000-0000-0000-0000-000000000001","cropType":"Maize","activityType":"planting","date":"2025-10-01","quantity":4.0,"unit":"hectares"}', 'published', 'optimism', '0xab00000000000000000000000000000000000000000000000000000000000001', '2025-10-02 10:00:00+00'),
('a0000000-0000-0000-0000-0000000001b1', '0xab00000000000000000000000000000000000000000000000000000000000002', 'a0000000-0000-0000-0000-0000000001a0', 'mrv', 'a0000000-0000-0000-0000-000000000040', 'harvest_event', '{"locationId":"a0000000-0000-0000-0000-000000000001","cropType":"Maize","activityType":"harvest","date":"2025-12-20","quantity":34.96,"unit":"tonnes"}', 'published', 'optimism', '0xab00000000000000000000000000000000000000000000000000000000000002', '2025-12-21 10:00:00+00'),
('a0000000-0000-0000-0000-0000000001b2', '0xab00000000000000000000000000000000000000000000000000000000000003', 'a0000000-0000-0000-0000-0000000001a1', 'impact', 'a0000000-0000-0000-0000-000000000001', 'location', '{"locationId":"a0000000-0000-0000-0000-000000000001","metric":"ndvi_change","value":0.27,"unit":"index","period":"Oct-Dec 2025"}', 'published', 'optimism', '0xab00000000000000000000000000000000000000000000000000000000000003', '2025-12-31 10:00:00+00'),
('a0000000-0000-0000-0000-0000000001b3', '0xab00000000000000000000000000000000000000000000000000000000000004', 'a0000000-0000-0000-0000-0000000001a0', 'mrv', 'a0000000-0000-0000-0000-000000000042', 'crop_cycle', '{"locationId":"a0000000-0000-0000-0000-000000000001","cropType":"Cassava","activityType":"harvest","date":"2026-03-15","quantity":21.38,"unit":"tonnes"}', 'published', 'optimism', '0xab00000000000000000000000000000000000000000000000000000000000004', '2026-03-16 10:00:00+00')
ON CONFLICT (id) DO NOTHING;

-- Chain Indexer Status (avoid duplicates with existing ethereum/rpc, ethereum/eas, optimism/eas, ethereum/subgraph)
INSERT INTO chain_indexer_status (id, chain, indexer_type, last_synced_block, last_synced_at, status) VALUES
('a0000000-0000-0000-0000-0000000001c0', 'optimism', 'rpc', 12008000, '2026-03-01 09:00:00+00', 'healthy'),
('a0000000-0000-0000-0000-0000000001c1', 'base', 'rpc', 8000000, '2026-03-01 09:00:00+00', 'healthy')
ON CONFLICT (id) DO NOTHING;
