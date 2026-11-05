"""Contracts for the required GitHub Actions CI status and parallel gates."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security.yml"
FULL_CI_RUNNER = ROOT / "scripts/run-github-ci.sh"


def _job_block(workflow: str, job_id: str, next_job_id: str) -> str:
    start = workflow.index(f"  {job_id}:\n")
    end = workflow.index(f"\n  {next_job_id}:\n", start)
    return workflow[start:end]


def test_parallel_image_gate_keeps_the_required_ci_status_as_aggregate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    preflight = _job_block(workflow, "preflight", "source-checks")
    source_checks = _job_block(workflow, "source-checks", "full-ci")
    full_ci = _job_block(workflow, "full-ci", "kernel-image")
    kernel_image = _job_block(workflow, "kernel-image", "ci")
    aggregate = workflow.split("\n  ci:\n", 1)[1]
    aggregate = "  ci:\n" + aggregate

    assert "name: ci" in aggregate
    assert "if: ${{ always() && !cancelled() }}" in aggregate
    assert "needs: [preflight, source-checks, full-ci, kernel-image]" in aggregate
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "PREFLIGHT_RESULT: ${{ needs.preflight.result }}" in aggregate
    assert "SOURCE_CHECKS_RESULT: ${{ needs.source-checks.result }}" in aggregate
    assert "FULL_CI_RESULT: ${{ needs.full-ci.result }}" in aggregate
    assert "KERNEL_IMAGE_RESULT: ${{ needs.kernel-image.result }}" in aggregate
    assert '"$SOURCE_CHECKS_RESULT" != "success"' in aggregate
    assert '"$PREFLIGHT_RESULT" != "success"' in aggregate
    assert '"$FULL_CI_RESULT" != "success"' in aggregate
    assert '"$KERNEL_IMAGE_RESULT" != "success"' in aggregate

    assert "scripts/run-github-ci.sh --source-only" in source_checks
    source_job_settings = source_checks.split("steps:", 1)[0]
    assert "runner.temp" not in source_job_settings
    assert "CI_DIAGNOSTICS_DIR: ${{ runner.temp }}/kokonut-ci-source-" in source_checks
    assert "scripts/run-github-ci.sh --integration-only" in full_ci
    assert "scripts/build-kernel-multiarch.sh" not in full_ci
    assert "Set up ARM emulation" not in full_ci
    assert "Set up ARM emulation" in kernel_image
    assert "Set up Docker Buildx" in kernel_image
    assert "scripts/build-kernel-multiarch.sh" in kernel_image

    assert "name: preflight" in preflight
    assert "scripts/ci-preflight.sh" in preflight
    assert "needs:" not in preflight
    for expensive_job in (source_checks, full_ci, kernel_image):
        assert "needs: preflight" in expensive_job


def test_full_ci_no_longer_waits_for_multiarch_build_before_running_tests() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")

    assert "build-kernel-multiarch.sh" not in runner
    assert "=== Full Python suite (strict database mode) ===" in runner
    assert 'RUN_MODE="${1:-all}"' in runner
    assert "all|--source-only|--integration-only)" in runner


def test_source_and_integration_modes_do_not_repeat_each_others_gates() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")

    assert 'if [ "$RUN_MODE" != --integration-only ]; then' in runner
    assert 'if [ "$RUN_MODE" = --source-only ]; then' in runner
    assert "All source and contract CI checks completed successfully." in runner
    assert 'if [ "$RUN_MODE" = all ]; then' in runner
    assert 'if [ "$RUN_MODE" != --source-only ]; then' in runner


def test_full_ci_caches_locked_python_and_node_dependencies() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    source_checks = _job_block(workflow, "source-checks", "full-ci")
    full_ci = _job_block(workflow, "full-ci", "kernel-image")

    assert "actions/setup-node@53b83947a5a98c8d113130e565377fae1a50d02f" in full_ci
    assert "cache: npm" in full_ci
    assert "cache-dependency-path: extensions/kokonut-hooks/package-lock.json" in full_ci
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in full_ci
    assert 'python-version: "3.12"' in full_ci
    assert "cache: pip" in full_ci
    assert "cache-dependency-path: requirements.txt" in full_ci
    assert "cache-dependency-path: |" in source_checks
    assert "requirements/ci-tools.txt" in source_checks


def test_ci_preflight_runs_fast_stale_inventory_gates_before_expensive_jobs() -> None:
    script = (ROOT / "scripts/ci-preflight.sh").read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "Kernel release input lock" in script
    assert "check-kernel-release-inputs.py" in script
    assert "report_generator_inventory.py --check" in script
    assert "report_generator_query_scope_inventory.py --check" in script
    assert "report_generator_helper_scope_inventory.py --check" in script
    assert "runtime_sql_inventory.py --check" in script
    assert "docker" not in script
    assert "pip install" not in script


def test_python_tooling_is_isolated_from_application_dependencies() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")
    tools = (ROOT / "requirements/ci-tools.txt").read_text(encoding="utf-8")

    assert 'CI_TOOLS_VENV="$CI_STATE_DIR/ci-tools"' in runner
    assert '"$CI_TOOLS_VENV/bin/python" -m pip install --only-binary=:all: --retries 5 --timeout 60 -r requirements/ci-tools.txt' in runner
    assert 'CI_TOOLS_BIN="$CI_TOOLS_VENV/bin"' in runner
    assert 'export PATH="$CI_TOOLS_VENV/bin:$PATH"' not in runner
    assert 'PATH="$CI_TOOLS_BIN:$PATH" ./scripts/verify-ci-toolchain.sh' in runner
    assert '"$CI_TOOLS_BIN/ruff" check' in runner
    assert 'APP_VENV="$CI_STATE_DIR/app"' in runner
    assert 'python3 -m venv "$APP_VENV"' in runner
    bootstrap_install = runner.index(
        "python -m pip install --upgrade --only-binary=:all: --retries 5 --timeout 60 pip setuptools"
    )
    requirements_install = runner.index(
        "python -m pip install --only-binary=:all: --retries 5 --timeout 60 -r requirements.txt"
    )
    site_packages = runner.index('APP_SITE_PACKAGES="$(python -c')
    requirements_audit = runner.index(
        'PIPAPI_PYTHON_LOCATION="$APP_VENV/bin/python" "$CI_TOOLS_BIN/pip-audit" --path "$APP_SITE_PACKAGES"'
    )
    assert bootstrap_install < requirements_install < site_packages < requirements_audit
    assert 'sysconfig.get_path("purelib")' in runner
    cryptography_floor = "cryptography>=50.0.0,<51.0.0"
    assert cryptography_floor in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert cryptography_floor in (ROOT / "requirements/oidc.txt").read_text(encoding="utf-8")
    assert 'PATH="$CI_TOOLS_BIN:$PATH" ./scripts/static-analysis.sh' in runner
    assert "python -m pip check" in runner
    assert "slither-analyzer==0.11.5" in tools
    assert "semgrep==1.170.0" in tools
    assert "ruff==0.17.3" in tools
    assert "pip-audit==2.10.1" in tools


def test_postgis_pull_overlaps_dependency_setup_and_database_starts_once() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")
    fast_gate = (ROOT / "scripts/ci-check.sh").read_text(encoding="utf-8")

    pull = runner.index('"${CI_COMPOSE[@]}" pull database')
    app_dependencies = runner.index("python -m pip install --only-binary=:all: --retries 5 --timeout 60 -r requirements.txt")
    source_gate = runner.index("./scripts/ci-check.sh --source-only")
    wait = runner.index('if ! wait "$DB_PULL_PID"')
    database_start = runner.index('"${CI_COMPOSE[@]}" up -d database')
    later_infrastructure = runner.split("echo '=== Starting isolated CI infrastructure ==='", 1)[1].split(
        "ci_phase_start 'Database extensions and schema setup'", 1
    )[0]

    assert pull < app_dependencies < source_gate < wait < database_start
    assert runner.count('"${CI_COMPOSE[@]}" up -d database') == 1
    assert '"${CI_COMPOSE[@]}" up -d clickhouse cache' in later_infrastructure
    assert "down -v" not in later_infrastructure
    assert './scripts/ci-check.sh --database-only' in runner
    assert 'CHECK_MODE="${1:-all}"' in fast_gate
    assert 'all|--source-only|--database-only)' in fast_gate
    assert 'if [ "$CHECK_MODE" = --database-only ]; then' in fast_gate
    assert 'if [ "$CHECK_MODE" = all ]; then' in fast_gate
    assert 'check "Clean PostgreSQL bootstrap"' in fast_gate
    assert 'pull database > >(tee "$DB_PULL_LOG") 2>&1 &' in runner
    assert 'cat "$DB_PULL_LOG"' not in runner


def test_ci_dependency_bootstrap_is_bounded_visible_and_skips_redundant_runner_apt() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")

    assert 'if [ "${GITHUB_ACTIONS:-false}" != true ] && command -v apt-get' in runner
    assert 'run_ci_timeout 10m "${APT_PREFIX[@]}" apt-get' in runner
    assert "Acquire::http::Timeout=30" in runner
    assert "Acquire::https::Timeout=30" in runner
    assert "apt output is visible" in runner
    assert "Skipping apt bootstrap: hosted runners and non-apt hosts use Python wheels." in runner
    assert "run_ci_timeout()" in runner
    assert "run_ci_timeout 25m python -m pip install --only-binary=:all:" in runner
    assert 'run_ci_timeout 20m "$CI_TOOLS_VENV/bin/python" -m pip install --only-binary=:all:' in runner
    assert "run_ci_timeout 15m npm install --global" in runner
    assert 'run_ci_timeout 30s "${CI_COMPOSE[@]}" ps --all' in runner
    assert 'run_ci_timeout 2m "${CI_COMPOSE[@]}" logs' in runner
    assert 'run_ci_timeout 2m "${CI_COMPOSE[@]}" down -v --remove-orphans' in runner
    assert "docker compose --progress plain -f docker-compose.yml -f docker-compose.ci.yml" in runner


def test_ci_reports_phase_timings_and_uploads_failure_diagnostics() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")
    test_runner = (ROOT / "scripts/verify-full-test-suite.sh").read_text(encoding="utf-8")
    source_checks = _job_block(workflow, "source-checks", "full-ci")
    full_ci = _job_block(workflow, "full-ci", "kernel-image")

    assert "ci_finish_phase" in runner
    assert "GITHUB_STEP_SUMMARY" in runner
    assert "::error title=CI runner failed::" in runner
    assert '"$RUN_MODE" "$CI_PHASE"' in runner
    assert "uploaded diagnostics" in runner
    assert 'compose-logs.txt' in runner
    assert 'tee "$RUNNER_TEMP/kokonut-ci-run.log"' in full_ci
    assert "status=${PIPESTATUS[0]}" in full_ci
    assert "kokonut-ci-run.log" in full_ci
    assert "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9" in full_ci
    assert "if: failure()" in full_ci
    assert "retention-days: 7" in full_ci
    assert '"$PYTHON_BIN" -m pytest -v -rs --durations=25' in test_runner
    assert "kokonut-ci-source.log" in source_checks
    assert "artifacts/static-analysis/" in source_checks
    assert "if: failure()" in source_checks


def test_security_workflow_retries_pinned_gitleaks_download() -> None:
    workflow = SECURITY_WORKFLOW.read_text(encoding="utf-8")

    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "--retry 5 --retry-delay 2 --retry-max-time 120" in workflow
    assert "--connect-timeout 30 --max-time 180" in workflow
    assert "sha256sum --check" in workflow
    assert "gitleaks git --config .gitleaks.toml --redact --verbose --log-opts='--all' ." in workflow


def test_ci_builds_directus_hooks_before_starting_directus() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")
    hooks_build = runner.index("make hooks-build")
    directus_start = runner.index('"${CI_COMPOSE[@]}" up -d --wait directus')
    hook_tests = runner.index("make hooks-test")

    assert runner.index("=== Building Directus extension hooks ===") < hooks_build
    assert hooks_build < directus_start
    assert 'if [ "$RUN_MODE" = --source-only ]; then' in runner[:hook_tests]


def test_hooks_build_publishes_compiled_bundle_for_container_uid() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    hooks_build = makefile.split("hooks-build:\n", 1)[1].split("\nhooks-test:", 1)[0]

    assert "(umask 022 && npm run build)" in hooks_build
    assert "find dist -type d -exec chmod 0755 {} +" in hooks_build
    assert "find dist -type f -exec chmod 0644 {} +" in hooks_build
