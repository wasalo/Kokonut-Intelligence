# Batch 2 — isolated provider inventory

10 October 2026. Original legacy services stayed stopped. New Redis, PostgreSQL
and Mosquitto volumes were created from read-only source mounts. Compatible pinned
engines ran with network mode none, no host ports and no application workers.
All three clones are now stopped and their recovery volumes retained.

## Observed state

| Provider | Aggregate observation | Remaining gate |
| --- | --- | --- |
| Redis | RDB loaded four string keys in DB 0; no expiry keys; 16 DBs configured; no AOF; zero keys expired at load | Semantic key/session ownership and historical in-memory state; expiry behavior acceptance |
| Legacy PostgreSQL | Four databases, including Metabase and a bootstrap DB; 376 migration rows; four events, fifteen sensor readings, four attestations; no scheduled tasks/runs/uploads | Legacy drift reconciliation, populated recovery and grant/role parity |
| Metabase | 39 saved cards, one dashboard, one user, zero sessions | Kokonut-specific dashboard/output parity and analytics ownership |
| Mosquitto | Copied persistence loads; SYS stored/retained counters 55; inactive counter 4,294,967,295 | Offline persisted-message decoding; anomalous counter and SYS-generated messages prevent buffered-message certification |

Only aggregate results were read. No Redis keys/values, Metabase query contents,
sensor payloads, private account records or role passwords were printed. Broker
subscription observations alter clone client/system state only. Raw clone counters
are not a count of the original application message backlog.

## Logical checkpoint and evidence

Encrypted custom-format pg_dump archives now cover kokonut_intelligence, metabase,
kokonut_bootstrap_28232 and postgres. Encrypted globals capture cluster roles.
Private files: backups/legacy-logical-batch2-20261010/; local development mirror:
backups/development-mirror/legacy-logical-batch2-20261010/. All five ciphertext
checksums matched after copying. At the time of this original inventory, a
logical archive restore had not yet been performed; later restore evidence is
recorded below and in `legacy-logical-restore.md`.

- [Provider aggregates](builds/2026-10-10-recovery/provider-logical-inventory.json)
- [Logical archive manifest](builds/2026-10-10-recovery/legacy-logical-manifest.json)
- [Mirror comparison](builds/2026-10-10-recovery/legacy-logical-mirror.json)

For a future capture, scripts/kernel-legacy-logical-checkpoint.sh discovers all
non-template databases on the running no-network recovery clone, encrypts each
dump and globals, refuses identifier/path reuse, and records hashes. Shell syntax
passed; the archives above were captured using the equivalent explicit command
sequence before this wrapper was added. No acceptance test suites ran.

## Restart, restore and rollback

Retained clone names are kokonut-kernel-recovery-redis,
kokonut-kernel-recovery-legacy-postgres and kokonut-kernel-recovery-broker;
volumes use the same names. Start clones only for scoped inventory. Broker clone
uses the temporary /tmp/kokonut-recovery-mosquitto.conf; reconstruct that disposable
configuration before restart if removed. Redis clone persistence writes were
disabled; PostgreSQL/Mosquitto may perform recovery or shutdown writes to clones.
Never attach their writable copies to legacy containers or treat them as originals.

Restore logical dumps into a new compatible engine, not the existing populated
recovery clone. Provision separate empty databases for all archived DBs. Review
globals privately before applying: they may contain credentials or duplicate roles.
Database dumps omit grants/ownership; production permissions need explicit restore
policy. Use age streaming decryption and pg_restore --single-transaction
--exit-on-error; no --clean on an occupied database. Preserve failures privately.

Original volumes remain unchanged. No default deployment or migration was cut over.
Batch 2 remains open for broker/ClickHouse logical assessment, populated work/media
recovery and external ownership reconciliation. R2 production backups are deferred
by user instruction; a same-disk mirror closes only local development copying.

### Batch 2 Redis ownership assessment — 10 October 2026

Inspected the retained no-network Redis clone without printing key identities or
values. Four db0 string keys have no Redis expiry. Three are source-mapped against
the exact retained Directus image: two API request telemetry counters and one
collaboration instance registry. These are not evidence of governed domain state
or queued jobs. One opaque key remains unclassified; retain the encrypted RDB and
original volume, and leave Redis retirement blocked pending its ownership review.

[Sanitized evidence](builds/2026-10-10-recovery/redis-ownership.json).
Pinned source paths: `middleware/request-counter.js`,
`telemetry/counter/use-counters.js`, `websocket/collab/messenger.js`,
`websocket/collab/store.js`, `utils/store.js` in the retained Directus image.
Telemetry counters stay archived; they must not become native rate-limit state.
Collaboration presence is runtime state: archive it, reconnect clients and recreate
instance identity when restoring the optional adapter. Do not import stale
presence into Kernel domain tables. No Redis keys deleted or rewritten; clone stopped.

