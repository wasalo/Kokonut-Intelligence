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
supervisor lifetime, and refuses an empty worker role. By default the
scheduler retains the shared control-plane login for compatibility; the
explicit `--scheduler-role` Standard overlay selects the restricted executor
identity described below. When composed with `--separate-api-worker-logins`,
the supervisor stays on `kokonut_worker_runtime` while the scheduler child
uses its dedicated connection. The event-bus and
notification feature switches may default on, but their isolated database
worker switches default off. In that state they remain paused without opening
a shared database connection. Enabling either operation requires its dedicated
DSN, login, and migration-backed bounded functions. CLI worker modes are
mutually exclusive. The scheduler filters scheduled commands to only the
dedicated worker credentials selected by the source allowlist. Freshness and ClickHouse outbox delivery follow the
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

The API receives `KOKONUT_NOTIFICATION_WEBHOOK_CONFIGURED` as a non-secret
presence flag because it intentionally does not receive the webhook URL. It
defaults to `false`; set it to `true` in the selected Compose environment when
`ALERT_WEBHOOK_URL` is configured. The delivery worker alone receives the URL.
This explicit flag keeps the same behavior across Compose implementations that
do not support Docker's `${VAR:+value}` interpolation form.

### Opt-in scheduler executor identity

`python3 scripts/kernel-profile.py standard --scheduler-role` appends
`docker-compose.kernel-scheduler-role.yml` after Standard, runtime-role, and
selected architecture/service overlays. Standard does not select this identity
by default. The overlay changes only the worker-side PostgreSQL identity and
scheduler DSN; the Gateway API continues to use `kokonut_runtime`. It grants
scheduler claim/run/resource execution columns and queue-health reads, but not
schedule definition edits or direct completion-event writes. Completion events
use migration 747's bounded function. The bootstrap rejects unreviewed callable
`SECURITY DEFINER` access and broad/stale scheduler grants.

Load `KOKONUT_SCHEDULER_PASSWORD` and
`KOKONUT_SCHEDULER_DATABASE_URL` from the encrypted environment before asking
the planner for any scheduler-role command. Use a distinct password of at least
32 UTF-8 bytes. Apply the complete ordered migration set (including 747/748),
run the explicit `bootstrap-runtime-role` action with the overlay selected,
then start Standard with the same `--scheduler-role` selection. The scheduler
one-shot `--tick` uses this selected identity. `--run-now` is disabled in the
isolated scheduler environment because it bypasses durable claims; `--enable`
and `--disable` fail in that environment because the candidate has no
authenticated, audited schedule-administration path yet. The profile
planner keeps both secrets out of its printed command. `release-up` accepts
this configuration because the overlay introduces no additional image; the
same reviewed digest-pinned application image remains in use.

Authenticated synthesis dispatch is enabled only by this opt-in overlay; the
default Standard profile returns `503` for synthesis requests and creates no
receipt or scheduled task. Migration 751 adds the atomic receipt-and-one-shot
enqueue function. Before using the endpoint, apply the migration and configure
configure the requested task's source database URL and worker credential
through SOPS, using the `TASK_WORKER_KEYS` mapping in
`services/agents/task_registry.py` (for example, feedback synthesis uses
`KOKONUT_AGENT_FEEDBACK_SOURCE_DATABASE_URL` and
`KOKONUT_AGENT_FEEDBACK_SOURCE_WORKER_CREDENTIAL`). The scheduler process
receives the configured task identities, while each child receives only the
identity selected by its registered task key. Missing credentials fail closed
with no shared-database fallback. A dispatched task can create a draft only;
independent human review remains required.

The scheduler profile can be combined with G2 API/worker attribution:

```sh
python3 scripts/kernel-profile.py standard --separate-api-worker-logins --scheduler-role --action config
```

