# Provider configuration — first Phase 1 slice

`services/core/providers.py` provides an immutable `ProviderSettings` object.
`from_environment(mapping)` validates configuration without loading application
services, vendor packages, credentials, or database connections. An omitted
mapping reads the process environment. Explicit values must be `true` or `false`
(case insensitive, surrounding whitespace allowed); malformed values fail early
with the setting name and never echo the supplied value.

The existing feature registry consumes these settings at import time. Restart
the application after changing settings. All historical defaults remain:
Directus, ClickHouse, gRPC, Metabase, and MQTT enabled; Prefect disabled.
PostgreSQL cannot be disabled. Directus remains critical when selected. The
legacy stored-SQL dashboard refresher is disabled unless
`KOKONUT_FEATURE_LEGACY_DATASET_SQL=true` is set explicitly. The settings are
shown in `.env.example`.

Health output includes every configured feature by default. Disabled providers
receive `state=disabled`, `healthy=true`, and `critical=false`, without running
a probe or importing the vendor implementation. `healthy=true` here means the
disabled dependency does not block health, not that it can serve requests.
Enabled features without probes report `state=unmonitored`; successful or failed
probes report `state=checked`. An explicit empty target list checks nothing.
Existing `healthy` aggregation is preserved; optional probe failures still make
the aggregate unhealthy, while `critical_failures` identifies required failures.

This slice does not gate domain routes, start/stop Compose services, provide
native Directus replacements, replace analytics, or supervise workers. Therefore
disabling Directus currently removes its health requirement but leaves dependent
gateway location routes unavailable. No lightweight deployment is certified yet.
Metabase's Compose opt-in and its legacy feature default remain separate until
the deployment profile work reconciles them.

The `legacy_dataset_sql` feature is an execution gate, not a new provider. Its
default-off setting prevents `refresh_dataset()` and the refresh CLI from
executing stored `dashboard_dataset.query_sql` until an operator explicitly
enables the compatibility path. Read-only dataset listing remains available.
Enabling it does not establish query safety, least-privilege database grants,
location scoping, or result materialization; those acceptance gates remain open.

## Acceptance and remaining checks

- Settings module uses only the standard library.
- Legacy defaults and existing feature registry function signatures retained.
- Disabled providers bypass registered probes and port checks.
- PostgreSQL health connections close even after a failed query.
- No schema, durable state, credentials, or Docker changes in this slice.
- Lint and formatting reviewed; runtime/contract tests have not been run.
- Before profile cutover, exercise defaults, malformed values, disabled-provider
  probes, absent optional packages, explicit target lists, and gateway health
  response compatibility in the focused core/gateway suites.

Rollback: revert provider settings wiring, feature switches, and additive health
state fields, then restart the application with its prior environment. No data
rollback is needed. The existing Docker stack remains available.

## ClickHouse adapter boundary

`services/core/ports.py` declares structural `ProviderHealth` and `HealthProbe`
contracts. The existing explicit health registry is typed against these ports.
It still invokes the same probes; no dynamic plugin loading is introduced.

`services/core/adapters/clickhouse.py` owns the optional `clickhouse_connect`
import. Both `services/ingestion/base.py:get_clickhouse` and
`services/export/exporter.py:get_ch` delegate client construction to this adapter.
Ingestion retains the driver's default database; exports retain their configured
database. A disabled provider or missing driver returns `None`; connection errors
continue to propagate. Existing callers retain ownership of client cleanup and
their existing error/skip behavior. The export warning now covers both disabled
and missing-driver cases.

The adapter checks provider settings before importing the optional driver.
This factory reads settings per call; the legacy feature registry remains an
import-time snapshot, so restart remains required after configuration changes.
No SQL, outbox delivery protocol, authorization, or export schema changes.
Direct ClickHouse driver imports are now confined to the adapter. Prefect,
MQTT, and gRPC boundaries still need migration before Phase 1 acceptance.

Static lint and whitespace checks passed. Runtime contract suites remain pending.
Rollback this slice by restoring the two legacy connection factories and the
untyped health registry; no schema or data changes require reversal.

## MQTT adapter boundary

`services/core/adapters/mqtt.py` owns the sole Paho import and constructs the
existing callback-v2 client without connecting to a broker. Subscriber startup
and actuator publication delegate construction to it. Disabled MQTT returns
before driver loading, credential checks, TLS setup, or broker connection.
Subscriber startup returns without running; publication returns `False` so it
cannot be mistaken for successful delivery. Missing-driver CLI/error behavior
is retained, as are actuator client-construction error handling and return values.

Topic names, QoS, TLS/client certificates, HMAC validation, registered-device
lookup, PostgreSQL writes, ClickHouse outbox enqueue, command logging, and human
approval logic are unchanged. This step does not replace sensor envelopes or
change actuation policy. HTTP/CSV ingestion remains independent.

