# Scripts

Operational scripts for the Kokonut Intelligence platform. All shell scripts use `set -euo pipefail` for strict error handling.

## Platform Setup & Data

| Script | Purpose | Context |
|--------|---------|---------|
| `kernel-inventory.py` | Static Kernel capability/dependency inventory without importing services or reading secrets | Manual |
| `kernel-profile.py` | Print an explicit Kernel candidate Compose command; see docs/refactor/profile-selection.md | Manual |
| `kernel-portability.py` | Print isolated AMD64/ARM64 evaluation build/readiness commands; see docs/refactor/portability-database.md | Manual |
| `check-provider-boundaries.py` | Reject optional vendor imports outside declared adapters | CI, manual |
| `check-requirement-groups.py` | Keep candidate groups aligned with legacy dependency constraints | CI, manual |
| `setup.sh` | First-run bootstrap: prerequisites check, `.env` creation, data directories, infrastructure startup | Manual |
| `load-secrets.sh` | Decrypt `.env.sops` via SOPS/age and export into current shell. **Must be sourced**, not executed. | Manual |
| `seed.sh` | Apply PostgreSQL schema migrations + ClickHouse schemas + Directus permissions + curated seeds | Manual, CI |
| `seed-pilot.sh` | Load pilot farm data (`*_pilot_*.sql` seeds + CRISP + alignment + dashboards) | Manual, CI |
| `seed-metabase.sh` | Configure Metabase with database connection (prints manual setup instructions) | Manual |

## Metric Computation

| Script | Purpose | Context |
|--------|---------|---------|
| `compute-metrics.sh` | Compute all metrics for all locations via host Python or one-shot `kokonut-worker` container | Manual, CI |

## Verification & Testing

| Script | Purpose | Context |
|--------|---------|---------|
| `verify-platform.sh` | Validate platform definition of done via `tests/test_platform_done.py` | Manual |
| `verify-ci-toolchain.sh` | Verify all required CI tools are installed (python3, node, npm, forge, slither, aderyn, semgrep, ruff, pip-audit) | CI |
| `verify-clean-bootstrap.sh` | Create temp database, apply schema-only migrations, drop it. Validates clean bootstrap. | CI (via `ci-check.sh`) |
| `verify-full-test-suite.sh` | Run full pytest suite with unexpected-skip detection | CI |
| `verify-local-test-suite.sh` | Start local Compose databases, wait for readiness, run full test suite | Manual |

## CI Pipeline

| Script | Purpose | Context |
|--------|---------|---------|
| `ci-check.sh` | Fast-fail CI gate: Python imports, CLI parsers, TypeScript build, clean bootstrap | CI |
| `static-analysis.sh` | Slither (Solidity), Aderyn (Solidity), Semgrep (Python + Solidity) | CI |
| `check-tracked-secrets.sh` | Scan Git-tracked files for private keys and token patterns | CI |
| `check-image-digests.sh` | Fail if Dockerfile `FROM` or Compose `image:` is not pinned by `@sha256` digest | CI |
| `check-python-runtime.py` | Validate Python >= 3.11 and OpenSSL availability | CI (via `ci-check.sh`) |

## Monitoring & Operations

| Script | Purpose | Context |
|--------|---------|---------|
| `health-check.sh` | Verify core services (PostgreSQL, Directus, ClickHouse, Docker, disk/memory); optional Metabase checks require `HEALTH_CHECK_METABASE=true`. Supports `--json` and `--alert`. | Manual, cron, programmatic |
| `health-alert.sh` | Cron wrapper for `health-check.sh` — quiet on success, sends webhook/email alerts on failure | Cron (`*/5 * * * *`) |
| `backup.sh` | Create an encrypted, checksum-verified PostgreSQL + ClickHouse upgrade checkpoint | Manual/upgrade workflow |
| `verify-backup.sh` | Validate checkpoint manifest, files, sizes, and SHA-256 checksums | Manual/restore workflow |
| `restore.sh` | Restore an explicit encrypted checkpoint after operator confirmation | Manual |
| `rollback.sh` | Stop application services, restore a checkpoint, restart, and verify | Manual |
| `upgrade.sh` | Plan and apply a checked-out release with backup, migration, health, and verification gates | Manual |
| `schema-snapshot.sh` | Export Directus schema as JSON snapshot via API | Manual |

## Development & Analysis

