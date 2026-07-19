-- Gnosis Chain — Kokonut Moloch DAO seed data
-- Chain indexer status and DAO contract wallet profiles

-- Chain indexer status for Gnosis Chain
INSERT INTO chain_indexer_status (chain, indexer_type, last_synced_block, last_synced_at, status, metadata)
VALUES ('gnosis', 'rpc', 0, NOW(), 'syncing', '{"chain_id":100,"source":"kokonut moloch dao"}'::jsonb)
ON CONFLICT (chain, indexer_type) DO UPDATE SET
    last_synced_block = EXCLUDED.last_synced_block,
    last_synced_at = EXCLUDED.last_synced_at,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Protocol: Kokonut Treasury (Moloch v3 / Baal on Gnosis Chain)
INSERT INTO protocol (id, name, slug, chain, protocol_type, category, contract_address, description, metadata)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'Kokonut Treasury',
    'kokonut-treasury',
    'gnosis',
    'dao',
    'treasury',
    '0xeb55b75328a8dffd45bbf34b7e7efc431a179085',
    'Kokonut DAO treasury on Gnosis Chain — Moloch v3 (Baal), rage-quit-enabled SAFE wallet',
    '{"chain_id": 100, "contract_type": "moloch_v3_baal", "baal": "0x5DcE1044A7E2E35D6524001796cee47252f18411", "token_manager": "0x8977c56e979f0d8b76afb5ad85549acd2e96422d", "shares": "0x8124Cbb807A7b64123F3dEc3EF64995d8B10d3Eb", "loot": "0x0444AE984b9563C8480244693ED65F25B3C64a4E", "zodiac": "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552", "vkkn_token": "0xc6b075ac3234a7ac729114b27370b552fa284690", "loot_token": "0x2508a11aee11ad545bae87cd42131c04613b2099"}'::jsonb
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    chain = EXCLUDED.chain,
    protocol_type = EXCLUDED.protocol_type,
    category = EXCLUDED.category,
    contract_address = EXCLUDED.contract_address,
    description = EXCLUDED.description,
    metadata = EXCLUDED.metadata;

-- Wallet profiles for DAO contracts
INSERT INTO wallet_profile (address, chain, chain_id, role, label, owner_type, is_active, metadata)
VALUES
    -- Main Treasury (SAFE)
    (
        '0xeb55b75328a8dffd45bbf34b7e7efc431a179085',
        'gnosis',
        100,
        'treasury',
        'Kokonut Treasury SAFE',
        'dao',
        true,
        '{"contract_type": "ragequit_safe", "description": "Main DAO treasury — rage-quit-enabled"}'
    ),
    -- Token Manager
    (
        '0x8977c56e979f0d8b76afb5ad85549acd2e96422d',
        'gnosis',
        100,
        'token_manager',
        'Kokonut Token Manager',
        'dao',
        true,
        '{"contract_type": "moloch_v2", "description": "Handles token issuance and DAO smart wallet operations"}'
    ),
    -- $vKKN Voting Token
    (
        '0xc6b075ac3234a7ac729114b27370b552fa284690',
        'gnosis',
        100,
        'token',
        '$vKKN Voting Token',
        'dao',
        true,
        '{"token_type": "soulbound_voting", "description": "Soulbound governance token — 1 token = 1 vote"}'
    ),
    -- Loot Token
    (
        '0x2508a11aee11ad545bae87cd42131c04613b2099',
        'gnosis',
        100,
        'token',
        'Loot Token',
        'dao',
        true,
        '{"token_type": "soulbound_loot", "description": "Non-voting soulbound token — economic rights without governance voting"}'
    )
ON CONFLICT (address, chain) DO UPDATE SET
    chain_id = EXCLUDED.chain_id,
    role = EXCLUDED.role,
    label = EXCLUDED.label,
    owner_type = EXCLUDED.owner_type,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Baal core, Shares/Loot ERC20, and Zodiac module contract profiles (Moloch v3).
INSERT INTO wallet_profile (address, chain, chain_id, role, label, owner_type, is_active, metadata)
VALUES
    (
        '0x5DcE1044A7E2E35D6524001796cee47252f18411',
        'gnosis',
        100,
        'dao',
        'Kokonut DAO Baal (Moloch v3 core)',
        'dao',
        true,
        '{"contract_type": "baal", "description": "Baal core contract — proposal/vote/ragequit/shaman logic"}'
    ),
    (
        '0x8124Cbb807A7b64123F3dEc3EF64995d8B10d3Eb',
        'gnosis',
        100,
        'token',
        'Kokonut vKKN Shares (Baal ERC20)',
        'dao',
        true,
        '{"token_type": "soulbound_voting", "description": "Baal SharesERC20 — 1 share = 1 vote"}'
    ),
    (
        '0x0444AE984b9563C8480244693ED65F25B3C64a4E',
        'gnosis',
        100,
        'token',
        'Kokonut Loot (Baal ERC20)',
        'dao',
        true,
        '{"token_type": "soulbound_loot", "description": "Baal LootERC20 — economic rights without governance voting"}'
    ),
    (
        '0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552',
        'gnosis',
        100,
        'dao',
        'Kokonut DAO Zodiac Module',
        'dao',
        true,
        '{"contract_type": "zodiac", "description": "Zodiac module attached to the Kokonut DAO"}'
    )
ON CONFLICT (address, chain) DO UPDATE SET
    chain_id = EXCLUDED.chain_id,
    role = EXCLUDED.role,
    label = EXCLUDED.label,
    owner_type = EXCLUDED.owner_type,
    is_active = EXCLUDED.is_active,
    metadata = EXCLUDED.metadata,
    updated_at = NOW();

-- Governance framework registry: Baal is the live framework; the others are
-- declared as configured frameworks for future adapters.
INSERT INTO governance_framework (framework_key, name, chain, contract_address, abi_ref, is_active, config_json)
VALUES
    (
        'moloch_v3_baal',
        'Kokonut DAO (Moloch v3 / Baal)',
        'gnosis',
        '0x5DcE1044A7E2E35D6524001796cee47252f18411',
        'Baal.json',
        true,
        '{"chain_id": 100, "tokens": {"shares": "0x8124Cbb807A7b64123F3dEc3EF64995d8B10d3Eb", "loot": "0x0444AE984b9563C8480244693ED65F25B3C64a4E"}, "treasury": "0xeb55b75328a8dffd45bbf34b7e7efc431a179085"}'::jsonb
    ),
    (
        'moloch_v2',
        'Legacy Kokonut DAO (Moloch v2)',
        'gnosis',
        '0x8977c56e979f0d8b76afb5ad85549acd2e96422d',
        'MolochV2.json',
        false,
        '{"chain_id": 100, "note": "historical only — read via gnosis_indexer"}'::jsonb
    ),
    (
        'governor',
        'OpenZeppelin Governor (stub)',
        'gnosis',
        NULL,
        NULL,
        false,
        '{"status": "planned"}'::jsonb
    ),
    (
        'aragon',
        'Aragon DAO (stub)',
        'gnosis',
        NULL,
        NULL,
        false,
        '{"status": "planned"}'::jsonb
    ),
    (
        'colony',
        'Colony (existing integration)',
        'gnosis',
        NULL,
        NULL,
        false,
        '{"status": "existing"}'::jsonb
    )
ON CONFLICT (framework_key) DO UPDATE SET
    name = EXCLUDED.name,
    chain = EXCLUDED.chain,
    contract_address = EXCLUDED.contract_address,
    abi_ref = EXCLUDED.abi_ref,
    is_active = EXCLUDED.is_active,
    config_json = EXCLUDED.config_json,
    updated_at = NOW();