Kernel computation cache remains PostgreSQL-backed (`services/cache/cache.py`),
and native gateway rate-limit state has its own provider boundary and PostgreSQL
schema. Directus Redis settings remain optional-adapter concerns; clustered Directus
cache/collaboration/limit behavior still needs adapter acceptance before changing
its deployment. Source mapping is not live Redis-free Directus certification.
Batch 2 remains active; no capability promoted to fully accepted.

### Batch 2 final Redis key mapped — 10 October 2026

All four retained db0 keys now have source-backed owners. The remaining `rlflx`
namespace is the pinned rate-limiter-flexible default. Directus authentication
constructs a limiter with `duration: 0` and consumes by `user.id`; privately matched
the retained UUID to `directus_users` in the isolated legacy PostgreSQL clone.
Only a boolean match is retained, with hashed key identity; no UUID or counter
value is published. This is a persistent failed-login counter, not disposable
cache or native gateway rate-limit state. No source keys/grants/data modified.
Both recovery clones stopped after inspection.

[Updated evidence](builds/2026-10-10-recovery/redis-ownership.json).
Redis ownership inventory is complete for the retained local snapshot. Retirement
remains open: optional Directus must preserve this security counter in compatible
Redis state, or use an explicitly reviewed transfer/reset policy with login lockout
acceptance checks. Native gateway token buckets do not replace failed-login policy.
Do not clear Redis wholesale or promote a Redis-free Directus deployment based
on the telemetry/presence classifications. Original volume and encrypted archives
remain the rollback source. Live lockout behavior and provider parity remain open.
Batch 2 stays active; no capability fully accepted.

### Optional database consumer-role recovery — 11 October 2026

A fresh internal-only project restored the encrypted `kokonut_intelligence` and
`metabase` archives. The Directus DML role passed synthetic DML/sequence checks
and DDL/admin/database denials; the non-superuser Metabase role owned its
metadata database and 290 application relations; and the analytics-source role
could query one synthetic curated view while application relations remained
unreadable. All three roles were non-superusers with no role memberships. The
pinned Directus bootstrap completed and its DML-only runtime became healthy.
Metabase first-start migrations also completed against a separate empty
metadata database, and its health endpoint returned 200. Saved-card/dashboard
and real source parity remain open.

[Policy and remaining gates](optional-database-roles.md) ·
[Sanitized role evidence](builds/2026-10-11-recovery/optional-consumer-db-roles.json) ·
[Product startup evidence](builds/2026-10-11-recovery/optional-consumer-startup.json)

### Metabase source inventory — 11 October 2026

The restored Metabase metadata has 39 saved cards and one dashboard. All cards
and all 22 dashboard placements reference its only registered source, a source
flagged as the sample H2 database; host and database name are unset, with no
nonempty password value. No PostgreSQL or ClickHouse source appears in the metadata. The
inventory printed no connection values, names, card definitions, or SQL and
executed no cards. It does not establish result parity or sample-data
availability. [Report](metabase-source-inventory.md) ·
[machine evidence](builds/2026-10-11-recovery/metabase-source-inventory.json).

### Populated Metabase startup — 11 October 2026

Pinned Metabase 0.62.4 started healthy against a fresh populated metadata
restore using the non-superuser application role. The health endpoint returned
200. Post-startup saved-content counts matched the earlier inventory of the
same encrypted metadata archive: 39 cards, one dashboard, 22 dashboard
placements, and one user. All cards still referenced
the sample H2 source. No saved definitions or SQL were read or executed. The
fresh project was stopped and removed with its named volume retained.
Candidate containers remained healthy and legacy services stayed stopped.
[Evidence](builds/2026-10-11-recovery/metabase-populated-startup.json).

### Metabase saved-content review — 11 October 2026

A separate fresh Metabase-only metadata restore was inventoried structurally.
The board is titled **E-commerce Insights** and contains 22 placements drawn
from 39 cards over the sample H2 source. Titles and source-table categories
cover orders, products, subscriptions, checkout, revenue, and survey examples;
the cards span 19 visualization types. The inventory emitted no SQL,
connection values, filter values, or domain rows and did not execute cards.
This is generic demo content, not a Kokonut dashboard or parity fixture.

Disposition: retain only as an explicitly labeled demo/compatibility fixture.
Build Kokonut-specific cards against reviewed published views after agreeing
measures and reference outputs. A separate exploratory application-database
restore attempt hit a PostGIS duplicate-extension catalog error; that unused
database was reset empty. The Metabase-only inventory succeeded, and the
candidate and stopped legacy deployment were not touched. [Report](metabase-source-inventory.md) ·
[sanitized evidence](builds/2026-10-11-recovery/metabase-content-inventory.json).