In the combined profile, the Gateway uses `kokonut_runtime`, the worker
supervisor uses `kokonut_worker_runtime`, and the scheduler child uses
`kokonut_scheduler_login` through `KOKONUT_SCHEDULER_DATABASE_URL`. The final
supervisor overlay restores the worker login after the scheduler overlay; the
scheduler child still selects its dedicated DSN and strips inherited `PG_*`
credentials. Both worker and scheduler secrets must be provisioned during the
explicit runtime-role bootstrap. The worker login still inherits the existing
runtime grants, so this composition improves attribution but does not narrow
the worker's privileges or close C1.

Example after loading the encrypted environment:

```sh
python3 scripts/kernel-profile.py standard --scheduler-role --action config
python3 scripts/kernel-profile.py standard --scheduler-role --action migrate
python3 scripts/kernel-profile.py standard --scheduler-role --action bootstrap-runtime-role
python3 scripts/kernel-profile.py standard --scheduler-role --action up
```

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

For G2 identity attribution, add `--separate-api-worker-logins` to Standard
`config`, `build`, `up`, `release-up`, `ps`, or `bootstrap-runtime-role` after
loading a distinct `KOKONUT_WORKER_RUNTIME_PASSWORD` from encrypted secrets.
The runtime-role bootstrap creates the marked worker login; the worker uses
that login while the API retains `KOKONUT_RUNTIME_USER`. Startup verifies the
worker has only the expected inheriting membership and cannot `SET ROLE` to
the API login. Until the caller map is reviewed, the worker inherits the same
existing ACL as the API. This separates attribution, not capability. The flag
can be combined with `--scheduler-role`: the worker supervisor keeps the
general worker login while the scheduler child uses its dedicated login as
described above. Do not describe this staged identity split as least privilege
or as closing C1. Verify the role membership, API/worker session identities,
inherited ACL behavior, and `SET ROLE` denial on a disposable PostgreSQL 16
instance with `python3 scripts/check-worker-runtime-identity-disposable.py`;
this synthetic acceptance does not change a candidate database.

Manual ClickHouse outbox actions require migration 746, the optional
`KOKONUT_CLICKHOUSE_OUTBOX_OPERATOR_PASSWORD`, and a separate post-migration
runtime-role bootstrap. Compose passes that credential to the Gateway API and
bootstrap only; the general worker receives none. The action login has no direct
table privileges and exposes only bounded, audited list/replay/resolve/discard
functions. Each OIDC operator action also requires its distinct global
capability; those capabilities are not seeded or granted by this profile and
must be explicitly approved and provisioned by a DBA. They are global controls,
not location-scoped tenant grants. Legacy CLI mutation flags are retired and
fail before database access.

Scheduler definition administration requires migration 749 and the normal
OIDC operator session/CSRF flow. The Gateway exposes bounded task inventory,
graph-validated enable, and guarded disable actions with per-task audit rows;
the isolated scheduler executor still cannot edit definitions. A DBA must
explicitly provision the operator's `scheduler:read`, `scheduler:enable`, or
`scheduler:disable` global capabilities through
`kokonut_security.grant_operator_global_capability`. The route uses the
Gateway's existing `kokonut_runtime` connection, so it does not close the
API/general-worker identity gap (C1) and is not candidate rollout acceptance.

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

`database-up` prints a command that starts only PostgreSQL and waits for its
healthcheck. `migrate` prints the
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

## Previous Standard acceptance snapshot — migration 745 — 1 November 2026

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

A repeat run on 2 November at source revision `672c8b2d` passed the same 736
schema snapshot, role bootstrap/reapplication, health, stalled-child and outage
recovery, and clean shutdown checks. The worktree was dirty, so this is
additional disposable evidence, not a clean committed-head PR gate. The run
used a unique project and generated synthetic credentials; its cleanup check
found zero project containers, volumes, or networks. It did not change the
candidate, legacy, or production targets
([rerun evidence](builds/2026-11-02-recovery/standard-profile-recovery-745-disposable.json)).

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

## Current Standard acceptance — migration 746 — 3 November 2026

