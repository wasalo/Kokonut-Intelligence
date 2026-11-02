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
`docker-compose.kernel-standard.yml`, `docker-compose.kernel-runtime-role.yml`,
and `docker-compose.kernel-proxy.yml` by default. The app overrides its
command to run only the API; the worker service runs the same
Dockerfile/package with
`python3 -m services.core.runtime --workers-only --require-schema
--require-runtime-role`. Both roles require schema readiness and a dedicated
unprivileged runtime login before spawning child processes. The role gate
requires the same session/login role, LOGIN, NOINHERIT, and no role
memberships; it rejects superuser, database/role creation, replication,
RLS-bypass, database-owner, or database-owner-member logins. The services use
the private candidate database and explicitly disable vendor providers. No
database port or worker port is published. The API retains its localhost
binding. Caddy's
HTTP and HTTPS host ports default to loopback (`127.0.0.1:8088` and
`127.0.0.1:8448`) with the local `localhost` domain; this is a development
ingress, not public TLS or Internet exposure.

The supervisor starts the scheduler and the event-dispatch and notification
delivery child processes, generates distinct UUID-based identities for each
supervisor lifetime, and refuses an empty worker role. The event-bus and
notification feature switches may default on, but their isolated database
worker switches default off. In that state they remain paused without opening
a shared database connection. Enabling either operation requires its dedicated
DSN, login, and migration-backed bounded functions. CLI worker modes are
mutually exclusive. The scheduler retains the shared control-plane login, but
filters scheduled commands to only the dedicated worker credentials selected
by the source allowlist. Freshness and ClickHouse outbox delivery follow the
same explicit-worker model; disabled paths do not use shared-runtime writes.
Notification enqueue also uses its separate migration-417 identity when
configured destinations exist, and fails closed if that path is unavailable.
When migrations or required read
relations are missing, the supervisor exits before starting API or worker
children; Compose retries after the external migration runner completes.
Existing process-group shutdown,
shared 30-second drain budget, unexpected-exit failure, init process, and
40-second Compose grace period apply to both roles. Lease and delivery state
remain PostgreSQL state; unique identities do not prove concurrency safety.
The API defaults to the shared PostgreSQL rate limiter in this profile. A
current target must have the complete ordered schema applied before serving
traffic; migration 373 introduced its bucket table, and migration 712 moves
access behind bounded functions. Optional maintenance uses a separate schema
and login. Role provisioning removes `PUBLIC` execution on restricted
credential/context functions; the maintenance login inherits only the shared
`kokonut_security` schema usage and its explicit cleanup grant.
An explicit provider override is available for a reviewed deployment topology;
multi-replica APIs must retain a shared limiter.

### Isolated event and notification worker identities

Event dispatch uses migration 648's dedicated identity and bounded queue/receipt
functions. Notification delivery uses migration 647's dedicated identity and
bounded claim/completion functions. Both isolation flags are off by default.
Before enabling, provision the matching password through the runtime-role
bootstrap after the ordered migration run, provide the worker-only DSN, and
select the flag. Compose does not pass those DSNs to the API. The supervisor
removes shared PostgreSQL credentials and unrelated worker secrets from each
child. Delivery receives only the SMTP, webhook, and Directus settings needed
to send; the dispatcher receives no provider destination secrets. An isolated
deny marker also prevents a legacy module from restoring shared credentials
from a mounted `.env` file.

