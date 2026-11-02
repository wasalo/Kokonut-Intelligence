# CI gates

The active workflow is `.github/workflows/ci.yml`. It runs on pull requests and
pushes targeting `main` and `develop`, plus manual dispatch. All jobs use
GitHub-hosted `ubuntu-24.04`; the database-backed integration job uses the
isolated Compose project `ki-ci` and runner-local high ports.

The workflow has dependency-free preflight followed by three gates:

| Job | What it checks | Limit |
|---|---|---:|
| `preflight` | Release-input hashes and fast source inventories before expensive work starts. | 10 minutes |
| `source-checks` | Ruff security scan, Python dependency audit, fast-fail imports/CLI/hooks, static analysis, Solidity, and Directus hook tests through `scripts/run-github-ci.sh --source-only`. | 45 minutes |
| `integration-ci` | Strict database-backed integration and full test checks through `scripts/run-github-ci.sh --integration-only`; PostgreSQL, ClickHouse, and related services run under `ki-ci`. | 90 minutes |
| `kernel-image` | Locked AMD64 and ARM64 Kernel image builds and image checks. | 45 minutes |

The source, integration, and image jobs run in parallel after preflight. The
required `CI / ci` status is an aggregate that waits for preflight and every
gate, then fails if any result is not `success`. This keeps the status check
stable while exposing the failing stage directly. CI builds test images and
does not publish or deploy them.

CI is fail-closed: missing required tools, database connectivity failures,
missing schema objects, and infrastructure-related skips do not count as
successful acceptance. Review the workflow and scripts for exact tool versions
and current job steps rather than relying on a copied list here.

### Finding logs and failure diagnostics

Every run exposes per-job, per-step logs in the GitHub Actions run page. Open
the failed job and expand the failed step first. On failure, the workflow also
uploads `kokonut-ci-compose-diagnostics` for integration failures and
`kokonut-ci-source-diagnostics` for source-check failures; these artifacts are
retained for seven days. Artifacts supplement the step logs and may not include
the underlying database diagnostic when a wrapper reports only a `psql` exit
status.

For a strict local host-side run, use:

```bash
./scripts/verify-local-test-suite.sh
```

This uses the CI-only Compose override to publish PostgreSQL/ClickHouse on
loopback high ports for tests running on the host. The base Compose configuration
keeps the databases private. `scripts/ci-check.sh` and `make ci` are repository
commands; they may start or use the legacy integration stack and are not a
Kernel candidate deployment command.

`./scripts/ci-check.sh` is the fast-fail local check, not the complete hosted
workflow. For local source-only or integration-only runs, use the corresponding
`--source-only` or `--integration-only` mode of
`scripts/run-github-ci.sh`; review that script before running because the
integration mode starts and removes its isolated Compose resources.

The shared static-analysis gate is `scripts/static-analysis.sh`. Required
GitHub status checks and rulesets are repository controls, not inferred from a
local pass. Workflow triggers, deployment workflows, and protection setup are
documented in [GitHub Actions](github-actions.md).

Foundry dependencies are committed vendor trees under `contracts/lib/`, not
Git submodules. Their exact revisions are pinned in `contracts/foundry.lock`.
