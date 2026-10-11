# Batch 2 — legacy logical database restore

10 October 2026. All four encrypted legacy database archives restored successfully
on the recorded compatible PostgreSQL/PostGIS image in a fresh no-network engine.
Original legacy services remained stopped; running Kernel services were unchanged.

## Completed evidence

Ciphertext sizes and SHA256 matched the checkpoint manifest before decryption.
Each target was created from template0 and restored using streaming age decryption,
pg_restore --exit-on-error --single-transaction --no-owner --no-privileges.
No plaintext dump file was written to disk. No migrations or seeds were applied.

| Source archive database | New target database |
| --- | --- |
| kokonut_intelligence | kokonut_intelligence |
| metabase | metabase |
| kokonut_bootstrap_28232 | kokonut_bootstrap_28232 |
| postgres | legacy_postgres_archive |

The control database is recovery_control. Source postgres was restored under a
different name to keep the initialized maintenance database separate.

Counts and sorted whole-row JSON MD5 fingerprints match between the preserved
source clone and logical restore for 13 selected tables:

- schema_migration: 376 rows, including legacy seeds.
- platform_event: 4; sensor_reading: 15; weather_observation: 12.
- wallet_activity_event: 15; attestation_record: 4.
- scheduled_task, task_run and file_upload: 0 each.
- Metabase report_card: 39; report_dashboard: 1; core_user: 1; core_session: 0.

Comparison sessions used repeatable-read/read-only transactions, UTC, identical
float formatting and a bounded statement timeout. Row payloads were not retained.
These fingerprints are comparison evidence, not cryptographic authenticity; age
and ciphertext SHA256 are the separate archive integrity evidence.

[Exact results and identities](builds/2026-10-10-recovery/legacy-logical-restore.json).
The fingerprint queries used count(*) and md5 of sorted row_to_json text for each
explicit table. This does not cover every table or certify domain invariants.

## Operational notes and rollback

The first creation attempt encountered the image's temporary initialization server
shutdown. No target database was created. Final startup and absence of the target
were confirmed before retry. All subsequent archive restores exited zero.

Container and volume: kokonut-kernel-recovery-logical. Image:
sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5.
Both the logical restore engine and raw source clone are stopped; volumes retained.
No host ports, application workers or indexers were enabled. Do not reuse the
populated destination for another restore. Preserve it for review or select another
fresh destination. Rollback is the unchanged original stack and retained ciphertext.

## Remaining acceptance gates

Globals are encrypted and preserved but were not applied: production role/grant
restoration needs a reviewed policy. The dumps deliberately omit ownership/grants.
Saved Metabase objects restored; their query results and dashboard display were not
exercised. Legacy migration inventory is retained, not upgraded to current Kernel.
No active scheduled leases or uploaded media exist in this source fixture, so
worker crash/restart and private-media recovery remain unproven. Broker counters
remain ambiguous; ClickHouse logical recovery and external ownership remain open.
No acceptance test suites ran. Batch 2 remains in progress with this scoped
populated-record restore item complete. Independent R2 backups remain deferred
per the user's local development scope.

### Batch 2 legacy authorization recovery — 10 October 2026

Read-only metadata from all four isolated source databases excludes password hashes.
One custom role (`kokonut`) is superuser with create-role/create-database,
replication and bypass-RLS privileges. No custom memberships, default ACLs or
row-security tables were found. Ownership and explicit object ACLs matched all
four logical restores. Main database schema ACLs initially differed because
no-privileges dumps omit grants. Rehearsed two explicit schema grants only on
the isolated logical restore; all selected main-database catalog fields then matched.
Both recovery clones stopped; original databases and encrypted globals unchanged.

[Inventory](builds/2026-10-10-recovery/legacy-authorization.json),
[before comparison](builds/2026-10-10-recovery/legacy-authorization-comparison.json),
[grant rehearsal](builds/2026-10-10-recovery/legacy-authorization-grants-rehearsal.json).
Recovery compatibility policy: create the recorded database owner under private
operator custody, restore no-owner/no-privileges archives, review source catalog
metadata, then apply only explicitly reviewed grants. Never replay encrypted
globals blindly or print their credentials. The isolated SQL fixture is not a
production migration and must not be added to ordered schema files.

Production policy remains open: separate migration/operator and runtime roles,
restrict privileges to actual service needs, and verify runtime denial of DDL,
role creation and unrelated databases alongside required domain workflows.
Legacy superuser parity does not satisfy that gate. Batch 2 remains active.
