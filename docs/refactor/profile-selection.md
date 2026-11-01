# Kernel candidate command planner

> **Status reference:** This page documents the planner's current source-level
> options and Compose selections. It is not a deployment or rollout ledger.
> Acceptance snapshots elsewhere on this page and in linked records are dated
> evidence; they do not establish the state of a local or production target.
> For present gates, current migration source, and deployment limits, see the
> [current refactor status and implementation guide](current-state-and-implementation.md).

`python3 scripts/kernel-profile.py PROFILE` prints a shell-quoted Compose
command with absolute manifest paths and the explicit isolated candidate project.
It does not invoke Docker, load secrets, inspect containers, migrate data, or
certify any profile. Its default action is `config --quiet`, avoiding resolved
configuration output containing credentials. The printed command uses
`--env-file /dev/null` to prevent implicit plaintext `.env` loading; export
required values through the encrypted-secrets loader before executing it.
This POSIX planner is not a Windows deployment entry point.

`--target-platform` declares linux/amd64 (default) or linux/arm64. For ARM64,
the planner appends `docker-compose.kernel-arm64.yml`, selects the custom
PostgreSQL/PostGIS 16 image, and uses the distinct project
`kokonut-kernel-candidate-arm64`; this keeps its database volume separate from
the AMD64 candidate. The standard profile also appends the ARM64 worker
override. Current ARM64 command selection supports core, minimal, edge, standard, and
analytics. The HTTPS proxy, Gateway OIDC application, self-hosted ZITADEL
profile, gRPC, MQTT, HTTP sensor receiver, and Directus adapter are also
selectable on ARM64. ClickHouse analytics is supported as a combined or
separate-worker profile. The app targets and pinned service images have ARM64
build/runtime evidence and dedicated platform overlays. This is software
compatibility evidence under QEMU, not a Raspberry Pi resource/performance
recommendation.
Image environment overrides must preserve the selected architecture.
An earlier 15 October 2026 ARM64 evidence record documents a minimal runtime,
schema replay through migration 402, restore, and short recovery checks under
QEMU. That snapshot is superseded by later schema-replay records and does not
certify Raspberry Pi hardware. See the
[ARM64 profile record](arm64-database.md).

| Selection | Services/configuration | Acceptance remaining |
| --- | --- | --- |
| core | PostgreSQL + combined API/workers with only the selected kernel dependency set | Release CI, full capability parity, upgrade/restore recovery, and target resource acceptance |
| minimal | PostgreSQL + combined API/workers | End-to-end governed workflow, populated-data parity, backup/restore, and operational recovery |
| edge | Minimal + encrypted local media/resource limits | Media failure/recovery, offline/device acceptance, and physical-hardware behavior |
| standard | PostgreSQL + separate API and worker sharing one app image + dedicated runtime-role overlay + loopback Caddy ingress by default; PostgreSQL shared limiter by default | Publish and verify immutable multi-architecture images, current-target ordered migration/role rollout, worker progress monitoring, public ingress/TLS and trusted-proxy policy, backups, and recovery acceptance |
| standard --edge | Standard plus Edge local-media and resource overlays. The media key/provider and private-media volume are API-only; resource limits apply to PostgreSQL and the API without changing the worker command. | Standard gates plus local-media key provisioning and storage recovery; worker sizing remains separate. No physical Raspberry Pi acceptance is claimed. |
| analytics | Minimal + private ClickHouse | Schema bootstrap, projection parity, and outage/rebuild acceptance |
| analytics --separate-workers | Standard + ClickHouse settings for both roles | Standard gates plus worker analytics parity and recovery |
| scale | Rejected with an explanation | Shared rate limits, replica/failover behavior, recovery, and measured sizing |

Standard now matches the source architecture plan by including the Caddy proxy
overlay once by default. Its host ports are loopback-bound and its default
`localhost` certificate is for development, not public TLS. To use an
externally managed ingress, select `standard --no-proxy`; preserve the HTTPS
origin and callback behavior required by browser sessions. Public binding,
public TLS, DNS, firewall, and multi-hop trusted-proxy policy still require
acceptance. The Gateway ignores forwarded headers by default.

Standard also selects the runtime-role Compose overlay. It requires distinct
`KOKONUT_RUNTIME_USER` and `KOKONUT_RUNTIME_PASSWORD` values for both app and
worker, and each supervisor checks that its database login is not privileged,
does not own the database, and cannot become a database-owner member before
starting children. Load the encrypted environment, then execute the planner
actions and their printed commands in this order:

1. `python3 scripts/kernel-profile.py standard --action database-up` starts
   only PostgreSQL.
2. `python3 scripts/kernel-profile.py standard --action migrate` prints the
   Python command for the complete ordered schema migration. Run that command
   as the database owner.
3. `python3 scripts/kernel-profile.py standard --action bootstrap-runtime-role`
   provisions the distinct runtime and operator-auth logins.
4. `python3 scripts/kernel-profile.py standard --action up` starts the app,
   worker, and selected ingress.

The bootstrap applies compatibility DML only when it creates the runtime
login. Later bootstrap runs preserve existing relation grants and reapply
migration-owned denials without widening access to newly created tables. It is
not a routine restart action. The planner actions print commands and do not
execute them.

To retain the API/worker split while selecting Edge's local-media provider and
resource limits, use `standard --edge`. The planner appends the Edge overlay
after Standard's API/worker and runtime-role overlays. Load
`MOBILE_MEDIA_LOCAL_KEY` through the encrypted environment before resolving or
starting the composition. The private-media settings apply only to the API;
the worker receives no media key, volume, or copied API/database resource
limits. This is Compose/source capability, not physical-device, power-loss, or
production acceptance.

