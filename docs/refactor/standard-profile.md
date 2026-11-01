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

The supervisor starts enabled scheduler, event-dispatch, and notification
delivery workers, generates distinct UUID-based identities for each supervisor
lifetime, and refuses an empty worker role. Notification delivery defaults to
the event-bus feature setting and can be independently disabled or enabled.
When `isolated_notification_delivery` is enabled, it selects the dedicated
notification child mode and filters that child's environment; otherwise it
retains the shared-runtime compatibility mode. CLI worker modes are mutually
exclusive. When migrations or required read
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

### Optional notification-delivery database identity

Notification delivery can run as an isolated child with the dedicated login
introduced by migration 647. It is opt-in and off by default. Set
`KOKONUT_FEATURE_ISOLATED_NOTIFICATION_DELIVERY=true` and provide
`KOKONUT_NOTIFICATION_DELIVERY_DATABASE_URL` to the Standard worker. Compose
does not pass either setting to the API. The supervisor strips the shared
PostgreSQL login and unrelated worker credentials from this child while
preserving the SMTP, webhook, and Directus delivery settings it needs. The
login receives only the bounded claim/completion functions; it gets no direct
table or sequence access. Provision it with the explicit runtime-role bootstrap
using `KOKONUT_NOTIFICATION_DELIVERY_PASSWORD` (and, if needed,
`KOKONUT_NOTIFICATION_DELIVERY_USER`) after the ordered migrations. This
isolates notification delivery only: the API and general worker still share
`kokonut_runtime`, and other worker children still use their configured
identities. See the
[migration-647 disposable acceptance](builds/2026-10-25-recovery/notification-delivery-worker-disposable.json)
and the [focused supervisor/profile checks](../../tests/test_kernel_runtime_supervisor.py).

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

## Dated Standard acceptance snapshot

The latest network-disabled disposable Standard recovery applied all 713
ordered schema files through migration 722 with zero failures or seed rows.
The harness captured a stable schema snapshot before building the API and
worker images and verified both image manifests against its SHA-256. It
exercised fresh migration-created role placeholders, post-migration runtime
provisioning and reapplication, the read-only migration ledger, API/worker/proxy
health, database outage degradation and recovery, private heartbeat behavior,
zero active leases after shutdown, and disposable resource cleanup. No host
ports, external network, seeds, candidate, legacy stack, or production service
were used ([acceptance evidence](builds/2026-11-01-recovery/standard-profile-recovery-722-disposable.json);
[runner](../../scripts/check-kernel-standard-recovery-disposable.py)). The
focused source/contract selection passes 279 tests; Ruff, schema-only migration
validation, runtime SQL inventory, dependency/provider boundaries, capability
matrix, Python compilation, release-input validation, and diff checks pass.

The API and worker are separate services but still connect as the same
`kokonut_runtime` database login. Distinct API and worker identities remain an
open C1 boundary; this recovery check does not claim otherwise. It also does
not prove long-running handler lease reclaim, populated-data parity, live
provider recovery, 24-hour endurance, scale, public ingress, backup/restore
ownership, or physical Raspberry Pi behavior.

This recovery confirms Standard's current default topology and bootstrap path;
it is not candidate rollout or production acceptance. A separate native,
network-disabled PostgreSQL replay now refreshes the aggregate runtime ACL
report and synthetic two-tenant operator-scope probe through migration 722. It
applies 713/713 schemas, passes all 38 checks, loads no seeds or farm data, and
cleans up its disposable resources. The report covers 1,522 public relations,
with 1,315 having effective runtime DML and 931 tables having runtime DML while
RLS is disabled; 172 migration-revoked relations match the declared policy,
with zero mismatches. It also records 212 unprotected DML relations without
candidate SQL relations and 374 without candidate write sites. These overlapping
counts measure privilege reach and heuristic inventory coverage, not confirmed
leaks or tenant isolation. The probe found zero direct table/column violations
within its declared scoped-write checks. ARM64/QEMU full replay through 722,
distinct API/worker identities, Directus/tenant reconciliation, candidate
rollout, and production acceptance remain open
([native replay and probe](builds/2026-11-01-recovery/native-resource-limited-schema-722-operator-probe.json);
[ACL report](builds/2026-11-01-recovery/runtime-privilege-callsite-report-722.json)).

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

The source-level planner and disposable-harness contract selection passes
116 tests, plus Ruff, Python compilation, and release-input validation. The
stable-snapshot replay now provides full current schema acceptance through
migration 718; it does not start the local candidate or establish production
readiness. The first replay attempt exposed a race between schema snapshot
capture and image build. The harness now pins migration discovery and both
images to the same private snapshot, records its digest, and preserves a
redacted runner-output tail if the migration count changes or a migration
fails. Remaining acceptance
includes populated-data lease/retry recovery, provider outages and real
delivery, disabled-worker behavior against an explicit deployment, replica
identity/scale, public ingress and trusted proxy policy, operator alert
routing, 24-hour endurance, and physical Raspberry Pi testing when hardware
is available. The health probe is one signal; it does not establish provider
recovery or multi-replica safety.

Rollback: stop and remove only the separate candidate worker, allow in-flight
leases to settle, then recreate the candidate app using the base manifest's
combined-role command. Omitting the overlay alone leaves an orphan worker that
must be stopped explicitly. Preserve database volumes, migration history, and
run/delivery evidence. Keep the legacy stack stopped during candidate cutover.