Lint and whitespace checks passed. Runtime sensor/actuator suites remain pending;
no broker was started and no physical-device commands were sent. Rollback restores
the two local Paho construction sites; persistent state needs no reversal.

## gRPC application boundary

`services/core/adapters/grpc.py` provides guarded `serve()` and
`check_health(target)` entry points. The CLI delegates to these functions.
Disabled selection raises an explicit configuration error before importing the
legacy server or gRPC driver, creating a channel, or opening a database pool.
The health CLI retains its status output and failure exit code; its channel
closes on success, non-serving status, or RPC error.

`services/grpc/` is the existing transport adapter package, including generated
bindings, interceptors, and RPC handlers. Its vendor imports remain there, as
required by its SDK implementation. Directly importing that package's server
module still requires its optional packages; application callers use the lazy
core boundary. `server.serve()` additionally guards selection before opening
the database pool, preserving module-level symbols used by existing consumers.
No RPC schema, service registration, API-key policy, TLS, or shutdown changes.

Lint passed for the new adapter and CLI; whitespace checks passed. Existing
server lint debt is outside this slice. Runtime gRPC suites remain pending.
No RPC listener was started. Rollback restores CLI delegation and removes the
server selection guard; there is no persistent data migration.

## Prefect decorator boundary

The flow modules obtain decorators through
`services/core/adapters/prefect.py`. Only that adapter imports the Prefect SDK.
Importing the adapter or `services.flows` alone does not load it. Requesting
`flow` or `task` returns the actual Prefect decorator, preserving genuine flow
objects, deployment discovery, names, and retry configuration. Importing a
concrete legacy flow definition still requires Prefect because its decorators
execute during module initialization. No identity-decorator fallback is used.

Explicit legacy Prefect entry points continue working regardless of the legacy
reporting flag (which historically defaults to false). This slice does not
reinterpret that flag as scheduler selection or install a second dispatcher.
Subprocess commands, schedules, retries, and human verification boundaries are
unchanged. Unused Prefect task/hash imports were removed from pipelines, and
`full_pipeline` now references its own monitoring/analytics functions instead
of importing nonexistent sibling modules.

The existing pipeline `.submit()` calls on flow objects remain a known runtime
validation gate. They must be reconciled with the installed Prefect API before
pipeline parity can be certified. No scheduler cutover has occurred and no
flows were executed. Adapter/package lint and whitespace checks passed; runtime
workflow checks remain pending. Rollback restores decorator import paths and
package exports; no database or schedule rollback is needed.

## Import boundary gate

`scripts/check-provider-boundaries.py` parses all Python sources under
`services/` using only the standard library. The fast-fail CI script now invokes
it. It rejects ClickHouse, Paho, Prefect, Redis, and gRPC SDK imports outside
explicit allowed paths, including imports inside functions and literal dynamic
imports using `importlib.import_module` or `__import__`. Parse errors fail the
gate. It never imports application modules or reads environment/secret values.

The existing `services/grpc/` package is an explicit transport adapter, including
generated bindings. `services/security/interceptor.py` is a narrow documented
exception: its existing class subclasses the gRPC interceptor API. Moving it
would affect existing import consumers, so it remains an SDK-specific security
adapter for this phase. No general exemption exists for security/domain modules.

This is a source-level dependency check, not a Python sandbox. Aliased dynamic
loaders, computed module names, transitive dependencies, and non-Python runtime
coupling still require review. Adding an allowed path requires an architectural
decision; the gate does not certify runtime capability parity. Full CI and
runtime suites have not been run.

## First analytics catalog query

`services/analytics/queries.py` defines `AnalyticsBackend`, `QueryId`, an immutable
`MetricSummaryRequest`, `AnalyticsContext`, and typed `MetricSummary` results.
The catalog initially supports only `public_metric_summary`. The application
construction boundary is `services/analytics/backend.py:get_analytics_backend`;
its existing PostgreSQL implementation lives in
`services/core/adapters/postgres_analytics.py`. An injected connection factory
supports future contract checks without opening a production connection.

The gateway public metrics route calls the backend instead of embedding SQL.
It retains the same path, public route policy, view, parameter binding, ordering,
response keys, timestamp conversion, and empty-result behavior. Database failures
now enter the route's existing internal-error handler, including connection
creation failures. Cursor and connection cleanup run on failed queries too.

The adapter rejects unknown query IDs, non-public contexts, and location scope
mismatches before connecting. The context is constructed by this public route;
it is not an authenticated principal or a substitute for gateway authorization.
The governed public view remains the data visibility boundary. No draft/private
query, caller-supplied SQL, export, pagination, or ClickHouse implementation is
introduced. Those require additional catalog entries and policy review.

