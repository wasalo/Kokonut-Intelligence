# Gateway rate-limit provider boundary

`RateLimitBackend` defines the two operations used by gateway middleware:
`check(caller, tokens_needed=1)` decides/consumes tokens, and
`retry_after(caller, tokens_needed=1)` supplies whole seconds for Retry-After.
`create_app(rate_limiter=...)` accepts an explicitly owned backend; otherwise
`get_rate_limiter()` selects the configured implementation at application startup.
Dependency injection does not change request identity, authorization, audit,
route policy, or public-route selection.

## Kernel deployment-profile defaults

The minimal candidate and edge profile default to `KOKONUT_RATE_LIMIT_PROVIDER=local`.
They run one API process on one host, so the bounded in-memory token bucket
keeps Redis out of the smallest deployment. Restart resets its buckets; this is
acceptable only for a single-instance deployment where shared limits are not a
requirement.

The standard profile defaults to `KOKONUT_RATE_LIMIT_PROVIDER=postgres`. This
shares the budget across API processes and containers and survives app restarts.
Migration 373 must be applied before the gateway serves traffic. The profile
can be explicitly overridden for a reviewed deployment shape; horizontal or
multi-host API replicas must use a shared provider. Existing direct and ASGI
multi-process checks plus the two-container private HTTP check exercised shared
consumption. Multi-host failover, public ingress, and production scale remain
open.

Kernel operator sessions and computation-result cache entries are stored in
PostgreSQL. The cache table (`cache_entry`) is durable computation metadata,
not an HTTP session or authorization store. Redis is used only when the optional
legacy Directus service is selected for its cache/rate-limit adapters; no Redis
service is present in the Kernel candidate profiles.

The subsequent [PostgreSQL adapter](postgres-rate-limits.md) implements explicit
`postgres` selection in source with migration 373; the original local-only
factory description below records the earlier slice. Migration, availability,
retention, and scale acceptance remain pending.

`KOKONUT_RATE_LIMIT_PROVIDER` defaults to `local` in the provider factory and
minimal candidate Compose file. The factory rejects every unsupported value
rather than silently falling back. The standard Compose overlay overrides the
default to `postgres`; the active minimal candidate remains local. PostgreSQL is
not enabled in the candidate deployment, and scale selection remains unavailable.
Redis is not required by any Kernel profile. A backend requiring shutdown
resources will need an explicit ASGI lifespan contract before adoption.

The existing local implementation remains a 100-token bucket, 10-token/second
refill, and at most 10,000 caller buckets. It is process-local, resets on restart,
and evicts the oldest caller bucket when capacity is reached. It offers no
distributed budget or durable rate-limit history. The gateway offloads limiter
checks and retry calculations to Starlette's thread pool; the local reentrant
lock protects concurrent calls in a process. This does not bound database
connection time, thread-pool queue time, or total concurrency.

Behind the current proxy boundary, socket-peer IP identifies unauthenticated
callers; credentials retain the existing hashed identity. Limits never grant
permission or replace capability/device verification. Standalone HTTP sensor
ingress does not use this gateway limiter and is not made public by this change.

Future shared adapters must consume atomically across replicas, bound caller
storage, define expiry, avoid credentials in keys, use a consistent clock,
specify storage-outage fail-closed behavior, and preserve denied-request audit
and retry headers. Synchronous shared operations must have bounded I/O and an
event-loop performance review before use. No shared provider is certified by
the interface alone.

Static lint, placeholder Compose parsing, and diff checks passed at the source
boundary stage. The candidate image at that point predates this boundary and
requires rebuilding; the later deployed runtime check below supersedes that
image-status note. Remaining gates include unsupported-setting startup failure,
injected backend selection, restart/eviction behavior, identity isolation,
concurrency, and shared-provider failure behavior.

Rollback restores direct local construction with the existing local semantics.
No business data or persisted limit state needs migration. Never substitute a
local limiter silently during shared-provider failure or use its cache presence
as proof of authorization.

## Local adapter validation and synchronization

The local limiter now requires positive integer bucket/caller capacities and a
finite positive refill rate. It rejects boolean capacities/rates, empty or
non-string caller identities, identities longer than 255 characters, and
nonpositive/noninteger token requests. Requests exceeding bucket capacity fail
explicitly because they can never refill to a satisfiable amount. The gateway's
existing bounded hashed/IP identities and one-token request remain compatible.

A per-instance reentrant lock now protects bucket creation/eviction, refill and
consumption, retry calculations, and status snapshots. This provides a local
synchronization boundary for threaded callers without changing default bucket
sizes, restart semantics, oldest-caller eviction, or authorization policy.
It does not share state across processes or replicas. The private bucket helper
is an internal operation whose callers must hold the lock.

