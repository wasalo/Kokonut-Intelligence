# Deployment topology

This document describes the repository's current deployment definitions. A
workflow, Compose manifest, image build, or passing health check is not by itself
evidence that an environment is deployed, that external credentials are
configured, or that the Kernel has passed its production gates. See the
[current refactor status and implementation guide](refactor/current-state-and-implementation.md)
for the accepted state and open gates.

## Compose isolation

The repository has two different Compose families:

| Family | Manifests | Purpose | Data boundary |
|---|---|---|---|
| Legacy integration stack | `docker-compose.yml` and legacy overlays | Existing integration and compatibility workflows | Do not combine with Kernel manifests or assume its volumes are interchangeable |
| Kernel candidate | `docker-compose.kernel-candidate.yml` plus selected `docker-compose.kernel-*.yml` overlays | Isolated Kernel development and acceptance | Separate project and PostgreSQL volume; no automatic migration, seed, or legacy-data copy |

Always set an explicit project name. The Kernel profile planner defaults to the
candidate project name and prints `--project-directory`, `--env-file /dev/null`,
and absolute manifest paths; it does not run Docker commands or change existing
projects. Read the printed command before executing it. Never use implicit
directory-derived project names on a shared host.

## Current environments

| Environment | Definition | What the source establishes | What it does not establish |
|---|---|---|---|
| Local Kernel candidate | `docker-compose.kernel-candidate.yml`; planner profiles `core`, `minimal`, `edge`, `standard`, `analytics`, `scale` | Candidate app binds to `127.0.0.1:8098` by default; candidate PostgreSQL stays private; selected optional services are composed by explicit overlays | Production readiness, full legacy capability parity, live provider readiness, public ingress acceptance, or Raspberry Pi hardware suitability |
| Standard candidate | Candidate plus `docker-compose.kernel-standard.yml` | API and worker run as separate processes against the candidate database; worker progress is recorded durably, not represented by an HTTP health endpoint | Provisioned least-privilege runtime roles, 24-hour recovery/scale acceptance, or verified production sizing unless separately evidenced in the refactor ledger |
| CI | `.github/workflows/ci.yml`, `ubuntu-24.04`, Compose project `ki-ci` | CI triggers for PRs/pushes to `main` and `develop`; test database ports use runner-local high ports | Production deployment or customer data handling |
| Staging workflow | `.github/workflows/deploy-staging.yml`, self-hosted labels `ki-staging`, project `ki-staging` | Manual dispatch from `main` with `confirm=yes`; workflow currently hardcodes `DEPLOY_STAGING_ENABLED=no` and exits before deployment | An active staging deployment or a ready staging cutover |
| Production workflow | `.github/workflows/deploy-production.yml`, protected GitHub environment `production` | Manual dispatch from `main` with `confirm=yes`; validates SSH host/key/known-host configuration and runs `deploy/scripts/deploy-production.sh` | Reachable/healthy `ki-prod` host, configured repository secrets, a successful deployment, or Kernel production acceptance |

The workflow file is the authoritative description of its triggers and gates.
For the current deployment procedure, inspect the workflow and deploy script
together; do not infer runtime state from this table.

## Kernel profile topology

| Profile or overlay | Services/behavior | Default exposure |
|---|---|---|
| `minimal` | PostgreSQL/PostGIS and one native app process (API plus enabled workers) | App on loopback port `8098`; database private |
| `standard` | Native API plus separate worker process | API on loopback port `8098`; worker has no public HTTP port |
| `edge` | Minimal plus selected edge resource/media configuration | Local/private defaults; device/public acceptance is separate |
| `analytics` | ClickHouse analytics adapter with the selected app topology | ClickHouse remains on the private Compose network |
| `--proxy` | Adds Caddy and proxy configuration | Loopback ports `8088`/`8448` by default; public bind is explicit |
| `--directus` | Adds Directus compatibility/admin adapter and its role bootstrap | Loopback-only default port `18055` |
| `--mqtt` | Adds Mosquitto and sensor subscriber | Local bind; certificate/client provisioning is required |
| `--grpc` | Adds the gRPC transport overlay | Private Compose network by default |
| `--oidc` / `--zitadel` | Adds HTTPS-backed browser OIDC or self-hosted ZITADEL | Requires explicit HTTPS, issuer/client settings, and secrets |
| `scale` | Planner rejects this selection | No scale deployment is generated |

Exact options can change with the planner. Inspect `python3 scripts/kernel-profile.py
--help` and use its generated config as the current source. Optional Directus,
ClickHouse, Metabase, Prefect, Redis, Mosquitto, gRPC, and Caddy are not all
required Kernel components. Metabase remains available in the legacy Compose
profile and is not a standard candidate service.

ARM64/QEMU builds and database replay are software portability checks. There is
no physical Raspberry Pi acceptance evidence, so this topology makes no
hardware suitability claim.

## Port and network policy

The candidate base does not publish PostgreSQL to the host. If local tooling
requires a host connection, the separate development-only
`docker-compose.kernel-local-db.yml` publishes the database on loopback port
`5433` by default. Do not use that override for production. The proxy overlay
defaults to `127.0.0.1:8088` and `127.0.0.1:8448`. Other optional overlay ports
are defined in their manifests and should be inspected before selection.

CI's loopback test ports are `15432` (PostgreSQL), `18123` (ClickHouse), `18055`
(Directus), `18099` (Gateway), and `50052` (gRPC), as defined by
`.github/workflows/ci.yml`. They exist on the ephemeral CI runner, not as public
service endpoints.

Rule: do not publish a database or change a loopback bind to `0.0.0.0` to work
around a local port conflict. Use Compose service names from containers or
choose an explicit unused loopback port in a reviewed development override.

## Secret handling

- Use the repository SOPS loader for encrypted local environment values.
- Never commit plaintext `.env` files or place secrets in command examples,
  issue text, or generated Compose output.
- The profile planner uses `--env-file /dev/null` so Compose does not silently
  load a plaintext `.env`; required variables must already be available in the
  process environment when the reviewed command is run.
- Production workflows use protected GitHub environment values and SSH
  host-key verification; confirm the configured environment before dispatch.

## Promotion and recovery boundaries

Feature work flows through `develop`; reviewed releases are promoted to `main`
under the repository rules. Current deployment workflows target `main`, and
the staging workflow is intentionally disabled. A Kernel promotion workflow
and accepted production cutover remain separate work. Do not combine the
legacy and Kernel manifests, reset one project to another's commit, remove
volumes, or route public traffic until the relevant migration, backup/restore,
authorization, provider, observability, ingress, and recovery gates are closed.
