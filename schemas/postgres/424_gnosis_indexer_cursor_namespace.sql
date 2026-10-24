-- Migration 424: give the Moloch event indexer its own cursor.
-- The legacy (gnosis, rpc) row was shared with wallet-activity indexing. Copy
-- its last observed boundary as a conservative resume point; the old row stays
-- intact for the general RPC indexer. Do not infer that copied status is fresh.
BEGIN;

INSERT INTO public.chain_indexer_status (
    chain,
    indexer_type,
    last_synced_block,
    last_synced_at,
    status,
    error_message,
    metadata,
    updated_at
)
SELECT
    legacy.chain,
    'gnosis_moloch',
    legacy.last_synced_block,
    legacy.last_synced_at,
    'paused',
    NULL,
    COALESCE(legacy.metadata, '{}'::jsonb) || jsonb_build_object(
        'cursor_migration', '424_gnosis_indexer_cursor_namespace',
        'cursor_origin', 'legacy_shared_rpc'
    ),
    NOW()
FROM public.chain_indexer_status AS legacy
WHERE legacy.chain = 'gnosis'
  AND legacy.indexer_type = 'rpc'
ON CONFLICT (chain, indexer_type) DO NOTHING;

COMMENT ON COLUMN public.chain_indexer_status.indexer_type IS
    'Identifies an independent chain indexer cursor; gnosis_moloch is separate from the general rpc wallet-activity cursor.';

COMMIT;
