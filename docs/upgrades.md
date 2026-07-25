# Platform Upgrades

Kokonut Intelligence upgrades are operator-controlled, forward-only database
changes deployed during a Docker Compose maintenance window.

## Release Identity

The canonical release version is stored in `VERSION`. Containers expose the
version and `KOKONUT_GIT_SHA` through gateway `/health` and the Python health
contract. Releases should be tagged only after CI passes and the tag matches
`VERSION`.

## Normal Upgrade

Check out the intended release first. The upgrade command does not run `git
pull` and refuses a dirty working tree.

```bash
scripts/upgrade.sh --plan
scripts/upgrade.sh --yes
```

The command validates migration sources, displays pending migrations, creates a
verified encrypted checkpoint, builds images, applies migrations, applies
idempotent reference setup, restarts Compose services, runs health checks, and
executes `verify-platform.sh`.

Pilot data is not loaded by default. Metric recomputation remains a separate,
operator-controlled action.

## Checkpoints And Rollback

Every normal upgrade creates a checkpoint under `backups/`. The checkpoint has
a manifest and SHA-256 checksums. PostgreSQL uses custom-format archives and
ClickHouse uses encrypted schema and table exports.

Rollback is never automatic. First preserve logs and inspect the failure, then
run the explicit operator-confirmed command:

```bash
scripts/rollback.sh --checkpoint backups/<checkpoint-id> --confirm
```

Restore procedures must be tested in disposable infrastructure before relying
on them in production.

## Compose Availability Model

Ordinary Docker Compose is not a rolling deployment orchestrator. The current
upgrade process therefore has a maintenance window. `deploy.update_config`
settings must not be treated as zero-downtime behavior outside Docker Swarm.

Schema changes use expand-contract discipline:

1. Add compatible schema structures.
2. Deploy code that can use both old and new structures.
3. Migrate data if needed.
4. Remove deprecated structures in a later release.

## Seed Boundaries

- `services.migration`: tracked PostgreSQL migrations.
- `scripts/seed.sh`: bootstrap and full reference setup.
- `scripts/seed.sh --reference-only`: reference setup during upgrades.
- `scripts/seed-pilot.sh`: optional pilot/demo data, including the pilot organization.
- `scripts/compute-metrics.sh`: explicit derived draft metric computation.
