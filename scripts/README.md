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
| `check-sdk-schema-parity.py` | Verify Python and TypeScript models include canonical columns for selected operational tables | CI, manual |
| `setup.sh` | First-run bootstrap: prerequisites check, `.env` creation, data directories, infrastructure startup | Manual |
| `load-secrets.sh` | Decrypt `.env.sops` via SOPS/age and export into current shell. **Must be sourced**, not executed. | Manual |
| `seed.sh` | Bootstrap locked placeholders for optional worker/runtime role names, wait for the final PostgreSQL TCP listener, then apply PostgreSQL schema migrations + ClickHouse schemas + Directus permissions + curated seeds | Manual, CI |
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
| `bootstrap-optional-roles.sql` | Idempotently create locked `NOLOGIN` placeholders for optional runtime/worker roles referenced by signed-worker migration revocations; preserve existing roles | `seed.sh`, `verify-clean-bootstrap.sh` |
| `verify-clean-bootstrap.sh` | Create temp database, apply schema-only migrations, drop it. Uses the same locked optional-role bootstrap as `seed.sh`, preserving already-provisioned roles. Optional `KOKONUT_BOOTSTRAP_COMPOSE_PROJECT` and `KOKONUT_BOOTSTRAP_COMPOSE_FILE` select an isolated Compose target; set `KOKONUT_BOOTSTRAP_START_DATABASE=true` and `KOKONUT_BOOTSTRAP_REMOVE_PROJECT=true` to start and remove a disposable project. | CI (via `ci-check.sh`), isolated acceptance |
| `check-directus-role-disposable.py` | Provision and replay the Directus DML-only role on a temporary internal-only PostgreSQL instance; check existing/future DML, DDL denial, stale ACL removal, and database isolation; always removes its Compose project and volume. | Isolated acceptance |
| `check-directus-profile-disposable.py` | Build the Directus hook, provision its dedicated role, bootstrap a fresh Kernel database, start the actual optional Directus overlay on loopback, verify health/admin login/runtime DB identity, and remove the complete disposable project and volume. | Isolated acceptance |
| `check-scheduler-engine-reconnect-disposable.py` | Exercise real SchedulerEngine PostgreSQL outage/reconnect, pre-dispatch lease recovery, and post-effect crash/reclaim idempotency with synthetic events on a disposable PostgreSQL 16 container; no provider requests, candidate/legacy access, or retained container. | Isolated acceptance |
| `check-operator-session-role-disposable.py` | Exercise runtime-role bootstrap and migrations 391–396, 398–400, 405, and 417–419, plus migration 432 on disposable PostgreSQL 16/PostGIS; verify mobile/worker ACLs, notification enqueue, and remote-sensing SET ROLE isolation under forced RLS. Synthetic credentials only; removes the container and never connects to candidate or legacy databases. | Isolated acceptance |
| `check-governance-tension-actions-disposable.py` | Apply migration 437 on temporary PostgreSQL 16; verify explicit operator/person bindings, admin-only binding management, exact signed-context scope, idempotent draft intake/submission, reporter ownership, and denial of direct binding/lifecycle writes. Removes its container; never connects to candidate or legacy databases. | Isolated acceptance |
| `check-retention-policy-disposable.py` | Apply migration 401 through the ordered runner to a synthetic pre-migration schema in an internal-only temporary PostgreSQL project; verify policy transitions, audited holds, and hold-aware cleanup. Removes its container, network, and volume; never uses candidate or legacy databases. | Isolated acceptance |
| `check-sensor-anomaly-worker-reads-disposable.py` | Replay migrations 405–412 on isolated PostgreSQL 16; verify signed event/source/location scope, device-rule filtering, metric/history and cooldown results, forced-RLS access, and worker/runtime/auth privilege boundaries. Uses synthetic rows and removes its temporary container; never connects to candidate or legacy databases. | Isolated acceptance |
| `check-sensor-anomaly-alert-write-disposable.py` | Replay migrations 405–413 on isolated PostgreSQL 16; verify signed source/location/rule validation, reserved-receipt transition and duplicate suppression, atomic alert/audit rollback, forced-RLS execution, and worker/runtime/auth privilege boundaries. Uses synthetic rows and removes its temporary container; never connects to candidate or legacy databases. | Isolated acceptance |
| `check-cache-invalidation-worker-disposable.py` | Apply and replay migration 415 on network-isolated PostgreSQL 16; verify signed event/type/location matching, cache-type and location scoping, retry idempotency, forced-RLS policy behavior, and worker direct-table denial. Uses synthetic rows and removes its temporary container; never connects to candidate or legacy databases. | Isolated acceptance |
| `check-ai-summary-review-disposable.py` | Apply/replay migration 521 on disposable PostgreSQL 16; verify exact-location review scope, approval blockers, verified-versus-published lifecycle separation, append-only decisions, request retries, and runtime/Directus privilege boundaries. Uses synthetic rows and removes its temporary container; never connects to candidate or legacy databases. | Isolated acceptance |
| `check-ai-summary-draft-disposable.py` | Apply/replay migrations 521–524 on disposable PostgreSQL 16; verify authenticated requester attribution, bounded exact-location source references, location-linked crop and top-five expense-category references, retry/review manifest access, self-review denial, legacy creator blockers, independent verification lifecycle, append-only source records, and runtime/Directus privilege boundaries. Uses synthetic rows and a network-disabled temporary container; never connects to candidate or legacy databases. | Isolated acceptance |
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
