# Opt-in PostgreSQL gateway rate limits

Migration 373 adds `gateway_rate_bucket`, keyed by SHA-256 of the existing
bounded caller identity, with token balance and database timestamps. No raw
credential is stored. The adapter uses the same fixed default policy as local:
capacity 100 and refill 10 tokens/second. Row locks serialize consumption across
API processes; clock_timestamp is read after acquiring the lock. Negative clock
movement contributes zero refill. Updated balance commits before returning.

The standard Kernel Compose overlay defaults to `KOKONUT_RATE_LIMIT_PROVIDER=postgres`.
Apply migration 373 through the checksummed runner before exposing API traffic.
Minimal and edge remain on the process-local provider by default; other shared
deployments must select `postgres` explicitly. Redis remains unnecessary for
Kernel rate limiting. Unsupported settings still fail startup. Worker processes
do not need a rate-limit provider.
No migration was applied and no running deployment selected this adapter.

Each check/retry calculation uses a shared connection context, a two-second lock
timeout and a three-second statement timeout. Retry calculation observes/refills
without consuming tokens. Storage errors propagate; the factory never downgrades
to process-local state. At present those errors can become gateway server errors
without the normal denied-request audit path: an explicit audited availability
response remains further work. No request reaches its route through a failed
check. Connection establishment also needs its existing connection timeout
review; SQL timeouts alone do not bound all network or response time.

The subsequent gateway integration below supersedes the raw server-error and
direct event-loop limiter behavior described in this initial implementation.

This synchronous adapter blocks the gateway event loop during database I/O.
An async/thread-offload review is required before production use. Caller rows
are indexed by update time but not automatically expired or globally bounded;
define retention, identity-abuse controls, and reviewed cleanup before scale.
The rate table is operational throttle state, not lifecycle or permission data.
Database restore/reset can replenish budgets and needs an explicit policy.

Static lint and diff checks passed. No tests, requests, bucket rows, connections,
images, or containers were run. Pending acceptance: migration/rollback, concurrent
same-caller consumption, different-caller isolation, shared replica budgets,
retry calculations, clock movement, lock/storage outages, audit behavior, bounded
connection I/O, retention, event-loop latency, and default local parity. Scale
selection remains rejected because this adapter alone does not certify scale.

Rollback requires an explicit local-provider switch and API recreation after
reviewing its per-process limits. Stop redundant API replicas if a shared budget
is required. Retain the additive table/migration and operational history; do not
silently change providers on database failure or remove applied migration files.

## Gateway availability integration

Gateway checks and retry calculations now run through Starlette's thread pool
for both local and PostgreSQL adapters. Local locking supports the new threaded
invocation. The request waits for the outcome before authorization/route dispatch;
there is no background permission decision or timeout-based allow path.

An exception from either limiter operation returns 503 with Retry-After 30 and
generic response text. It attempts the existing denied audit with reason
`rate_limit_unavailable`, and logs only the backend exception type at this new
boundary. It never falls back to another provider. Normal exhausted budgets
retain 429 and their computed retry interval. Existing OPTIONS bypass is
unchanged. A backend may consume a token before a response becomes uncertain;
the gateway does not refund it automatically.

Offloading keeps limiter I/O off the event loop, but does not bound database
connection establishment, thread-pool queue time, total request concurrency, or
synchronous existing gateway authentication/audit work. Durable audit can fail
during the same database outage; existing audit logs make that failure visible
but cannot promise persisted denial evidence. Those are remaining availability
acceptance requirements, not claims resolved by this integration.

Static lint and diff checks passed. No tests, requests, database operations,
images, or containers were run. Pending checks: backend check/retry exceptions,
503/429 headers, denied audit metadata, no route dispatch on failure, local
threaded parity, pool saturation/cancellation, database timeout behavior, and
audit failure during storage outage. Migration 373 remains unapplied and the
running candidate remains on its previous source image.

## Connection establishment safeguard

The shared database factory now accepts optional positive integer
`connect_timeout` seconds, forwarded to psycopg2. `DatabaseConnection` and
`get_connection` propagate the explicit option; an already supplied connection
cannot receive a connection-establishment setting. Existing callers omitting
the option retain their previous factory behavior.

The PostgreSQL limiter now requests `connect_timeout=3` for each operation,
alongside its existing statement and lock limits. This closes the previously
unconfigured connection-establishment setting for this adapter. It does not
constitute a total request deadline: name resolution, multiple addresses,
thread-pool waiting, transaction cleanup, and separate audit work need runtime
review. No background thread is forcibly cancelled or allowed to return an
authorization result after a fabricated timeout.

Static lint and diff checks passed. No tests, database connections, requests,
images, or containers were run. Pending acceptance includes timeout forwarding,
invalid values, existing-connection rejection, unavailable/unreachable hosts,
default factory compatibility, and observed end-to-end outage response time.
Migration 373 is still unapplied. Rollback can omit the explicit timeout without
changing persisted state, but requires renewed outage-latency review.

## Explicit idle-bucket maintenance