Lint and whitespace checks passed. Runtime route parity and adapter contract
checks remain pending. No metrics were computed or verified. Rollback restores
the route's previous inline query and leaves these additive interfaces unused.

## Computation cache port

`services/cache/ports.py:ComputationCacheBackend` describes the current persisted
cache API: get, set, invalidate, expiration cleanup, and statistics.
`services/cache/backend.py:get_computation_cache` retains `ComputationCache` as
the default implementation and accepts its existing connection and TTL options.
The original class import remains supported.

All four event invalidation handlers construct through that boundary and accept
an optional keyword-only backend for application injection. Existing event bus
calls with two positional arguments remain valid. Cache keys, location scoping,
invalidation reasons, counts, SQL transactions, result metadata, TTLs, provenance,
and hit counters are unchanged. The PostgreSQL implementation and its existing
connection ownership behavior are retained.

This port intentionally models persisted computations. An ephemeral memory/Redis
cache cannot replace it without preserving metadata and invalidation semantics;
such a replacement is not selected here. No Redis dependency or feature switch
is introduced. Lint and whitespace checks passed; runtime cache/event checks
remain pending. Rollback restores direct construction in the four handlers;
cache records and database schemas need no reversal.

## Durable event-store port

`services/events/ports.py:EventStore` matches the existing public bus operations:
publish, process pending, replay/dispose dead letters, statistics, cleanup, and
close. Claims, acknowledgments, retries, and handler execution remain internal
to `EventBus`, preserving its ownership checks rather than introducing alternate
paths. The port does not claim transactional append or publisher idempotency
features absent from the current public publish API (which commits its insert).

`services/events/backend.py:get_event_store` constructs the existing PostgreSQL
bus with its connection and lease options. The six bus-backed CLI commands now
use that factory. Single-run process, statistics, and cleanup commands close
their owned connections on exit; worker and operator commands retain their
existing cleanup. Injected connections retain the bus's non-owning behavior.

Importing `services.events` no longer eagerly imports the psycopg2-dependent
insight-transfer engine. Its package-level `InsightTransferEngine` export is
resolved lazily, preserving its public import path. No insight-transfer policy,
event SQL, multiprocessing timeout, retry ceiling, dead-letter disposition,
handler registration, or durable state changes.

Ports/factory/package lint and whitespace checks passed; runtime durability and
CLI suites remain pending. No events were dispatched or replayed. Rollback
restores CLI construction and the eager package export; no data rollback is
needed. Scheduler interfaces and worker supervision remain separate work.

## Durable scheduler port

`services/scheduler/ports.py:SchedulerBackend` exposes the existing tick and
status operations plus a public worker identity. The construction boundary
`services/scheduler/backend.py:get_scheduler` retains `SchedulerEngine` with
its existing PostgreSQL connection and worker-ID arguments. Status/tick CLI
commands and the worker construct through that factory. The engine's new
read-only `worker_id` property replaces private-field access in worker logging.

Engine construction is inside the worker's cleanup block so a constructor
failure closes the already-opened connection. Caller-owned connections and
transaction recovery remain the worker/CLI's responsibility. Claims, execution,
heartbeats, lease-loss checks, resource admission, retry budgets, subprocess
isolation, schedule calculation, and task-run SQL are unchanged. Operator
enable/disable/run-now commands retain their existing SQL and behavior.

This port deliberately keeps ownership-sensitive operations encapsulated by
tick. It does not invent register/pause/heartbeat APIs or certify equivalent
Prefect scheduling. No second scheduler, ASGI background loop, or process
supervisor is started. New ports/factory/worker lint and whitespace checks
passed; runtime scheduler durability and CLI checks remain pending. Rollback
restores direct engine construction and private worker-ID logging; there is
no durable-state rollback.

## Integration review corrections

Disabled ClickHouse delivery now exits `clickhouse_outbox.deliver_batch` before
claiming any rows, preserving pending projections, leases, and retry budgets
during an intentional pause. Producers continue enqueueing durable projections;
operators can resume delivery after re-enabling the adapter. This does not
certify backlog/storage limits or change enabled-provider delivery behavior.

ClickHouse health probes close their client after ping and treat a false ping
result as unhealthy. Aggregate health now includes additive `ready`, true when
there are no critical probe failures. Existing `healthy` aggregation and gateway
HTTP-status selection remain unchanged; this field does not create a separate
readiness endpoint or establish unmonitored worker readiness.

`services.core` package exports now resolve lazily. Importing ports/settings or
adapter modules no longer initializes the entire feature registry and health
module through the package initializer. Existing public import names remain.

Core lint, provider-boundary, and whitespace checks passed. Runtime validation
remains pending. No rows were claimed and no probes or workers were run during
this review. Rollback removes the additive readiness field and lazy exports;
retain the disabled-delivery guard to preserve paused outbox state.
