# CI gates

The active workflow is `.github/workflows/ci.yml`. It runs on pull requests and
pushes targeting `main` and `develop`, plus manual dispatch. GitHub-hosted
`ubuntu-24.04` is used for the CI job. Its Compose project name is pinned to
`ki-ci`; database services use runner-local high ports to avoid common host
port conflicts.

The workflow invokes `scripts/run-github-ci.sh`, which runs the repository's
complete check pipeline, including strict database-backed tests and static
analysis. CI is fail-closed: missing required tools, database connectivity
failures, missing schema objects, and infrastructure-related skips do not count
as successful acceptance. Review the workflow and scripts for the current tool
versions and job steps rather than relying on a copied list here.

For a strict local host-side run, use:

```bash
./scripts/verify-local-test-suite.sh
```

This uses the CI-only Compose override to publish PostgreSQL/ClickHouse on
loopback high ports for tests running on the host. The base Compose configuration
keeps the databases private. `scripts/ci-check.sh` and `make ci` are repository
commands; they may start or use the legacy integration stack and are not a
Kernel candidate deployment command.

The shared static-analysis gate is `scripts/static-analysis.sh`. Required
GitHub status checks and rulesets are repository controls, not inferred from a
local pass. Workflow triggers, deployment workflows, and protection setup are
documented in [GitHub Actions](github-actions.md).

Foundry dependencies are committed vendor trees under `contracts/lib/`, not
Git submodules. Their exact revisions are pinned in `contracts/foundry.lock`.
