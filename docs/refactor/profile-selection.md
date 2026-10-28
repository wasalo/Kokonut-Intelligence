# Kernel candidate command planner

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
Current-source minimal ARM64 runtime,
schema replay through migration 402, restore, and short recovery checks now pass
under QEMU; this does not certify Raspberry Pi hardware. See the
[ARM64 profile record](arm64-database.md).

| Selection | Services/configuration | Acceptance remaining |
| --- | --- | --- |
| core | PostgreSQL + combined API/workers with only the hash-locked kernel runtime | Capability parity, multi-arch OCI build, and recovery |
| minimal | PostgreSQL + combined API/workers | Capability parity and recovery |
| edge | Minimal + encrypted local media/resource limits | Media/storage recovery and physical-device behavior |
| standard | PostgreSQL + separate API and worker; PostgreSQL shared limiter by default | Migration 373, role cutover, and worker progress monitoring |
| analytics | Minimal + private ClickHouse | Schema bootstrap and projection parity |
| analytics --separate-workers | Standard + ClickHouse settings for both roles | Same gates plus worker analytics parity |
| scale | Rejected with an explanation | Multi-host failover, replica concurrency, recovery and measured sizing |

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
`--directus` explicitly for the corresponding optional overlay. `--oidc` requires `--proxy`
so Secure operator-session cookies use the HTTPS origin. `--zitadel` selects
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

Examples that only print commands:

```sh
python3 scripts/kernel-profile.py minimal
python3 scripts/kernel-profile.py core --action config
python3 scripts/kernel-profile.py core --web3 --exports --local-media --action config
python3 scripts/kernel-profile.py standard --proxy --action build
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