`python3 -m services.gateway.rate_limit_cli --cleanup --limit 1000` now deletes
one page of buckets idle for more than 24 hours. The command is documented, not
executed. It requires migration 373 and operator database access. Limits must
be 1–1000; idle age is fixed rather than allowing an operator to accidentally
delete depleted active budgets by choosing a short age.

Candidates are ordered by update time and hash, locked with FOR UPDATE SKIP
LOCKED, and deleted in one transaction. An in-use bucket lock is skipped.
After 24 idle hours the fixed 100-token/10-per-second policy would already have
fully replenished the bucket, so a subsequent recreation retains that idle
policy outcome. Requests queued behind cleanup may create a fresh full bucket;
the preceding idle budget was already eligible for full refill. No business
data, credential, permission, or durable audit row is deleted.

Cleanup uses the same three-second connection/statement and two-second lock
settings and shared transaction cleanup. Output reports counts only, not caller
identities. No recurring job, scheduler permission, API route, or automatic
deletion is configured. This maintenance option is not a hard cardinality cap:
active identity churn can still grow the table and requires measured sizing,
monitoring, and identity-abuse controls before scale certification.

Static lint and diff checks passed. No tests, cleanup commands, bucket deletion,
migrations, images, or container changes were run. Pending acceptance includes
idle boundary, recent/locked bucket preservation, concurrent check/cleanup,
page bounds, rollback on SQL failure, and post-cleanup refill behavior. Rollback
removes the maintenance entry point without altering migration history; deleted
idle throttle rows are recreated under the documented fixed refill policy.

## Current candidate runtime status — 10 October 2026

The candidate app was rebuilt and promoted with `KOKONUT_RATE_LIMIT_PROVIDER=local`.
The deployed local path now has loopback evidence for throttling, `Retry-After`,
CORS/preflight ordering, and persisted denial audit. The PostgreSQL adapter in
this document remains source-only and unselected in the candidate. Migration
373 was not applied to the candidate database; it remains applied only to the
separate portability deployment. No candidate `gateway_rate_bucket` rows were
created. The shared-provider concurrency, outage, retention, and multi-replica
gates remain open. [Runtime evidence and rollback](gateway-rate-limit-runtime.json).

## Portability shared-consumption check — 11 October 2026

Started only the existing private portability PostgreSQL container. Its
migration-373 `gateway_rate_bucket` table existed and was empty. A one-off
portability app container explicitly selected `PostgresRateLimiter`; it was
removed after the check. The first serial request consumed a 100-token bucket,
a second 100-token request was denied, and `retry_after(..., 100)` returned 10.
A different caller consumed its independent 100-token bucket.

For a new caller, 140 requests were distributed across two limiter instances
and 16 threads. The database allowed 121 and denied 19 over 2.193 seconds. That
fits the 100-token capacity plus 10 tokens/second refill (with a five-token
measurement tolerance). The three synthetic bucket rows were deleted and a
read-only count confirmed the table was empty. The portability database was
stopped afterward with its original container and named volume intact. The
candidate database/app were not used. [Evidence](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json).

This exercises shared row-lock consumption across concurrent connections and
separate adapter instances against one database. It does not certify separate
OS processes/API replicas, lock or storage outages, gateway 503/audit behavior,
retention under identity churn, or candidate activation. No schema migration,
domain write, audit row, or pytest suite ran.

## Unreachable-database gateway behavior — 11 October 2026

A disposable container from the candidate app image ran with Docker networking
disabled, explicit KOKONUT_RATE_LIMIT_PROVIDER=postgres, and the database
target set to closed loopback port 1. A source-level ASGI GET /health selected
PostgresRateLimiter; its connection attempt raised OperationalError, and the
gateway returned 503 with Retry-After: 30 and the generic unavailable response.
The middleware invoked one denied audit callback with status 503 and reason
rate_limit_unavailable. The callback was captured in memory because PostgreSQL
was intentionally unreachable. No local limiter fallback occurred.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-outage.json).

This confirms only the immediate connection-failure response and attempted audit
callback. It does not verify durable audit persistence, PostgreSQL lock-timeout
behavior, real API process/replica limits, or candidate provider activation.
The candidate remains on the local provider. No database, schema, audit or domain
writes occurred, and no pytest suite ran. No rollback was needed because no
configuration or running service changed.

## PostgreSQL limiter lock timeout — 11 October 2026

The isolated migration-373 portability database had zero bucket rows before
the probe. A one-off app container held a synthetic bucket row with
SELECT FOR UPDATE on one connection while PostgresRateLimiter.check ran on a
separate connection. The adapter returned LockNotAvailable (SQLSTATE 55P03)
after 2.124 seconds, consistent with its configured two-second lock timeout
and before the three-second statement timeout. The one temporary bucket row was
deleted and a read-only count confirmed zero rows afterward.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json).

The one-off app was removed and the portability PostgreSQL container was
stopped, restoring its previous state. The candidate was not used. This verifies
the adapter's database lock boundary, not HTTP behavior for this specific
exception or durable outage audit. No migrations, domain/audit writes, or pytest
suite ran; no rollback beyond cleanup and stopping the database was needed.

## Shared limiter across OS processes — 11 October 2026

