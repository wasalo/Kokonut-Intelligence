# Standard candidate: separate API and durable workers

> **Current rollout status:** This document describes the source and acceptance
> evidence for the role-separated profile; it does not show that the latest
> source or full migration chain has been rolled onto a candidate. The full
> current state and gates are tracked in the
> [refactor status guide](current-state-and-implementation.md). Before any
> target starts, use the ordered checksummed migration runner and check that
> target's ledger; the older migration numbers below are feature-introduction
> references only.

The profile planner combines `docker-compose.kernel-candidate.yml`,
`docker-compose.kernel-standard.yml`, and `docker-compose.kernel-proxy.yml` by
default. The app overrides its command to run only the API; the new worker
service runs the same Dockerfile/package with
`python3 -m services.core.runtime --workers-only --require-schema`. Both roles
require schema readiness before spawning child processes, use the private
candidate database, and explicitly disable vendor providers. No database port
or worker port is published. The API retains its localhost binding. Caddy's
HTTP and HTTPS host ports default to loopback (`127.0.0.1:8088` and
`127.0.0.1:8448`) with the local `localhost` domain; this is a development
ingress, not public TLS or Internet exposure.

The supervisor starts enabled scheduler, event-dispatch, and notification
delivery workers, generates distinct UUID-based identities for each supervisor
lifetime, and refuses an empty worker role. Notification delivery defaults to
the event-bus feature setting and can be independently disabled or enabled.
CLI worker modes are mutually exclusive. When migrations or required read
relations are missing, the supervisor exits before starting API or worker
children; Compose retries after the external migration runner completes.
Existing process-group shutdown,
shared 30-second drain budget, unexpected-exit failure, init process, and
40-second Compose grace period apply to both roles. Lease and delivery state
remain PostgreSQL state; unique identities do not prove concurrency safety.
The API defaults to the shared PostgreSQL rate limiter in this profile. A
current target must have the complete ordered schema applied before serving
traffic; migration 373 is the historical feature-introduction reference for
that limiter. An explicit provider override is available for a reviewed
deployment topology; multi-replica APIs must retain a shared limiter.

## Deployment prerequisites

This overlay is prepared source, not a production certification. Migration
371 introduced the scheduler worker contract, migration 373 the standard
profile's shared rate limiter, and migration 372 the MQTT receipt path. For a
fresh or existing target, apply the entire current ordered migration ledger,
then confirm readiness before starting workers; do not select those historical
IDs as a substitute for the full migration run.
Inspect existing schedules, handler registrations, leases, and Prefect/cron
ownership before switching roles. Rebuild both roles from the same reviewed
source and dependency resolution; the current build is not release-pinned.

After acceptance, use encrypted secrets and the explicit candidate project:

```sh
: "${SOPS_AGE_KEY_FILE:?Set this to your private age identity path}"
export KOKONUT_ALLOW_PLAINTEXT_ENV=false
source scripts/load-secrets.sh
python3 scripts/kernel-profile.py standard --action config
python3 scripts/kernel-profile.py standard --action up
```

The planner prints a Compose command; `--action config` and `--action up` are
documented here, not executed by this record. Standard selects Caddy without a
redundant `--proxy` flag. Use `standard --oidc` to add the Gateway OIDC client
while keeping the default loopback Caddy ingress. Caddy's local CA is not
automatically trusted by browsers or clients, so local browser acceptance still
requires trusting the development certificate.

A separately managed ingress can replace Caddy with
`python3 scripts/kernel-profile.py standard --no-proxy`. For browser OIDC with
that selection, add `--oidc` and configure the external ingress to terminate
HTTPS and forward the exact configured callback and application paths to the
Gateway. The Gateway ignores forwarded headers by default; do not enable broad
proxy trust. Public-origin, secure-cookie, multi-hop trusted-proxy, public TLS,
DNS, and firewall behavior remain acceptance gates. `--no-proxy` cannot be
combined with `--zitadel`, because that self-hosted identity overlay includes
its own Caddy routes.

Stop the combined app's workers and
allow their leases to settle before starting the separate worker on populated
data. Compose does not promise an atomic role cutover. Do not use a separate
project name to attach unrelated deployments to candidate data.