`standard --action release-up` is the immutable-image deployment path. It
requires `KOKONUT_KERNEL_APP_IMAGE` to be a registry reference pinned to a
SHA-256 digest; the API and worker use that same image. With `--oidc` or
`--zitadel`, it also requires a digest-pinned `KOKONUT_KERNEL_OIDC_IMAGE`.
ZITADEL defaults are digest-pinned, and any image override must also use a
digest. The selected application reference must resolve to an OCI manifest
index that includes the requested platform; verify that against the release
record because the planner validates digest syntax, not registry contents or
architecture. The action prints `pull && up -d --no-build --wait --wait-timeout
300` and does not run it. It rejects `--grpc`, `--http-sensors`, `--directus`,
`--mqtt`, and `--sensor-anomaly-ml`, whose source overlays still need their own
published immutable-image contracts. The source-oriented `build` and `up`
actions remain available for development and acceptance.

Migration numbers referenced below (including 371–373) identify when specific
features were introduced. They are not a current target's migration status or
a complete deployment instruction. New and existing targets must use the full
ordered checksummed migration runner and inspect that target's ledger.

`core` is an additive opt-in package profile. It does not change `minimal` or
the existing profile defaults. Web3, spreadsheet/S3, and encrypted local-media
dependencies are omitted from core until selected with `--web3`, `--exports`,
or `--local-media`. The local-media overlay still requires the existing
runtime `MOBILE_MEDIA_LOCAL_KEY` from the encrypted environment. The release
gate builds the core base and the composition with all three package overlays
enabled for linux/amd64 and linux/arm64, then checks exact locked package
inventories. Hosted CI acceptance is pending. Even a successful ARM64 OCI build
does not establish Raspberry Pi resource suitability. `--oidc` and `--zitadel`
are rejected with core because the current OIDC application target is built on
the full image.

Add `--proxy`, `--oidc`, `--zitadel`, `--grpc`, `--mqtt`, `--http-sensors`, or
`--directus` explicitly for the corresponding optional overlay. The Standard
profile already includes `--proxy` by default, so `standard --oidc` needs no
redundant proxy flag. Minimal, edge, and analytics need `--proxy` with `--oidc`;
core rejects OIDC because it does not use the required application image. To
replace Standard's Caddy with an external ingress, select
`standard --no-proxy --oidc`; that ingress must provide the browser HTTPS origin
and OIDC callback path.
`--no-proxy` is Standard-only and cannot be combined with `--proxy` or
`--zitadel`. `--zitadel` selects
the proxy, Gateway OIDC client, and self-hosted ZITADEL overlays together. It
uses a separate private PostgreSQL service and exposes its HTTP/2 API and
Login V2 UI only through Caddy. ZITADEL remains absent from minimal and edge
unless selected. These options do not enable providers in unrelated services
or promise capability parity. OIDC and ZITADEL require provider values in the
SOPS-loaded environment; the planner only prints the command and does not read
or expose them. For ARM64, the planner appends explicit overlays for each
verified optional service and analytics profile; registry/build evidence is not
live service acceptance. MQTT requires separately provisioned credentials,
certificates, persistent client identity, and migration 372. Standard/current
scheduler source requires migration 371. Neither migration is applied by this
planner. Read the individual overlay execution records before adoption.

Examples that only print commands (the release example assumes the required
digest-pinned image variables have already been exported):

```sh
python3 scripts/kernel-profile.py minimal
python3 scripts/kernel-profile.py core --action config
python3 scripts/kernel-profile.py core --web3 --exports --local-media --action config
python3 scripts/kernel-profile.py standard --action build
python3 scripts/kernel-profile.py standard --action bootstrap-runtime-role
python3 scripts/kernel-profile.py standard --edge --action config
python3 scripts/kernel-profile.py standard --no-proxy --action config
python3 scripts/kernel-profile.py standard --oidc --action config
python3 scripts/kernel-profile.py standard --action release-up
python3 scripts/kernel-profile.py analytics --separate-workers --action config
python3 scripts/kernel-profile.py edge --mqtt --action up
python3 scripts/kernel-profile.py minimal --proxy --oidc --action config
python3 scripts/kernel-profile.py minimal --zitadel --action config
python3 scripts/kernel-profile.py standard --target-platform linux/arm64 --zitadel --action config
python3 scripts/kernel-profile.py minimal --target-platform linux/arm64 --grpc --action config
python3 scripts/kernel-profile.py edge --target-platform linux/arm64 --mqtt --action config
```

Review the printed command, load encrypted secrets, and execute it separately
after the applicable acceptance gates. `--action up` prints an operational
command; it does not execute it. Do not pipe the planner into a shell as an
approval or migration workaround. No down, volume-removal, scaling, migration,
or orphan-removal action is exposed.

Profile changes can leave old overlay services running as orphans. Review and
stop them explicitly before cutover, allowing active leases to settle. Preserve
database, broker, certificate, and private-media volumes. Keep legacy services
stopped; the planner never selects legacy manifests or legacy project names.

Planner and Compose profile contract checks include minimal, edge, standard,
analytics, portability, external OIDC, and optional self-hosted ZITADEL
selections. The planner only builds a command string; no deployment, secret
read, or profile cutover is performed. Runtime acceptance remains separate
from command selection.