Four separate Python OS processes in a one-off portability app container
issued 160 direct PostgresRateLimiter checks for one synthetic caller. The
migration-373 database allowed 114 and denied 46 over 1.653 seconds, within the
capacity/refill upper bound of 121. The bucket table was empty before the run;
the one synthetic bucket was deleted and the table returned to zero rows.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json).

The one-off app was removed and the portability database stopped, restoring its
previous state. The candidate was not used. This validates shared adapter state
across OS processes, not HTTP request traffic through separate API containers
or replicas. Durable audit during database outages remains open. No migrations,
domain/audit writes, or pytest suite ran.

## Real gateway audit behavior during PostgreSQL outage — 11 October 2026

A network-disabled disposable container selected PostgresRateLimiter and sent a
source-level ASGI GET /health with PostgreSQL pointed at a closed loopback port.
The real GatewayAudit.log path then attempted a PostgreSQL connection, logged
OperationalError, and returned control to the middleware. The gateway response
completed as 503 with Retry-After: 30. No durable denial audit row was possible
while PostgreSQL was unavailable. The test captured the failure log in memory
and made no database writes.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json).

This confirms visible audit-write failure handling and the response boundary,
not durable audit availability. Audit replay/reconciliation after the database
returns remains open; private-network HTTP sharing across two API containers
was verified in the later check below.
The active candidate remains on the local limiter. No code or runtime config
changed; no rollback was needed.

## Gateway middleware across OS processes — 11 October 2026

Four gateway ASGI app instances in four OS processes shared the PostgreSQL
limiter. Across 160 GET /health requests for one synthetic loopback identity,
121 returned 200 and 39 returned 429 with Retry-After; the result was within
the refill-aware upper bound of 140 over 3.527 seconds. GatewayAudit.log was a
no-op in each process so no durable audit rows were written. The one limiter row
was deleted and the table returned to zero rows.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json).

The one-off app was removed and the portability database stopped; the candidate
was untouched. This verifies shared PostgreSQL limiter behavior through
middleware in separate processes, not network HTTP across separate API
containers or production replicas. No migrations, domain writes, or pytest
suite ran.

## Network HTTP across two API containers — 11 October 2026

Two separate gateway API containers in the isolated portability Compose network
selected PostgresRateLimiter and shared the migration-373 database. A third
container sent 160 GET /health requests, alternating between the APIs. The same
synthetic client identity reached both. Responses were 119×200 and 41×429 with
Retry-After; the 119 allows were within the refill-aware upper bound of 126
over 2.142 seconds. GatewayAudit.log was disabled in both API containers to
avoid durable audit writes in this limiter-only probe.

The Docker image healthcheck had created one expected loopback limiter bucket
before the probe; it was identified by a hash-only aggregate check and removed.
After the HTTP burst, the request bucket was deleted and the table returned to
zero rows. Both API containers were removed and the portability database was
stopped. The candidate was untouched.
[Sanitized evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json).

This validates private-network HTTP sharing across two API containers, not
public ingress, multi-host routing, container failure/restart, or production
scale. Audit recovery after database restoration remains open. No migration,
domain write, or pytest suite ran.

## Gateway audit outage and PostgreSQL recovery — 11 October 2026

In the isolated portability stack, the database was stopped while a synthetic
GatewayAudit event was submitted. The real writer logged OperationalError and
returned without persisting the event. After PostgreSQL restarted and passed its
health check, a new synthetic audit event persisted normally. An aggregate query
found zero rows for the outage path and one row for the post-recovery control
path. That exact synthetic control row was deleted, and a follow-up query found
zero rows for its caller/resource pair.

This confirmed forward writes recover when PostgreSQL returns, but the probe
did not replay outage events. That is the pre-journal baseline and is superseded
by the bounded replay implementation below. The temporary app was removed and
the portability database returned to its prior stopped state; the active
candidate was untouched. No migration, domain write, or pytest suite ran.
[Sanitized evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).

## Bounded local audit journal and startup replay — 11 October 2026

The earlier outage result is historical and has been superseded in current
source by the bounded SQLite journal. A real ASGI request during PostgreSQL
outage returned 503 with `Retry-After: 30`; its denied event was queued. After
the app container was replaced with the journal volume retained and PostgreSQL
restored, the FastAPI startup worker committed the event exactly once, retained
its original `created_at`, and drained the queue. The canonical PostgreSQL
table remains the audit source of truth; no migration was needed because the
existing primary key stores the stable event UUID.

See the [journal contract, configuration, and remaining limits](gateway-audit-spool.md)
and [sanitized recovery evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).
This is partial audit recovery evidence: saturation/volume loss, backup/restore,
candidate activation, production ingress, and multi-replica failover/scale
remain open. The candidate provider remains local.

The bounded maintenance CLI now supports read-only status/integrity checks,
SQLite online checkpoints, and restore copies to new paths. Abrupt-process-exit,
checkpoint consistency while the source changed, restored identity, file modes,
and no-overwrite behavior passed in a synthetic local fixture. This did not
exercise Compose-volume installation, hardware failure, or encrypted backup
transfer. [Recovery record](builds/2026-10-11-recovery/gateway-audit-spool-backup-restore.json).
