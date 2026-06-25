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

-- Protocol: Kokonut Treasury (DAOHaus Moloch v2)
INSERT INTO protocol (id, name, slug, chain, protocol_type, category, contract_address, description, metadata)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'Kokonut Treasury',
    'kokonut-treasury',
    'gnosis',
    'dao',
    'treasury',
    '0xeb55b75328a8dffd45bbf34b7e7efc431a179085',
    'Kokonut Moloch DAO treasury on Gnosis Chain — rage-quit-enabled SAFE wallet',
    '{"chain_id": 100, "contract_type": "moloch_v2", "token_manager": "0x8977c56e979f0d8b76afb5ad85549acd2e96422d", "vkkn_token": "0xc6b075ac3234a7ac729114b27370b552fa284690", "loot_token": "0x2508a11aee11ad545bae87cd42131c04613b2099"}'::jsonb
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