Static lint and diff checks passed; no tests, requests, images, or containers
were run during the local adapter source review. The deployed local runtime
check below covers default gateway throttling, retry headers, CORS preflight,
and durable audit. A subsequent isolated contract check covers concurrent
consumption, least-recently-used caller eviction, and fresh-instance reset.
Retry/status snapshots under concurrency and live service-process restart
behavior remain open. These guards change previously permissive direct API
usage, so review any custom callers before adoption.

## Deployed local-provider runtime — 10 October 2026

The rebuilt candidate app uses `KOKONUT_RATE_LIMIT_PROVIDER=local`. A loopback
canary with the source defaults (100-token capacity, 10-token/second refill)
returned 429 with `Retry-After: 1` and the configured CORS header after a bounded
request burst. Configured-origin OPTIONS preflight passed after exhaustion and
the next GET was denied. An exact read-only audit query confirmed 127 allowed
and two `rate_limited` denied rows for the accepted probe. The rebuilt image is
now active and healthy in the candidate project. [Full evidence and rollback](builds/2026-10-10-recovery/gateway-rate-limit-runtime.json).

This does not certify the PostgreSQL shared adapter. Migration 373 remains
applied only to the separate portability database; the candidate did not apply
it or write gateway rate-bucket rows. The promoted image later passed an
isolated local contract check for concurrent token consumption and LRU caller
eviction; a separate check also confirmed that the same local caller receives a
fresh budget in a new Python OS process in the same disposable container.
[Contract evidence](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json)
and [process reset evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json).
The active gateway service/container was not restarted. Multi-replica budgets,
actual gateway service restart behavior, and shared-provider outage behavior
remain open.

## Isolated local limiter contract — 11 October 2026

Using the promoted app image in a disposable container with networking disabled
and no mounts, 100 concurrent checks from 32 threads against a capacity-five
bucket admitted exactly five and denied 95. A two-caller-capacity sequence
confirmed the least-recently-used caller was evicted while the refreshed caller
kept its exhausted bucket. Reconstructing a limiter instance gave the same
caller a fresh bucket, confirming the process-local reset model.

This did not contact the active candidate, PostgreSQL, or any replica. A
separate process-boundary check confirmed that state is lost when one Python
process exits and a new one selects the local provider; it did not restart the
gateway ASGI service or Compose container. The PostgreSQL backend, shared
cross-process budgets, and live service restart behavior remain unaccepted.
See the [sanitized evidence](builds/2026-10-11-recovery/gateway-rate-limit-local-contract.json)
and [process reset evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json).

## Local provider process-boundary check — 11 October 2026

Two Python OS processes ran sequentially in one disposable container with
networking disabled and `KOKONUT_RATE_LIMIT_PROVIDER=local`. The first used the
default capacity of 100, exhausted the same caller bucket (100 allowed, one
denied), and exited. The second selected a new local backend and admitted one
request for the same identity. This confirms state is process-local across
process exit/start. It does not exercise restarting the candidate gateway
service or its container. [Sanitized evidence](builds/2026-10-11-recovery/gateway-rate-limit-process-reset.json).

## Candidate gateway restart acceptance — 11 October 2026

The active candidate app was exercised through its internal loopback using one
synthetic credential identity. A bounded health burst produced 123 allowed
responses then one 429 with `Retry-After: 1`; the app container was restarted
in place. Its container ID and image stayed the same, its process ID and start
time changed, and Docker health returned to `healthy`. The same identity then
received 200, confirming the process-local bucket reset in the candidate
service. The PostgreSQL container ID/start time remained unchanged. A read-only
audit query returned 124 allowed and one `rate_limited` denial; all 125
synthetic audit records were retained. [Evidence](builds/2026-10-11-recovery/gateway-rate-limit-app-restart.json).

This accepts the local rate-limit reset on one candidate gateway restart. It
does not certify Caddy/host ingress, PostgreSQL shared limits, multi-replica
state, or production restart behavior. No domain writes or schema migrations
occurred.

## PostgreSQL shared-consumption check — 11 October 2026

Using the separate portability database with migration 373 already applied,
the direct `PostgresRateLimiter` check confirmed a 100-token consume, denial
when asking for another full bucket, a 10-second retry estimate, and an
independent full bucket for a different caller. Across two backend instances
and 16 threads, 140 same-caller checks produced 121 allows and 19 denials in
2.193 seconds, within the refill-aware upper bound. Three synthetic rate-bucket
rows were deleted and the table returned to zero rows. The portability
database was stopped afterward; the candidate was untouched. [Evidence](builds/2026-10-11-recovery/postgres-rate-limiter-concurrency.json).