A portless, network-disabled Standard recovery applied 737 ordered schemas
through migration 746 with zero failures or seed rows. A captured migration
snapshot matched in both API and worker images. Runtime-role bootstrap and
reapplication, optional Directus read-only checks, API/worker/proxy health,
stalled-child detection and recovery, database-outage recovery, clean worker
shutdown, private heartbeat removal, and zero active leases all passed. The run
used a dirty checkout at source revision `9c1bd501f8c7e2928b777926d55c78c6c9b559b4`
and schema snapshot SHA-256
`3757f48b2184cd83bdd33ea71720a0733a5422c6e8abd9040b1e7830bad6c0f0`; it is
not a clean committed-head PR gate or candidate/production acceptance.

Migration 746's separate PostgreSQL 16 check verifies the dedicated
ClickHouse outbox action login, global capability grants/revocations, session
binding, bounded replay/resolve/discard functions, operator audit, and runtime
enqueue-only privileges. No operator capability was granted on a persistent
target. Native and ARM64/QEMU two-tenant probes remain through migration 745;
the 47-check probe has not been rerun through 746. Evidence:
[Standard recovery](builds/2026-11-03-recovery/standard-profile-recovery-746-disposable.json),
[ClickHouse outbox operator](builds/2026-11-03-recovery/clickhouse-outbox-operator-746-disposable.json).

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
starting this composition. This stable 32-byte key protects local media and is
also the compatibility fallback for the API's S3/R2 `KKM1` envelope; the API
receives it through `MOBILE_MEDIA_ENCRYPTION_KEY`, while isolated worker
children strip both names and all media-provider settings. The Edge
private-media volume, provider, directory, and key apply only to `app`; a
source audit found no local-media storage caller in the worker. Preserve the
key in the encrypted recovery set and do not rotate it while objects encrypted
with it remain, unless they are first re-encrypted and verified. Edge sets
limits on the database and API, not the worker; worker sizing remains a
separate acceptance decision. Multiple worker replicas and API replicas
remain scale acceptance work.

Inspect this composition with
`python3 scripts/kernel-profile.py standard --edge --action config` after
loading the encrypted environment. The planner prints the resolved command;
it does not execute it or supply the media key itself. Preserve the media key
and Edge private-media volume when changing profiles so stored private
evidence remains readable and available.

## Shared-host Coolify deployment

Standard can store private report snapshots locally or in S3-compatible storage
such as Cloudflare R2. Local mode uses a persistent private volume prepared
with owner-only permissions; the Gateway mounts it read-only, and the dedicated
one-shot export container writes to it. In S3 mode the Gateway receives only
the reader key, and the opt-in `report-snapshot-export` container receives the
separate writer key. It handles one bounded batch of at most ten requests and
never starts with the general worker. Invoke it explicitly with
`docker compose --profile report-snapshot-export run --rm report-snapshot-export-worker`;
the profile does not create or enable recurring work. For R2, set
`KOKONUT_PRIVATE_EXPORT_PROVIDER=s3`, the endpoint, bucket, and region, plus
the reader/writer keys in the encrypted environment.

A clean or dedicated host is not required. The prepared Coolify variant is
designed to coexist with existing Docker workloads and use the host's existing
Traefik proxy. It leaves the Gateway, worker, database, and internal ZITADEL
services on the Compose network; the public Gateway service listens on
container port `8099`, and the private Caddy service routes the ZITADEL login
and API paths on container port `80`. Coolify terminates public HTTPS and
connects its proxy to the resource network. The Gateway remains directly behind
Traefik, preserving its current policy of ignoring forwarded client headers.
No candidate host ports or host-level Traefik settings are required.
Dedicated compute, replicas, and failover remain optional scale/availability
choices based on measured workload; they are not installation prerequisites.
The manifest's network and volume names use the fixed
`kokonut-kernel-coolify` prefix, so run one candidate instance per Docker host.
Running separate staging and production candidates on the same host requires
parameterized project, network, and volume names first.

Standard does not impose CPU or memory quotas. Containers share host CPU, RAM,
and disk, so monitor the combined workload and size per-service Coolify limits
from measured usage before the soak. The Edge overlay caps the API and database
at 1 GiB and 2 CPUs each; its worker remains uncapped, so those settings are
not a complete shared-host budget.

