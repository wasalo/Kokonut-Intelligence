# Local stack and preservation inventory

Observed 9 October 2026. Compose project: kokonut-intelligence.
Only metadata and aggregate counts were read; no secrets or record contents
were copied into these documents.

## Container state

Initial state: all nine existing containers stopped.
Database and ClickHouse were started for read-only inventory. Other services
remain stopped. No containers were recreated, seeded, migrated, or removed.

| Service | Initial state | Captured observation |
|---|---|---|
| database | Exited 0 | PostgreSQL 16.4; kokonut_intelligence is 107 MB |
| clickhouse | Exited 137 | kokonut_analytics exists but contains no tables |
| cache | Exited 0 | Redis contents and TTLs unmeasured |
| directus | Exited 0 | Metadata in PostgreSQL; uploads volume preserved |
| metabase | Exited 143 | Old container retained despite new opt-in Compose profile |
| gateway, grpc, caddy, mosquitto | Exited 0 | Runtime parity and mounted artifacts unvalidated |

An exit 137 alone does not establish the cause; do not label it as proven OOM.
The empty ClickHouse schema means this local stack cannot validate analytics
parity until its reference schema/data fixture is deliberately prepared.

## PostgreSQL baseline

schema_migration has 376 applied rows, including seeds. This is not a count
of source schema files. Recent applied identifiers include schema #352 and
seed 116. The checkout has schema files through #370: verify migration
status/checksums using services.migration before any schema change.
Neither ordering by apply time nor PostgreSQL statistics is a drift check.

Exact read-only counts:

| Table | Rows |
|---|---:|
| scheduled_task | 0 |
| task_run | 0 |
| platform_event | 4 |
| clickhouse_outbox | 0 |
| sensor_reading | 15 |
| weather_observation | 12 |
| wallet_activity_event | 15 |
| attestation_record | 4 |

There is no active local scheduled workload in scheduled_task. Events exist
and must be preserved. No event or indexer worker was started.
Chain cursors include kgp_indexer_cursor; inspect additional status tables
and configured external RPC sources before restarting indexers.

## Persistent storage owners

All eight named volumes were observed with Docker's local driver:

| Volume | Owner/data | Preservation requirement |
|---|---|---|
| kokonut-intelligence_postgres-data | Canonical records, Directus metadata, jobs/events, possible Metabase metadata DB | Full encrypted DB checkpoint and isolated restore; include all DBs used by services |
| kokonut-intelligence_directus-uploads | Private uploaded evidence | Copy encrypted files and preserve identifiers/access metadata |
| kokonut-intelligence_metabase-data | Legacy Metabase files | Retain even if PostgreSQL is current metadata backend; inspect contents before disposal |
| kokonut-intelligence_clickhouse-data | Analytics storage | Preserve; current expected DB empty, other storage remnants unmeasured |
| kokonut-intelligence_clickhouse-logs | ClickHouse diagnostic history | Retain through incident investigation/window |
| kokonut-intelligence_mosquitto-data | Broker persistence | Inspect buffered messages before transport cutover |
| kokonut-intelligence_caddy-data | Certificates/proxy state | Preserve or reprovision before HTTPS/mobile cutover |
| kokonut-intelligence_caddy-config | Proxy runtime state | Retain alongside source config |

Bind mounts also include extensions/, config/caddy certificate material,
Mosquitto cert/ACL/config files, and mobile/maps assets. Do not expose their
secret contents in inventory output.

## Unmeasured state and gates

- Upload/broker/BI volume sizes, Metabase metadata database existence/content,
  Redis sessions/keys, and Prefect server/run history are not validated.
  There is no Prefect service in the base Compose file; external Prefect
  configuration is still possible.
- Backup encryption recipient/tool availability and a successful isolated
  restore have not been demonstrated. No existing production volume may be
  deleted before that gate closes.
- PostgreSQL migration drift/backlog remains to be reconciled. Do not apply
  seed.sh blindly: it touches both SQL stacks and may seed recurring work.
- Full capability tests have not been executed in this baseline slice.
- ARM64 manifest availability and actual Pi performance remain unverified.

The local Docker stack is approved for subsequent implementation work. These
gaps are provider removal/cutover gates; they do not prevent additive Phase 1
development against source fixtures.

## 10 October follow-up

All nine legacy containers are stopped. Read-only volume measurements and two
previously omitted anonymous storage owners are recorded in
[Batch 2 recovery preparation](recovery-preparation.md). Redis persistence and
broker files exist; their logical contents remain unassessed. Empty local uploads
and Metabase mounts do not establish absence of external media or metadata DBs.

### Batch 2 legacy preservation — 10 October 2026

All ten locally attached legacy volumes and selected configuration captured in
a finalized age-encrypted archive; source containers remained stopped. Sizes and
image/volume mappings retained. External-setting presence inspected without values;
no configured Prefect/mobile storage settings found in the inspected local scope.
[Preservation scope and restore procedure](legacy-storage-preservation.md). Logical provider
state and populated job/media recovery remain open; no capability acceptance closed.
User deferred independent R2 production backups and authorized a local development
mirror under backups/development-mirror/. Same-disk copies are not independent
production protection. Running Kernel services unchanged; no test suites ran.

### Batch 2 provider clone inventory — 10 October 2026

Isolated copied Redis/PostgreSQL engines loaded successfully: Redis has four string
keys without expiry; Metabase contains 39 cards and one dashboard. Four PostgreSQL
databases and globals captured into age-encrypted logical archives, with matching
development mirror checksums. Broker clone counters are ambiguous/anomalous and
do not certify application backlog. [Evidence and limits](provider-clone-inventory.md).
All clones stopped; original legacy services/storage unchanged. No test suites ran.
Batch 2 remains open for populated recovery, provider semantics and logical archive
restore. No capability acceptance counts changed.

### Batch 2 populated legacy database restore — 10 October 2026

All four legacy logical archives restored into fresh isolated databases on the
compatible recorded image. Counts and whole-row comparison fingerprints match for
13 selected tables, including populated events, sensors, weather, wallets,
attestations and Metabase cards/dashboard. [Restore evidence](legacy-logical-restore.md).
Both recovery engines stopped and volumes retained. Original legacy and running
Kernel deployments unchanged. Globals/grants were not applied; no active workload
or uploaded media exists in the selected source. Batch 2 remains open for those
recovery gates, broker/ClickHouse and external ownership. No acceptance suites ran
and no complete capability acceptance counts changed.

### Batch 2 analytics and broker inventory — 10 October 2026

Compatible isolated ClickHouse copy loaded: 34 analytics objects in default, zero
active non-system rows/parts, expected kokonut_analytics empty. Schema definitions
encrypted and mirrored; complete object metadata retained. Original broker file
scanned offline: version 6, one configuration chunk, zero message/client/subscription
chunks. [Evidence and limits](analytics-broker-recovery.md). Original services remain stopped;
ClickHouse clone stopped with volume retained. No acceptance suites ran. Full
analytics output/restore and transport recovery remain open; capability counts
unchanged. Redis semantics, active work/private media and permissions still pending.