This is one-database concurrent-connection evidence, not a multi-process API
replica or outage acceptance. PostgreSQL failure/timeout behavior and the
gateway's 503 and audit behavior remain open; the candidate continues to select
the local provider.

## PostgreSQL outage response boundary — 11 October 2026

With explicit PostgreSQL selection and a network-disabled disposable container
pointed at a closed loopback port, an in-process ASGI request selected
PostgresRateLimiter and returned 503 with Retry-After: 30. The gateway
attempted one denied audit callback carrying rate_limit_unavailable; the probe
captured it in memory and confirmed there was no local-provider fallback.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-outage.json).

This does not establish durable audit during database failure, lock-timeout
behavior, or multi-process/replica behavior. PostgreSQL remains opt-in and the
active candidate stays local. No running service or durable state changed.

## PostgreSQL row-lock timeout — 11 October 2026

In the isolated migration-373 database, one connection held a synthetic
bucket row lock while a second connection called PostgresRateLimiter.check.
The call raised LockNotAvailable with SQLSTATE 55P03 after 2.124 seconds,
consistent with the configured two-second lock_timeout and three-second
statement_timeout. The single synthetic row was deleted; the table returned to
zero rows. The database was stopped afterward and the candidate was untouched.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-lock-timeout.json).

This verifies the adapter-level lock timeout only. HTTP mapping for this
specific exception, durable audit outage semantics, and process/replica limits
remain open.

## PostgreSQL shared state across OS processes — 11 October 2026

Four Python OS processes issued 160 direct shared-limiter calls against the
isolated migration-373 portability database. The result was 114 allowed and
46 denied in 1.653 seconds, within the refill-aware upper bound. The temporary
bucket was deleted and the table returned to zero rows.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-multiprocess.json).

This proves shared adapter consumption across OS processes. It does not verify
the HTTP request path across API containers/replicas or durable outage audit.
The portability database was stopped afterward; the candidate remained
untouched.

## Real audit write failure on PostgreSQL outage — 11 October 2026

The gateway outage request was repeated with the real GatewayAudit.log method.
Its connection attempt failed with OperationalError; GatewayAudit logged the
failure and the middleware still completed the 503 response with Retry-After
30. No durable audit row could be written while PostgreSQL was unreachable.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-audit-outage.json).

This verifies visible failure handling without claiming persisted denial
history at the time of this probe. The later bounded journal/startup replay
check below supersedes this recovery status.

## Gateway ASGI shared limits across OS processes — 11 October 2026

Four ASGI gateway instances in separate OS processes used the PostgreSQL
provider against one synthetic identity. Of 160 GET /health requests, 121
returned 200 and 39 returned 429 with Retry-After, within the refill-aware
bound. The synthetic row was removed. Audit writes were suppressed for this
limiter-specific probe; no durable audit rows were written.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-asgi-multiprocess.json).

This checks the middleware and shared limiter across OS processes in one
container. Network HTTP across separate API containers/replicas and audit
replay after database recovery remain open.

## Network HTTP across two gateway containers — 11 October 2026

Two API containers on the private portability network selected the PostgreSQL
provider and shared one rate bucket. Across 160 HTTP GET /health requests sent
from a third container, 119 returned 200 and 41 returned 429 with Retry-After,
within the refill-aware bound. The synthetic request and Docker healthcheck
buckets were removed; the limiter table returned to zero rows.
[Evidence](builds/2026-10-11-recovery/postgres-rate-limit-two-api-http.json).

This verifies shared rate limiting over private-network HTTP to two API
containers. Public ingress, multi-host routing, replica failover/scale, and
production scale remain open; audit recovery status is updated in the later
journal section below.

### Gateway audit outage journal and replay — 11 October 2026

The earlier stop/restart probe recorded the pre-journal behavior: the outage
event was lost while a later write succeeded. Current source now journals
failed writes in a bounded per-deployment SQLite file and replays them to the
canonical audit table with stable IDs and timestamps. A real middleware denial
returned 503 with `Retry-After: 30`, queued one event, then the replacement
container's startup worker delivered it exactly once after PostgreSQL returned.
The original timestamp was preserved and the queue drained.
[Journal contract](gateway-audit-spool.md), [recovery evidence](builds/2026-10-11-recovery/gateway-audit-spool-recovery.json).

This is a verified basic recovery path, not complete audit availability.
Saturation, storage/host loss, backup/restore, candidate activation, and
multi-replica failover/scale remain open. The candidate still uses local
rate-limit state. The earlier observation remains available as
[historical baseline evidence](builds/2026-10-11-recovery/gateway-audit-outage-recovery.json).
