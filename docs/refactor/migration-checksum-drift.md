# Archived application migration checksum drift

**Status (11 October 2026):** the historical checksum mismatch has been
resolved in the checked-out migration sources. `schemas/postgres/000_extensions.sql`
now matches the exact source recovered from the stopped legacy worker image;
the later extension additions are in new migration 378. The retained archived
application clone and its ledger remain unchanged. No pending migration has
been applied to it.

## Findings and source correction

The archived `kokonut_intelligence` ledger has 344 applied schema rows. The
previous source snapshot had 368 schema files and one mismatch at
`schema:000_extensions.sql`: the database stored
`cf493b739f31cb2a9fb215dd5c7ccbc1ed2c8a2584ce156857416360a741a245`, while the
then-current source added a sync comment and `CREATE EXTENSION IF NOT EXISTS`
statements for `postgis_topology`, `pg_trgm`, and `pg_stat_statements`.

The exact deployed file was extracted from
`/app/schemas/postgres/000_extensions.sql` in the stopped local image
`kokonut-intelligence-kokonut-worker:latest` (image ID
`sha256:88f9a69b3c3b938f3878b00ff5502127e6938495920294619db43d22d90f2ed0`,
created 23 July 2026). Its SHA256 matches the archived ledger. The preserved
copy is [legacy-image-000_extensions.sql](builds/2026-10-11-recovery/provenance/legacy-image-000_extensions.sql).

Git history shows the edited file was reintroduced on 9 October 2026, after
migration checksum enforcement was introduced on 15 July 2026. The runner's
policy says newly introduced drift must be handled by a new migration, and the
repair allowlist has no entry for this migration. I restored the active
`000_extensions.sql` to its verified deployed bytes and added
[`378_optional_extensions.sql`](../../schemas/postgres/378_optional_extensions.sql)
for the three later idempotent extension declarations. This preserves the
archived checksum without repairing the ledger or weakening drift detection.
All six extensions in the current first-boot configuration were already present
in the archived database.

The post-alignment read-only schema-only plan succeeded against the retained
archived clone: all 344 applied schema rows match the restored sources, and 25
current schema migrations remain pending (353 through 378, with the existing
numbering gaps). The plan applied no migrations and changed no database state.
The exact pending list is in the machine-readable evidence.

## Validation and remaining gates

`python3 -m services.migration.cli validate --schemas-only` validated all 369
current migration sources, and `tests/test_migration.py` passed (17 tests). The
runner now wraps each migration body and ledger row in one transaction; balanced
existing migration wrappers are normalized, while unbalanced/nested markers are
rejected. A fresh scratch database in a second-generation copy applied all 369
sources through migration 378, reported zero pending migrations, and passed the
actual-view role fixture with synthetic rows rolled back. A third-generation
clone replayed all 369 sources through the transactional runner. An intentional
duplicate-table failure rolled back both its first table creation and ledger
write (`0|0`), and the source/checksum plan remained at zero pending. The earlier
368-migration run remains historical; the transactional runner record is
separate from the reporting-role fixture evidence.

The 25 pending migrations were reviewed in order and applied successfully to a
separate network-isolated copy of the archived clone. All 16 selected populated
table fingerprints over pre-existing columns matched; the retained archived
clone remains unchanged with 25 pending migrations. The migration-354 SAFE records' code, owners, thresholds, versions, and nonces
now match read-only Gnosis Chain calls. An independent source-event recomputation
matched the NOI view for six cycles; six snapshots were stale because the Directus
conflict key lacked a unique index. Migration 379, the native reconciler, and
Directus-hook alignment were exercised on a further network-disabled copy and
brought all six snapshots into parity. Before applying to an active target, check
for duplicate snapshot keys, review target objects and checksums, and take a
verified backup. Populated report parity and Metabase source setup remain gated.

Sanitized investigation and pending-plan details are in
[application-migration-checksum-drift.json](builds/2026-10-11-recovery/application-migration-checksum-drift.json).
Source-aligned scratch and reporting-role acceptance are in
[kokonut-reporting-contract-source-aligned.json](builds/2026-10-11-recovery/kokonut-reporting-contract-source-aligned.json).
Transactional replay and failure atomicity are in
[kokonut-reporting-transactional-run.json](builds/2026-10-11-recovery/kokonut-reporting-transactional-run.json).
Populated-clone compatibility review and row fingerprints are in
[application-migration-populated-clone-replay.json](builds/2026-10-11-recovery/application-migration-populated-clone-replay.json),
[application-migration-review-fingerprints.json](builds/2026-10-11-recovery/application-migration-review-fingerprints.json),
and [the per-migration review](pending-migration-compatibility-review.md).
NOI and SAFE evidence: [reconciliation record](noi-snapshot-reconciliation.md)
and [sanitized results](builds/2026-10-11-recovery/noi-snapshot-parity.json).
