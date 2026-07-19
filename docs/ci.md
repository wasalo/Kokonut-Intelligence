# CI Gates

CI requires Python, Node/npm, Foundry, Slither, Aderyn, and Semgrep. The
toolchain check is fail-closed; a missing tool or failed analyzer does not count
as a successful build.

Database-backed tests run with `CI_STRICT_DB=1`. PostgreSQL or ClickHouse
connectivity failures, missing tables, and infrastructure-related test skips
fail CI. Local runs may omit this variable when a database is intentionally not
available.

For a strict local host-side run, use `./scripts/verify-local-test-suite.sh`.
It starts the database services with the CI-only localhost port override, while
the base Compose configuration keeps those ports private.

The shared static-analysis gate is `scripts/static-analysis.sh`. Both GitHub
Actions and OneDev invoke it, so analyzer behavior is consistent across CI
systems.

Foundry dependencies are committed vendor trees under `contracts/lib/`, not
git submodules. Their exact revisions are pinned in `contracts/foundry.lock`.
