# Crop-cycle NOI snapshot reconciliation

**Updated:** 11 October 2026. This closes a data-path defect found while
reviewing migration 354 and the crop-cycle NOI view. It does not authorize an
active-target migration or schedule activation.

## Finding

The preserved populated clone had six completed crop cycles, six rows in
`v_crop_cycle_noi`, and six `noi_snapshot` rows. An independent aggregate over
verified/published source events matched the view for NOI and harvest loss rate
on all six cycles. Every existing snapshot differed from the current view; all
six were last calculated on 19 July 2026.

The Directus hook already called `ON CONFLICT (crop_cycle_id)`, but the table
had no unique index for that conflict key. That write cannot succeed until the
database enforces the one-snapshot-per-cycle contract. Its merge also omitted
location/period fields and returns/discounts. Directus is optional in Kernel, so
the owned scheduler also needs a native refresh command.

## Changes

- Migration [379](../../schemas/postgres/379_noi_snapshot_crop_cycle_key.sql)
  adds a unique index on `noi_snapshot.crop_cycle_id`. It fails transactionally
  if a target contains duplicate snapshots; it does not delete or merge them.
- `python3 -m services.metrics --reconcile-noi-snapshots` upserts eligible
  (`active`, `flowering`, `harvesting`, `harvested`, `completed`) crop cycles
  from `v_crop_cycle_noi` in one transaction. It refreshes the entire snapshot
  contract, including `returns_and_discounts`, dates, location, calculation
  version, and source-view metadata.
- `services.core.jobs` now exposes the `noi_snapshots` daily JobSpec. It remains
  disabled until the schedule owner approves activation.
- The Directus hook now writes and merges the same fields and source-view
  metadata. Migration 379 supplies the unique conflict key required by Knex.

## Isolated evidence

The SAFE entries in migration 354 were checked with read-only calls to the
official Gnosis Chain RPC (chain ID 100). Both SAFE contracts and the referenced
Baal contract have code. The two SAFE owner lists, thresholds, versions, and
nonces matched the seed values (the Core Team seed's `1.4.1+L2` label reports
`1.4.1` through the contract version getter). See the sanitized
[evidence record](builds/2026-10-11-recovery/noi-snapshot-parity.json) and the
[Gnosis Chain network documentation](https://docs.gnosischain.com/about/networks/).

NOI was first compared on the preserved migration-review clone using read-only
queries. Then a separate volume copy was started with networking disabled.
Migration 379 was applied with the repository's checksum-tracked runner, and
the reconciliation SQL was exercised on that copy: six rows were upserted,
all snapshot/view financial fields matched, and no duplicate crop-cycle keys
remained. The archived source clone, current candidate, and stopped legacy
stack were not changed. PostgreSQL emitted a copied-cluster collation-version
warning; queries and migration completed successfully. The temporary container,
volume copy, and Compose manifest were removed after evidence capture.

## Remaining gates and rollback

Before applying to any active target, make a verified backup, run the migration
plan and checksum checks against that exact target, and verify that duplicate
`crop_cycle_id` groups are zero. Reconcile only after migration 379 succeeds.
The new scheduled task remains disabled until its owner reviews run history,
cutover ordering, and retry policy; the direct command is available for a
controlled reconciliation.

If the refreshed values fail target review, disable the new task and restore
the affected snapshot rows from the verified pre-run backup. Keep the additive
unique index unless a reviewed forward migration explicitly rolls it back;
never edit migration 379 after application.