Render the single Git-based Compose definition from the reviewed overlays:

```sh
python3 scripts/render-kernel-coolify-compose.py
python3 scripts/render-kernel-coolify-compose.py --check
```

The renderer pins the Standard profile's separate API/worker database logins,
isolated scheduler executor, and self-hosted ZITADEL overlays. It asks Docker
Compose to merge those files without resolving environment variables or
absolute paths, so secrets stay as Coolify-managed placeholders and build/bind
paths remain relative to the repository root. Regenerate and check the artifact
whenever one of its source overlays changes. Do not hand-edit
`docker-compose.kernel-coolify.yml`.

The Coolify-only build overlay sets `pull_policy: build` on the Gateway and
worker. Both services name local images and define build contexts; without an
explicit policy Compose may reuse an existing local image instead of building
the checked-out source. The renderer requires this policy for both services.
See Docker's [`pull_policy` behavior](https://docs.docker.com/reference/compose-file/services/#pull_policy).

### Coolify private media configuration

Treat Coolify application environment variables as shared across every service
in the Compose resource. The live candidate showed that media credentials could
appear in non-Gateway containers even though the generated Compose manifest
declares explicit empty values for those services. The inventory and empty
overrides remain useful for ordinary settings, but they are not the security
boundary for media credentials.

For Coolify, keep the nine `MOBILE_MEDIA_*` values in `.env.sops` and remove
them from both production and preview application environment rows. Install the
allowlisted values from SOPS directly to the VPS without writing a plaintext
local file:

```sh
COOLIFY_SSH_HOST=root@your-coolify-host
COOLIFY_APPLICATION_ID=your-24-character-application-id
python3 scripts/install-coolify-media-config.py \
  --ssh-host "$COOLIFY_SSH_HOST" \
  --application-id "$COOLIFY_APPLICATION_ID" \
  --destination "/data/coolify/applications/$COOLIFY_APPLICATION_ID/private/media.env"
```

If SOPS cannot find the local age identity at its default path, set
`SOPS_AGE_KEY_FILE` to the authorized key file before running the command.

The installer validates the selected provider and required settings, streams
only the media keys over SSH stdin, and atomically creates a root-owned,
`10001` group-readable `0440` file. It prints the key names and permissions,
never their values. The file's parent is restricted to root. Use the same
procedure after rotating media credentials.

Set the nonsecret Coolify application variable
`KOKONUT_COOLIFY_MEDIA_SECRET_HOST_FILE` to the installed host path. The
Coolify-only overlay bind-mounts it read-only into the Gateway container at
`/run/kokonut/private-media.env`; it does not mount the file into the worker,
database, proxy, or ZITADEL services. The supervisor validates the file type,
ownership, permissions, provider, and required keys before starting the API.
It loads those values only into the Gateway child environment and removes the
file-path markers before creating child environments. The worker, scheduler,
event, and notification children receive no `MOBILE_MEDIA_*` values.

The Coolify environment-key inventory contains names only and is still checked
against `.env.example` and the tracked `.env.sops` key names. Add new nonsecret
app variables there. Standard Compose deployments continue to use their
normal per-service environment declarations; this private host-file procedure
is specific to the Coolify candidate.

Create a normal Git-based Docker Compose Application in the owner-provided
Coolify project/environment. Set Base Directory to the repository root and
Compose Location to `docker-compose.kernel-coolify.yml`; keep normal Coolify
deployment mode enabled so Coolify can add managed routing/network labels. In
Domains, route `https://hub.kokonut.network:8099` to service `app` and
`https://auth.kokonut.network:80` to service `proxy`. Coolify's Traefik handles
public TLS; the internal Caddy site uses HTTP only for the ZITADEL upstreams.
Enter every required Compose value and secret in the Coolify environment/secret
store, including `KOKONUT_KERNEL_DOMAIN=hub.kokonut.network`,
`KOKONUT_ZITADEL_DOMAIN=auth.kokonut.network`, and
`KOKONUT_KERNEL_HTTPS_PORT=443`. Never commit secret values.

