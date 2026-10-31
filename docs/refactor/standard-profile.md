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

The worker disables the inherited HTTP healthcheck because it serves no HTTP.
Supervisor failure exits the container; a stalled but live worker needs durable
run/delivery progress monitoring. A progress watchdog remains pending. The
default Caddy overlay gives Standard a loopback TLS entry point; the separate
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
replicas have distinct identities; job/event parity and operator monitoring pass.

Rollback: stop and remove only the separate candidate worker, allow in-flight
leases to settle, then recreate the candidate app using the base manifest's
combined-role command. Omitting the overlay alone leaves an orphan worker that
must be stopped explicitly. Preserve database volumes, migration history, and
run/delivery evidence. Keep the legacy stack stopped during candidate cutover.
