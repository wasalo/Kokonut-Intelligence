# Scripts

Operational scripts for the Kokonut Intelligence platform. All shell scripts use `set -euo pipefail` for strict error handling.

## Platform Setup & Data

| Script | Purpose | Context |
|--------|---------|---------|
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
| `health-check.sh` | Verify all services healthy (PostgreSQL, Directus, ClickHouse, Metabase, Docker, disk/memory). Supports `--json` and `--alert`. | Manual, cron, programmatic |
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
- `metabase`