When an external proxy terminates public TLS, start ZITADEL with
`--tlsMode external`. `ExternalSecure=true` and forwarded headers alone do not
replace this mode; ZITADEL uses external mode to generate HTTPS API and login
URLs while listening on internal plain HTTP. See ZITADEL's [TLS modes](https://zitadel.com/docs/self-hosting/manage/tls_modes)
and [reverse-proxy guidance](https://zitadel.com/docs/self-hosting/manage/reverseproxy/reverse_proxy).

For the initial database and identity bootstrap, leave `COMPOSE_PROFILES`
unset: Compose starts PostgreSQL and ZITADEL without the Gateway or worker.
After internal ZITADEL readiness is confirmed, set
`COMPOSE_PROFILES=identity-edge` to start the private HTTP-only Caddy route for
`auth.kokonut.network`; this profile does not start the Gateway, worker, or
migration/role bootstrap. Map the Coolify `auth` domain to service `proxy` on
port 80. The `auth` record can be cut over independently once that route is
healthy. If `hub` still points to Baserow or another service, first save the
exact existing record as the temporary rollback target. Configure the Coolify
`app` domain without deploying it. Once the candidate source, runtime health,
and route mapping are ready, replace `hub` with a DNS-only A record to the VPS.
This short, reversible cutover lets Traefik issue its trusted origin
certificate and supports direct Gateway acceptance before Cloudflare proxying.
If origin routing or TLS fails, restore the saved CNAME. Before enabling the
Cloudflare proxy, verify the certificate directly with the intended hostname.
When the zone's default SSL mode is Flexible, add a `http_config_settings`
Configuration Rule matching `http.host eq "hub.kokonut.network"` with
`action: "set_config"` and `action_parameters.ssl: "strict"`; this avoids
changing the zone-wide mode and prevents HTTPS redirect loops. Then enable
proxying, deploy the Worker routes, and verify `/health`, `/ops`, `/field`,
`/governance`, and same-origin `/operator/*`. Retire Baserow only after the
candidate route is accepted; no alternate Baserow hostname is required. From
the VPS, set local shell variables to the
Compose project name, generated Compose file, and generated environment file
for this specific Coolify resource; do not guess these values or print the
environment file. Run the ordered schema migration and the explicit role
bootstrap against that same project:

```sh
docker compose --project-name "$KOKONUT_COOLIFY_PROJECT" \
  --env-file "$KOKONUT_COOLIFY_ENV_FILE" \
  --file "$KOKONUT_COOLIFY_COMPOSE_FILE" \
  --profile runtime-admin run --rm runtime-role-bootstrap \
  python3 -m services.migration migrate --schemas-only

docker compose --project-name "$KOKONUT_COOLIFY_PROJECT" \
  --env-file "$KOKONUT_COOLIFY_ENV_FILE" \
  --file "$KOKONUT_COOLIFY_COMPOSE_FILE" \
  --profile runtime-admin run --rm runtime-role-bootstrap
```

Then set Docker Compose's [`COMPOSE_PROFILES`](https://docs.docker.com/compose/how-tos/environment-variables/envvars/)
to `identity-edge,runtime` in the Coolify environment and redeploy to start the
Gateway and worker alongside the already isolated ZITADEL routing proxy. This
staged sequence preserves the reviewed migration/bootstrap boundary; the
renderer does not run migrations or provision database roles. Confirm Coolify's
effective Compose and project name before running the one-shot commands.
Coolify's normal Git-based Compose path
supports a checked-in Compose location, per-service domains, and generated
proxy networking; review its [Compose deployment guide](https://coolify.io/docs/applications/builds/docker-compose)
and [networking model](https://coolify.io/docs/core/networking-in-coolify).
Candidate HTTPS, identity, report/provider parity, recovery, and browser
acceptance remain separate gates; rendering this manifest is not deployment or
candidate acceptance.

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
