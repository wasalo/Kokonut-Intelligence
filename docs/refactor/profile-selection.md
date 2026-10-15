# Kernel candidate command planner

`python3 scripts/kernel-profile.py PROFILE` prints a shell-quoted Compose
command with absolute manifest paths and the explicit isolated candidate project.
It does not invoke Docker, load secrets, inspect containers, migrate data, or
certify any profile. Its default action is `config --quiet`, avoiding resolved
configuration output containing credentials. The printed command uses
`--env-file /dev/null` to prevent implicit plaintext `.env` loading; export
required values through the encrypted-secrets loader before executing it.
This POSIX planner is not a Windows deployment entry point.

`--target-platform` declares linux/amd64 (default) or linux/arm64. ARM64 is
currently rejected because the exact pinned PostGIS image is AMD64-only; see
the [database blocker](arm64-database.md). The setting does not detect hardware
or force a Docker platform, and manual Compose commands bypass the guard.

| Selection | Services/configuration | Acceptance remaining |
| --- | --- | --- |
| minimal | PostgreSQL + combined API/workers | Capability parity and recovery |
| edge | Minimal + encrypted local media/resource limits | ARM64/Pi hardware and storage recovery |
| standard | PostgreSQL + separate API and worker; PostgreSQL shared limiter by default | Migration 373, role cutover, and worker progress monitoring |
| analytics | Minimal + private ClickHouse | Schema bootstrap and projection parity |
| analytics --separate-workers | Standard + ClickHouse settings for both roles | Same gates plus worker analytics parity |
| scale | Rejected with an explanation | Multi-host failover, replica concurrency, recovery and measured sizing |

Add `--proxy`, `--oidc`, `--zitadel`, `--grpc`, `--mqtt`, or `--http-sensors`
explicitly for the corresponding optional overlay. `--oidc` requires `--proxy`
so Secure operator-session cookies use the HTTPS origin. `--zitadel` selects
the proxy, Gateway OIDC client, and self-hosted ZITADEL overlays together. It
uses a separate private PostgreSQL service and exposes its HTTP/2 API and
Login V2 UI only through Caddy. ZITADEL remains absent from minimal and edge
unless selected. These options do not enable providers in unrelated services
or promise capability parity. OIDC and ZITADEL require provider values in the
SOPS-loaded environment; the planner only prints the command and does not read
or expose them. MQTT requires separately provisioned credentials,
certificates, persistent client identity, and migration 372. Standard/current
scheduler source requires migration 371. Neither migration is applied by this
planner. Read the individual overlay execution records before adoption.

Examples that only print commands:

```sh
python3 scripts/kernel-profile.py minimal
python3 scripts/kernel-profile.py standard --proxy --action build
python3 scripts/kernel-profile.py analytics --separate-workers --action config
python3 scripts/kernel-profile.py edge --mqtt --action up
python3 scripts/kernel-profile.py minimal --proxy --oidc --action config
python3 scripts/kernel-profile.py minimal --zitadel --action config
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
