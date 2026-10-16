# Standard candidate: separate API and durable workers

Combine `docker-compose.kernel-candidate.yml` with
`docker-compose.kernel-standard.yml`. The app overrides its command to run only
the API; the new worker service runs the same Dockerfile/package with
`python3 -m services.core.runtime --workers-only --require-schema`. Both roles
require schema readiness before spawning child processes, use the private
candidate database, and explicitly disable vendor providers. No database port
or worker port is published. The API retains its localhost binding.

The supervisor starts enabled scheduler/event workers, generates a distinct
UUID-based identity for each supervisor lifetime, and refuses an empty worker
role. CLI worker modes are mutually exclusive. When migrations or required read
relations are missing, the supervisor exits before starting API or worker
children; Compose retries after the external migration runner completes.
Existing process-group shutdown,
shared 30-second drain budget, unexpected-exit failure, init process, and
40-second Compose grace period apply to both roles. Lease and delivery state
remain PostgreSQL state; unique identities do not prove concurrency safety.
The API defaults to the shared PostgreSQL rate limiter in this profile, so
migration 373 must be applied before serving traffic. An explicit provider
override is available for a reviewed deployment topology; multi-replica APIs
must retain a shared limiter.

## Deployment prerequisites

This overlay is prepared source, not a production certification. Apply migration
371 through the checksummed runner before starting these scheduler workers.
Migration 373 is also required before the standard profile's default shared
rate limiter can serve requests. Migration 372 is additionally required when
selecting the MQTT receipt path.
Inspect existing schedules, handler registrations, leases, and Prefect/cron
ownership before switching roles. Rebuild both roles from the same reviewed
source and dependency resolution; the current build is not release-pinned.

After acceptance, use encrypted secrets and the explicit candidate project:

```sh
export SOPS_AGE_KEY_FILE=/Users/gilbertoadon/.config/sops/age/keys.txt
export KOKONUT_ALLOW_PLAINTEXT_ENV=false
source scripts/load-secrets.sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-standard.yml up -d --build
```

The command is documented, not executed. Stop the combined app's workers and
allow their leases to settle before starting the separate worker on populated
data. Compose does not promise an atomic role cutover. Do not use a separate
project name to attach unrelated deployments to candidate data.

The worker disables the inherited HTTP healthcheck because it serves no HTTP.
Supervisor failure exits the container; a stalled but live worker needs durable
run/delivery progress monitoring. A progress watchdog remains pending. Caddy or
another TLS ingress remains an additional explicit choice; no public proxy is
included here. This is the role-separation portion of the standard profile.

The separate [Kernel proxy overlay](kernel-proxy.md) now provides the optional
Caddy portion, with loopback defaults and TLS/routing acceptance still pending.

The [analytics companion](analytics-overlay.md#separate-standard-worker) now
explicitly supplies worker ClickHouse drivers and connection settings. Edge
still configures the app only; combining it with this split role does not
automatically give the worker encrypted media settings or equivalent resource
limits. Define and review those worker settings before composing profiles.
Multiple worker replicas and API replicas remain scale acceptance work.

## Acceptance and rollback

Static lint, Compose parsing with placeholder credentials, and whitespace checks
passed. The focused profile contract checks also pass (2 passed). No service
starts, migrations, queued work, or running-container changes were performed.

Pending acceptance: API has no embedded workers; worker has no API; both roles
use identical code and provider settings; worker leases, retries, dead letters,
restart and shutdown preserve durable state; disabled-worker mode fails startup;
replicas have distinct identities; job/event parity and operator monitoring pass.

Rollback: stop and remove only the separate candidate worker, allow in-flight
leases to settle, then recreate the candidate app using the base manifest's
combined-role command. Omitting the overlay alone leaves an orphan worker that
must be stopped explicitly. Preserve database volumes, migration history, and
run/delivery evidence. Keep the legacy stack stopped during candidate cutover.
