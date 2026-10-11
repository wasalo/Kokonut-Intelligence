# Opt-in candidate ClickHouse overlay

Combine `docker-compose.kernel-analytics.yml` with the standalone candidate file
under the same separate candidate project. Never combine it with legacy Compose.

    docker compose -p kokonut-kernel-candidate -f docker-compose.kernel-candidate.yml -f docker-compose.kernel-analytics.yml build app

The overlay sets the explicit ClickHouse feature flag and connection settings,
adds its private service and dedicated volumes, and waits for service health.
It requires CLICKHOUSE_PASSWORD only when the overlay is selected. The base
candidate remains PostgreSQL-only and does not interpolate that secret.

The app build argument `KOKONUT_CLICKHOUSE=true` installs the driver-only
`requirements/clickhouse.txt`; its default false excludes the SDK. Invalid build
argument values fail. ML/GIS packages remain separate and are not implicitly
installed. Docker now copies only its selected requirement files before package
installation so edits to dependency documentation do not invalidate that layer.
The eleven groups now reproduce all 28 root package constraints exactly,
including the subsequently added encrypted-storage dependency.

This prepares an optional provider, not analytical capability acceptance.
Initialize the six existing ClickHouse schema files in their documented order
before resuming projections. Verify database selection, every target table,
outbox lineage, and restart/replay behavior first. Health ping cannot certify
tables or projection freshness. No automatic schema application, backfill,
outbox replay, or legacy-volume reuse is configured.

Merged Compose syntax and dependency-group alignment checks passed. No analytics
image build, service start, or projection delivery was performed. The running
base candidate was not changed. ARM64 image/wheel compatibility, memory limits,
data lineage, table bootstrap, and runtime parity remain pending.

Rollback to PostgreSQL-only by rebuilding with only the base candidate file and
recreating its app, then explicitly stopping the candidate ClickHouse service.
Preserve ClickHouse volumes and pending PostgreSQL outbox rows. Do not use
volume removal or orphan removal as part of profile switching. Disabling
ClickHouse intentionally pauses delivery before claims; producers can continue
accumulating projections, so monitor backlog and storage.

## Separate standard worker

For split API/worker roles, select the companion overlay last:

```sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-standard.yml \
  -f docker-compose.kernel-analytics.yml \
  -f docker-compose.kernel-standard-analytics.yml build app worker
```

This sets the worker's driver build argument, explicit provider flag, password,
database/host/port/user, and ClickHouse health dependency to the same values as
the app. It must accompany all three preceding manifests: the companion alone
is not a complete worker or database definition. The standard manifest alone
keeps ClickHouse disabled. Gateway/vendor health probes are not worker progress
checks, and a healthy ClickHouse ping does not establish schema readiness.

The command is documented, not executed. Both roles must be built from the same
reviewed source and dependency resolution before adoption. Migration 371 is
required for the updated scheduler. Bootstrap and inspect ClickHouse tables,
then explicitly select a reviewed projection-delivery owner. Merely selecting
these overlays does not invoke `clickhouse_outbox --run-once`, register a job,
or drain accumulated projections. Existing leases, retry limits, and operator
dead-letter handling still apply to delivery.

Merged four-file Compose parsing with placeholder credentials passed. Worker
analytics image builds, import/startup, schema parity, concurrent claims,
recovery, projection delivery, and ARM64 acceptance remain pending. No tests,
services, migrations, or outbox operations were run for this companion slice.

To roll back while retaining separate roles, stop projection dispatch and
recreate both app and worker from candidate + standard only, rebuilding without
the ClickHouse driver. Stop the candidate ClickHouse explicitly; omitting its
manifest does not stop orphan containers. Retain both database volumes and all
pending, attempted, and dead-letter outbox evidence.
