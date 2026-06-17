-- Gnosis Chain — Kokonut Moloch DAO seed data
-- Chain indexer status and DAO contract wallet profiles

-- Chain indexer status for Gnosis Chain
INSERT INTO chain_indexer_status (chain, indexer_type, last_synced_block, status)
VALUES ('gnosis', 'rpc', 0, 'pending')
ON CONFLICT (chain, indexer_type) DO NOTHING;

-- Protocol: Kokonut Treasury (DAOHaus Moloch v2)
INSERT INTO protocol (id, name, slug, chain, protocol_type, contract_address, description, metadata)
VALUES (
    'b0000000-0000-0000-0000-000000000001',
    'Kokonut Treasury',
    'kokonut-treasury',
    'gnosis',
    'dao',
    '0xeb55b75328a8dffd45bbf34b7e7efc431a179085',
    'Kokonut Moloch DAO treasury on Gnosis Chain — rage-quit-enabled SAFE wallet',
    '{"chain_id": 100, "contract_type": "moloch_v2", "token_manager": "0x8977c56e979f0d8b76afb5ad85549acd2e96422d", "vkkn_token": "0xc6b075ac3234a7ac729114b27370b552fa284690", "loot_token": "0x2508a11aee11ad545bae87cd42131c04613b2099"}'
)
ON CONFLICT (slug) DO NOTHING;

-- Wallet profiles for DAO contracts
INSERT INTO wallet_profile (address, chain, role, label, owner_type, is_active, metadata)
VALUES
    -- Main Treasury (SAFE)
    (
        '0xeb55b75328a8dffd45bbf34b7e7efc431a179085',
        'gnosis',
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
        'token',
        'Loot Token',
        'dao',
        true,
        '{"token_type": "soulbound_loot", "description": "Non-voting soulbound token — economic rights without governance voting"}'
    )
ON CONFLICT (address, chain) DO NOTHING;