The worker serves no HTTP, so its Compose healthcheck queries PostgreSQL's
durable scheduler-run, event-lease, and notification-lease state instead of
using the API probe. It reports an idle enabled-worker set as healthy and
active work as healthy while its durable lease is current. Processing work is
unhealthy only after its stored lease or task-timeout deadline plus the
configured grace period; a processing row without a lease is unhealthy
immediately. The same read-only query reports aggregate due-queue counts and
the oldest due age for pending events, due pending/retryable notifications,
and claim-eligible scheduled tasks. Scheduler backlog follows the claim
contract, including due retry time, active leases, disabled tasks, dependency
readiness, and overlap rules. Future notification retries are excluded;
dead-letter rows are informational operator work and do not trigger unhealthy
worker status. Future-dated event creation timestamps are counted with age
zero rather than a negative age. Neither IDs nor payloads appear in the health
result, and queues whose worker feature is disabled are omitted.

Database errors fail health closed and expose only the exception class. The
worker supervisor writes an atomic heartbeat to a mode-0600 file inside a
mode-0700 private directory every five seconds. The default heartbeat
age limit is 60 seconds and can be changed with
`KOKONUT_WORKER_PROGRESS_HEARTBEAT_SECONDS`; the file path is
`KOKONUT_WORKER_PROGRESS_HEARTBEAT_FILE`, defaulting to
`~/.local/state/kokonut/worker-progress/supervisor.json` for direct host runs.
Standard Compose overrides it with
`/var/lib/kokonut/worker-progress/supervisor.json`; the image creates that
directory as mode 0700, owned by the non-root application user. The
healthcheck rejects a missing, malformed, non-private, stale, or dead-process
heartbeat, and missing/dead enabled worker children, before it opens
PostgreSQL. Its `supervisor` field exposes only alive state, whole-second age,
and aggregate `children_alive`; it never returns process IDs or the generation
token. In Standard Compose, the file is ephemeral container state; the profile
adds no volume or migration for liveness.

The default stale-work grace period is 300 seconds and can be changed with
`KOKONUT_WORKER_PROGRESS_STALE_SECONDS`; the default maximum due-backlog age is
900 seconds and can be changed with
`KOKONUT_WORKER_PROGRESS_BACKLOG_SECONDS`. Both values must be integers from
1 through 2,678,400 seconds. If any enabled queue has due work at least that
old, the probe returns unhealthy with aggregate counts and ages only. Compose
checks every 30 seconds with a 5-second timeout and three retries. The heartbeat
age limit exceeds multiple probe intervals; Docker may therefore need several
checks to mark an unresponsive supervisor unhealthy. This is a health signal,
not an alert route or automatic queue repair. It detects stale claimed work,
old eligible backlog, a supervisor that stops refreshing its heartbeat, and
enabled children whose processes have exited. It cannot detect a child that is
alive but permanently hung. Focused source tests and the network-disabled
disposable PostgreSQL acceptance check cover due-time,
lease, dependency, overlap, and dead-letter behavior
([disposable evidence](builds/2026-10-31-recovery/standard-worker-backlog-disposable.json),
[focused test record](builds/2026-10-31-recovery/standard-worker-backlog-focused-tests.json)). Live database-outage,
operator alert routing, and prolonged worker-recovery acceptance remain open.
The default Caddy overlay gives Standard a loopback
TLS entry point; the separate
[Kernel proxy overlay](kernel-proxy.md) documents its routing, trust, and
public-ingress limits. An external ingress can replace Caddy with `--no-proxy`
while retaining the role-separated profile.

The [analytics companion](analytics-overlay.md#separate-standard-worker) now
explicitly supplies worker ClickHouse drivers and connection settings. Edge
still configures the app only; combining it with this split role does not
automatically give the worker encrypted media settings or equivalent resource
limits. Define and review those worker settings before composing profiles.
Multiple worker replicas and API replicas remain scale acceptance work.

## Acceptance and rollback

The Standard-profile planner change passes its focused planner and ZITADEL
contract suites, plus Compose configuration parsing with synthetic placeholder
values. These source checks do not start services or validate public ingress.
No migrations, queued work, or running-container changes were performed.

Pending acceptance: API has no embedded workers; worker has no API; both roles
use identical code and provider settings; worker leases, retries, dead letters,
restart and shutdown preserve durable state; disabled-worker mode fails startup;
replicas have distinct identities; job/event parity and operational alert
routing pass. The health probe does not by itself demonstrate provider outage
recovery, multi-replica behavior, or notification delivery to an operator.

Rollback: stop and remove only the separate candidate worker, allow in-flight
leases to settle, then recreate the candidate app using the base manifest's
combined-role command. Omitting the overlay alone leaves an orphan worker that
must be stopped explicitly. Preserve database volumes, migration history, and
run/delivery evidence. Keep the legacy stack stopped during candidate cutover.
