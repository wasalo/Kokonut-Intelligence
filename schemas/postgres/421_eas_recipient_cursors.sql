-- Keep EAS pagination checkpoints per tracked recipient. A chain-wide
-- timestamp can skip attestations when wallet feeds advance at different rates.
BEGIN;

CREATE TABLE IF NOT EXISTS eas_indexer_cursor (
    chain TEXT NOT NULL CHECK (chain IN ('celo', 'optimism', 'base')),
    wallet_id UUID NOT NULL REFERENCES wallet_profile(id) ON DELETE CASCADE,
    last_attestation_time BIGINT NOT NULL DEFAULT 0
        CHECK (last_attestation_time >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (chain, wallet_id)
);

COMMENT ON TABLE eas_indexer_cursor IS
    'Per-recipient EAS timestamp cursors. Successful recipient writes and cursor advances commit atomically.';

-- Preserve the previous chain watermark for wallets already present so this
-- change does not trigger an unexpected historical reindex on upgrade. New
-- wallet profiles start at zero and receive their complete recipient history.
INSERT INTO eas_indexer_cursor (chain, wallet_id, last_attestation_time)
SELECT lower(wallet.chain), wallet.id,
       CASE
           WHEN status.metadata ->> 'last_attestation_time' ~ '^[0-9]{1,18}$'
               THEN (status.metadata ->> 'last_attestation_time')::BIGINT
           ELSE 0
       END
  FROM wallet_profile AS wallet
  LEFT JOIN chain_indexer_status AS status
    ON status.chain = lower(wallet.chain)
   AND status.indexer_type = 'eas'
 WHERE lower(wallet.chain) IN ('celo', 'optimism', 'base')
ON CONFLICT (chain, wallet_id) DO NOTHING;

COMMIT;
