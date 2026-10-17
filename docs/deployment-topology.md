# Deployment topology

**Invariant (KI-390 lesson):** *Every Compose project MUST pin its project
name (`-p` or `COMPOSE_PROJECT_NAME`). No project may derive its name from
a directory name on a shared host.* A derived name once collided with a
deployed stack and CI's `down -v` recreated that stack's data volumes.

## Environments

| | CI | Staging | Production |
|---|---|---|---|
| Host | GitHub-hosted `ubuntu-24.04` | dedicated self-hosted GitHub Actions runner | dedicated VPS (Coolify + Traefik) |
| Compose project | `ki-ci` | `ki-staging` | `ki-prod` |
| Compose files | yml + ci.yml | yml + staging.yml | yml + prod.yml + traefik.yml |
| Data | disposable | dev/historical ingestion | production |
| Backups | none | nightly local (keep 7) | nightly + off-host (keep 30) |
| Deploy | pull requests and pushes to `main` | manual dispatch from `main`, blocked by a disabled workflow flag | manual promotion from `main` (`DEPLOY_CONFIRM=yes`) |
| Public exposure | none | loopback only | 80/443 via Traefik |

## Port allocation

| Range | Owner | Notes |
|---|---|---|
| 15432 / 18123 | CI postgres / clickhouse | loopback, high ports to avoid host conflicts |
| 18055 / 18099 / 50052 | CI directus / gateway / grpc | loopback |
| 18056 / 18098 / 50053 | staging directus / gateway / grpc | loopback |
| 13001 | optional staging Metabase profile | loopback; only when explicitly enabled |
| 80 / 443 | production Traefik only | public |

Rule: new environments take unused high ports and document them here.

## Deploy flow

```
pull request ─┐
push main ────┴──► CI (ki-ci) ──► merge main ──► Staging (manual, paused)
                                                  │
                                                  └──► Production (manual dispatch,
                                                       protected environment,
                                                       DEPLOY_CONFIRM=yes)
```

## Secrets

- Per-environment SOPS-encrypted env files (`*.sops`) committed to the repo
- One age keypair per environment; private keys live only on the target host
- `.sops.yaml` per environment directory pins the recipient
- Plaintext env filenames are gitignored; plaintext never leaves a
  decryption pipe or a 0600 temp file cleaned by trap
