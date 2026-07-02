-- ============================================================
-- Celo EAS Seed Data
-- Kokonut Intelligence — EAS on Celo
-- ============================================================

-- Chain indexer status for Celo
INSERT INTO chain_indexer_status (id, chain, indexer_type, last_synced_block, last_synced_at, status) VALUES
('a0000000-0000-0000-0000-0000000001d0', 'celo', 'rpc', 0, NOW(), 'syncing'),
('a0000000-0000-0000-0000-0000000001d1', 'celo', 'eas', 0, NOW(), 'syncing')
ON CONFLICT (chain, indexer_type) DO UPDATE SET
    last_synced_block = EXCLUDED.last_synced_block,
    last_synced_at = EXCLUDED.last_synced_at,
    status = EXCLUDED.status,
    updated_at = NOW();

-- Celo attestation schemas (registered on Celo mainnet 2026-06-12)
INSERT INTO attestation_schema (id, schema_uid, name, description, schema_text, chain, resolver_address, version, active) VALUES
('a0000000-0000-0000-0000-0000000001e0', '0x93af67b8197dda513fa968e597e1c9a2c0d0607d656659f153dc1b065a100e54', 'Kokonut MRV', 'Kokonut MRV claim attestation for farm monitoring, reporting, and verification', 'string locationId, string farmId, string cropType, string activityType, uint256 quantity, string unit, uint256 measurementDate, string evidenceHash, string payloadCid', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE),
('a0000000-0000-0000-0000-0000000001e1', '0xb99bb4b2a55218b8f4df1f0bd4c39400711809f13ef5d150d2903648c6590dfe', 'Kokonut Impact', 'Environmental impact attestation for ecological outcomes', 'string locationId, string metric, int256 value, string unit, string period, string evidenceHash, string payloadCid', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE),
('a0000000-0000-0000-0000-0000000001e2', '0x75b42beb85dd852134dfaff3de41b8dc361ed0cb2bf93ce3009c8ec082de905b', 'Kokonut Financial', 'Financial summary attestation for farm economic performance', 'string locationId, string period, uint256 noi, uint256 revenue, uint256 costs, string currency, string evidenceHash', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE),
('a0000000-0000-0000-0000-0000000001e3', '0xb359f9756e3cb3597e4048dccae2842083359906fbae8dc8c0e9af8ac1b3ccff', 'Kokonut Harvest', 'Harvest verification attestation for crop production records', 'string locationId, string cropCycleId, uint256 quantity, string unit, string qualityGrade, uint256 harvestDate, string evidenceHash', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE),
('a0000000-0000-0000-0000-0000000001e4', '0x59632edcf1d04be0c2dcfd572282bbd4dac518e7a92872ec45ade29876ef95f5', 'Kokonut Compliance', 'Partner compliance and audit trail attestation', 'string locationId, string framework, string requirement, bool compliant, string evidenceHash, string notes', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE),
('a0000000-0000-0000-0000-0000000001e5', '0x9306a4cf6cc5a9c8aa6598a43bc62cfaa729f7490fe6b2e4cc0df10ec738ff29', 'Kokonut Bio-Batch', 'Bio-organic fertilizer batch production attestation for Latin America and the Caribbean', 'string locationId, string farmId, string batchType, string batchId, uint256 quantityKg, string unit, uint256 productionDate, string qualityGrade, string evidenceHash, string payloadCid', 'celo', '0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad', 1, TRUE)
ON CONFLICT (id) DO UPDATE SET
    schema_uid = EXCLUDED.schema_uid,
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    schema_text = EXCLUDED.schema_text,
    chain = EXCLUDED.chain,
    resolver_address = EXCLUDED.resolver_address,
    version = EXCLUDED.version,
    active = EXCLUDED.active;