Notification enqueue is a separate operation using migration 417's dedicated
identity and source-validated function. When destinations are configured but
this path is disabled or unprovisioned, the handler fails and the event follows
its retry/dead-letter policy; it does not silently acknowledge a missing
notification. Migration 723 removes direct shared-runtime DML from event
receipts, freshness output state, and notification attempts while preserving
reads. The API and general worker still share `kokonut_runtime`, so these
operation identities do not complete C1. See the
[migration-647 disposable acceptance](builds/2026-10-25-recovery/notification-delivery-worker-disposable.json),
the [focused supervisor/profile checks](../../tests/test_kernel_runtime_supervisor.py),
and the current [C1 status](current-state-and-implementation.md#c1-runtime-acl-work-current-batch).

## Deployment prerequisites

This overlay is prepared source, not a production certification. Migration
371 introduced the scheduler worker contract, migration 373 the standard
profile's shared rate limiter, and migration 372 the MQTT receipt path. For a
fresh or existing target, apply the entire current ordered migration ledger,
then confirm readiness before starting workers; do not select those historical
IDs as a substitute for the full migration run.
After migrations, run the Standard profile's explicit
`bootstrap-runtime-role` action once with a database-owner credential, a
separate `KOKONUT_RUNTIME_USER`/`KOKONUT_RUNTIME_PASSWORD`, and a separate
operator-auth credential. The app and worker do not depend on this admin
service and never receive its credentials. They fail closed before spawning
children if the connected database login is privileged or owns the database.
The compatibility DML grant runs only when the runtime login is first created.
Later bootstrap runs preserve existing relation grants and reapply reviewed
denials without granting newly created tables to the login. Existing broad
grants remain until a reviewed migration retires them; do not run the bootstrap
during routine `up` or simply to add a newly migrated table.
Inspect existing schedules, handler registrations, leases, and Prefect/cron
ownership before switching roles. For source acceptance, `--action build` builds
the app and worker from the checkout. That path is useful during development,
but it is not an immutable release deployment.

For a release deployment, publish and review the application image first, then
set `KOKONUT_KERNEL_APP_IMAGE` to its registry reference with a SHA-256 digest.
The reference must identify a multi-platform OCI manifest index that contains
the target architecture. The same image is used for the API and worker. If
`--oidc` or `--zitadel` is selected, also set
`KOKONUT_KERNEL_OIDC_IMAGE` to its own digest-pinned application image. The
self-hosted ZITADEL Compose defaults are already digest-pinned; any explicit
`KOKONUT_ZITADEL_POSTGRES_IMAGE`, `KOKONUT_ZITADEL_API_IMAGE`, or
`KOKONUT_ZITADEL_LOGIN_IMAGE` override must also include a SHA-256 digest.

The separate
[`Publish Kernel images` workflow](../../.github/workflows/publish-kernel-images.yml)
is manual only. It accepts publication only when dispatched from `main` with
the `publish` confirmation, then publishes the `kernel` and `oidc` Dockerfile
targets for `linux/amd64` and `linux/arm64` to GHCR. It verifies both pushed
manifest indexes and writes the exact digest-pinned `KOKONUT_KERNEL_APP_IMAGE`
and `KOKONUT_KERNEL_OIDC_IMAGE` values to the workflow run summary. BuildKit
provenance and SBOM attestations are attached to each image. The registry tags
are unique to the source SHA and workflow attempt; deploy the recorded digest
references rather than a tag. The workflow does not deploy the images. Before
first use, configure the `kernel-release` GitHub
Environment with required reviewers, prohibit self-review, and restrict
deployment branches to `main`; the workflow's environment gate cannot enforce
review until those repository settings exist. No image has been published by
adding this workflow.

`--action release-up` accepts only Standard with the release image contract. It
prints a `docker compose pull` followed by
`docker compose up -d --no-build --wait --wait-timeout 300`; it does not run
either command itself. It never builds on the deployment host. Before executing
the printed command, verify the image digests and OCI index architecture against
the release record, review the resolved Compose configuration without exposing
it in logs, and complete the migration, role bootstrap, backup, and rollback
gates above. The action currently rejects the `grpc`, `http-sensors`, `directus`,
`mqtt`, and `sensor-anomaly-ml` overlays because they do not yet have a complete
published immutable-image contract. Use source-build actions for those optional
overlays until their images are built and reviewed separately.

After acceptance, use encrypted secrets and the explicit candidate project:

```sh
: "${SOPS_AGE_KEY_FILE:?Set this to your private age identity path}"
export KOKONUT_ALLOW_PLAINTEXT_ENV=false
source scripts/load-secrets.sh
python3 scripts/kernel-profile.py standard --action config
python3 scripts/kernel-profile.py standard --action database-up
python3 scripts/kernel-profile.py standard --action migrate
python3 scripts/kernel-profile.py standard --action bootstrap-runtime-role
python3 scripts/kernel-profile.py standard --action up
```

`database-up` prints a command that starts only PostgreSQL. `migrate` prints the
ordered, schema-only migration runner command, which uses the explicit Standard
Compose project to execute `psql` inside the database container. Run that
printed Python command from the repository root after loading secrets; keep
`PG_USER=kokonut` and `PG_PASSWORD` unset so the migration runner uses the
database-owner credential. The other actions print Compose commands. These
commands are documented here, not executed by this record. Provisioning is
deliberately a separate post-migration action. Standard selects Caddy without a
redundant `--proxy` flag. Use `standard --oidc` to add the Gateway OIDC client
while keeping the default loopback Caddy ingress. Caddy's local CA is not
automatically trusted by browsers or clients, so local browser acceptance still
requires trusting the development certificate.

For an immutable release, export the reviewed application image references and
ask the planner to print the pull-and-start command:

```sh
export KOKONUT_KERNEL_APP_IMAGE='registry/repository@sha256:64-lowercase-hex-digest'
python3 scripts/kernel-profile.py standard --action release-up
```

For OIDC, add `--oidc` and export the reviewed digest for
`KOKONUT_KERNEL_OIDC_IMAGE`. For self-hosted ZITADEL, add `--zitadel`; its
digest-pinned defaults may be used, or explicit image overrides must also be
digest-pinned. `release-up` rejects source-only optional overlays without a
published immutable-image contract. Review and execute the printed command
separately after release approval.

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

## Current Standard acceptance — migration 745 — 1 November 2026

The network-disabled disposable Standard recovery applied all 736 ordered
schema migrations through migration 745 with zero failures or seed rows. It
captured one migration snapshot and verified the API and worker images use the
same schema bytes. Runtime-role provisioning/reapplication preserved the
reviewed read-only relations, including the three current public summary views;
optional Directus checks and bounded freshness reads also passed. The API,
worker, and proxy started healthy. The check observed worker degradation and
recovery through a database outage, detected and recovered from a live-but-
stalled child, then verified clean worker shutdown, removal of the supervisor
heartbeat, zero active leases, and no published host ports on an internal
network. Candidate, legacy, and production data were untouched
([acceptance summary](builds/2026-11-01-recovery/standard-profile-recovery-745-disposable.json);
[runner](../../scripts/check-kernel-standard-recovery-disposable.py)).

The accepted schema includes migration 742's global curated
`readiness_dimension` boundary (location-specific weights remain in
`readiness_location_weight`) and migrations 743–745's read-only boundaries for
`v_public_ebf_scorecard`, `v_public_metric_summary`, and
`v_public_wellbeing_metric_summary`. Existing SELECT behavior is retained;
the base-table writers and RLS policies are unchanged. The owner confirmed
`readiness_dimension` is global/read-only for Directus. The owner reports no
known external writers for `quality_grade`; external-client review remains
open.

The API and worker remain separate services using the same
`kokonut_runtime` database login. This short disposable acceptance does not
complete C1, establish populated-data parity, external provider or public
ingress readiness, 24-hour recovery, scale, backup restoration, or production
acceptance. Native and ARM64/QEMU replays through migration 745 each passed
736/736 schemas and the 47-check synthetic operator/two-tenant probe; the
emulated run cleaned up successfully. QEMU is not physical Raspberry Pi
acceptance
([native](builds/2026-11-01-recovery/native-current-schema-745-operator-probe.json);
[ARM64/QEMU](builds/2026-11-01-recovery/arm64-qemu-current-schema-745-operator-probe.json)).

## Previous Standard acceptance snapshot — migration 738

The latest network-disabled disposable Standard recovery applied all 729
ordered schema files through migration 738 with zero failures or seed rows.
The harness captured a stable schema snapshot before building the API and
worker images and verified both image inputs against its SHA-256. It exercised
fresh migration-created role placeholders, post-migration runtime provisioning
and reapplication, the read-only migration ledger, API/worker/proxy health,
database outage degradation and recovery, private heartbeat behavior, zero
active leases after shutdown, and disposable resource cleanup. No host ports,
external network, seeds, candidate, legacy stack, or production service were
used ([acceptance evidence](builds/2026-11-01-recovery/standard-profile-recovery-738-disposable.json);
[runner](../../scripts/check-kernel-standard-recovery-disposable.py)).

Native and ARM64/QEMU network-disabled schema replays each applied 729/729
ordered migrations through 738 and passed the synthetic two-tenant/operator
probe. The current scoped ACL policy check verifies 113 private relations,
107 mutation-denied relations, and three append-only relations, with zero
table/column violations inside that declared policy. The aggregate probe
reports 911 public tables with runtime DML while RLS is disabled. The joined
source/ACL report records 1,295 of 1,522 relations with effective runtime DML,
192 migration-denied relations matching policy, and zero policy mismatches;
3,640 of 4,947 SQL sites remain unresolved after tracing 261 verified Gateway
callback edges covering 943 sites. Static reachability does not prove route
authorization or runtime activation. These are scoped privilege and inventory
measurements, not confirmed leaks or proof of tenant isolation
([source/ACL report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-738.json);
[attribution inventory](runtime-role-attribution.json)). QEMU is portability evidence,
not physical Raspberry Pi acceptance
([native replay and probe](builds/2026-11-01-recovery/native-current-schema-738-operator-probe.json);
[ARM64/QEMU replay and probe](builds/2026-11-01-recovery/arm64-qemu-current-schema-738-operator-probe.json);
[reference-table ACL check](builds/2026-11-01-recovery/runtime-read-only-735-738-disposable.json)).

The API and worker are separate services but still connect as the same
`kokonut_runtime` database login. Distinct API and worker identities remain an
open C1 boundary. These short disposable checks do not establish long-running
handler lease reclaim, populated-data parity, live provider recovery, 24-hour
endurance, scale, public ingress, backup/restore ownership, or production
acceptance. The optional remote-checkpoint client now rejects malformed,
non-HTTPS, and credential-bearing endpoint URLs before S3 client construction;
16 mock-only tests include acceptance of the configured Cloudflare R2 endpoint.
No live R2 request or credential was used, so bucket permissions, inventory,
retention, and restore remain open. No candidate, legacy, or production
database or role was changed.

The 31 October recovery through migration 712 remains useful historical
evidence for the bounded Gateway rate-limit contract and its consume, deny,
check-only, and cleanup behavior
([historical evidence](builds/2026-10-31-recovery/standard-profile-rate-limit-712-disposable.json)).

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
explicitly supplies worker ClickHouse drivers and connection settings. To add
Edge's local encrypted media provider and app/database resource limits while
keeping Standard's API/worker split, select `standard --edge`. The planner adds
`docker-compose.kernel-edge.yml` after the Standard and runtime-role overlays,
so the API command and independent worker command remain intact. Supply
`MOBILE_MEDIA_LOCAL_KEY` through the encrypted environment before resolving or
starting this composition. The Edge private-media volume, provider, directory,
and key apply only to `app`; a source audit found no local-media storage caller
in the worker, so the worker receives none of those settings. Edge sets limits
on the database and API, not the worker; worker sizing remains a separate
acceptance decision. Multiple worker replicas and API replicas remain scale
acceptance work.

Inspect this composition with
`python3 scripts/kernel-profile.py standard --edge --action config` after
loading the encrypted environment. The planner prints the resolved command;
it does not execute it or supply `MOBILE_MEDIA_LOCAL_KEY` itself. Preserve the
Edge private-media volume when changing profiles so stored private evidence is
not lost.

## Acceptance and rollback

The latest stable-snapshot replay applies all 736 ordered schema files through
migration 745 and is recorded in the [dated Standard acceptance snapshot
above](#current-standard-acceptance-migration-745-1-november-2026). The replay does not start the
local candidate or establish production readiness. The harness pins migration
discovery and both app images to the same private snapshot, records its digest,
and preserves a redacted runner-output tail if the migration count changes or
a migration fails. Remaining acceptance includes populated-data lease/retry
recovery, provider outages and real delivery, disabled-worker behavior against
an explicit deployment, replica identity/scale, public ingress and trusted
proxy policy, operator alert routing, 24-hour endurance, and physical
Raspberry Pi testing when hardware is available. The health probe is one
signal; it does not establish provider recovery or multi-replica safety.

Rollback: stop and remove only the separate candidate worker, allow in-flight
leases to settle, then recreate the candidate app using the base manifest's
combined-role command. Omitting the overlay alone leaves an orphan worker that
must be stopped explicitly. Preserve database volumes, migration history, and
run/delivery evidence. Keep the legacy stack stopped during candidate cutover.