| Script | Purpose | Context |
|--------|---------|---------|
| `check-er-model.sh` | Read-only ER risk report via `services.schema_introspection` | Manual |
| `render-workflow-specs.py` | Render workflow specifications into Markdown + Mermaid in `docs/` | Manual |
| `baserow_reconciliation_dry_run.py` | Offline, no-write Baserow snapshot/manifest/crosswalk preflight; emits aggregate-only JSON | Manual, local-only |
| `baserow_reconciliation_projection.py` | Explicit allow-list projection into isolated scratch PostgreSQL; verifies constraints and always rolls back; never imports to live KI | Manual, local-only |
| `sandbox-setup.sh` | Bootstrap developer sandbox: Directus auth, sandbox role, Metabase dashboards, sample data | Manual (Docker entrypoint) |
| `fork-rehearsal.sh` | Fork Chiado chain, run Solidity tests, build contracts, dry-run deployment, gas snapshots | Manual |

## Cross-References

Scripts that call other scripts:

```
seed.sh ──────→ load-secrets.sh (source)
seed-pilot.sh → load-secrets.sh (source)
health-check.sh → load-secrets.sh (source)
health-alert.sh → health-check.sh
ci-check.sh ──→ check-python-runtime.py
              ──→ verify-clean-bootstrap.sh
verify-local-test-suite.sh → verify-full-test-suite.sh
schema-snapshot.sh → load-secrets.sh (source)
seed-metabase.sh → load-secrets.sh (source)
backup.sh ────→ load-secrets.sh (source)
```

## Service Names

All scripts use Docker Compose service names (not container names):
- `database` (PostgreSQL)
- `clickhouse`
- `directus`
- `metabase` (only when the `metabase` Compose profile is enabled)

### Scoped Kernel recovery preparation

`bash scripts/kernel-checkpoint.sh SOURCE_CONTAINER NEW_DIRECTORY AGE_RECIPIENT`
creates an encrypted single-database checkpoint without requiring ClickHouse.
It excludes roles/grants, other databases and provider/media storage. See
[scope, isolated restore and remaining gates](../docs/refactor/recovery-preparation.md).

`python3 scripts/kernel-legacy-archive.py --destination NEW_DIRECTORY --recipient AGE_PUBLIC_RECIPIENT`
streams all attached stopped legacy volumes and selected config into an encrypted
archive. See [scope and staging restore](../docs/refactor/legacy-storage-preservation.md).

`bash scripts/kernel-legacy-logical-checkpoint.sh NEW_DIRECTORY AGE_PUBLIC_RECIPIENT`
captures all non-template databases and globals from the isolated no-network legacy
PostgreSQL clone. See [inventory and restore limits](../docs/refactor/provider-clone-inventory.md).

`python3 scripts/kernel-broker-inventory.py PATH_TO_PERSISTENCE_COPY` counts only
Mosquitto v6 chunk framing without printing payloads. Prefer a read-only mount of
the stopped original snapshot; see [limits and evidence](../docs/refactor/analytics-broker-recovery.md).

Local-media recovery commands: `kernel-media-checkpoint.py` and
`kernel-media-restore.py`. Require quiesced owner-controlled storage and a new
restore directory. See [full command syntax, key custody and acceptance gaps](../docs/refactor/work-media-recovery.md).

`python3 scripts/kernel-recovery-fixture.py [--apply]` targets only the dedicated
recovery fixture deployment. It preserves migration history and inserts disabled
synthetic work transactionally. [Setup and remaining gates](../docs/refactor/recovery-fixture-setup.md).

`kernel-recovery-media.py` authenticates existing synthetic local media before
registering references on the guarded recovery fixture. See [required inputs and
limits](../docs/refactor/recovery-media-fixture.md). No enrollment/device token is minted.

`kernel-recovery-event-checks.sh` guards and exercises the retained synthetic event
fixture with controlled handler outcomes. It mutates work state; preserve its
checkpoint first. See [recovery evidence](../docs/refactor/builds/2026-10-10-recovery/fixture-events.json).

Outbox recovery operators require actor/reason and schema 374. See [audited operations](../docs/refactor/outbox-operator-audit.md).

`scripts/fixtures/kernel-recovery-sensor-e2e-verify.py` performs a read-only
verification of the retained single-reading recovery slice across PostgreSQL,
the outbox, ClickHouse raw rows and sensor-v3 daily summary. It requires the
isolated recovery fixture and does not create or repair rows. See [scope and
known visibility observation](../docs/refactor/sensor-entrypoint-recovery.md).
