"""Contracts for the required GitHub Actions CI status and parallel gates."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"
FULL_CI_RUNNER = ROOT / "scripts/run-github-ci.sh"


def _job_block(workflow: str, job_id: str, next_job_id: str) -> str:
    start = workflow.index(f"  {job_id}:\n")
    end = workflow.index(f"\n  {next_job_id}:\n", start)
    return workflow[start:end]


def test_parallel_image_gate_keeps_the_required_ci_status_as_aggregate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    full_ci = _job_block(workflow, "full-ci", "kernel-image")
    kernel_image = _job_block(workflow, "kernel-image", "ci")
    aggregate = workflow.split("\n  ci:\n", 1)[1]
    aggregate = "  ci:\n" + aggregate

    assert "name: ci" in aggregate
    assert "if: always()" in aggregate
    assert "needs: [full-ci, kernel-image]" in aggregate
    assert "FULL_CI_RESULT: ${{ needs.full-ci.result }}" in aggregate
    assert "KERNEL_IMAGE_RESULT: ${{ needs.kernel-image.result }}" in aggregate
    assert '"$FULL_CI_RESULT" != "success"' in aggregate
    assert '"$KERNEL_IMAGE_RESULT" != "success"' in aggregate

    assert "scripts/build-kernel-multiarch.sh" not in full_ci
    assert "Set up ARM emulation" not in full_ci
    assert "Set up ARM emulation" in kernel_image
    assert "Set up Docker Buildx" in kernel_image
    assert "scripts/build-kernel-multiarch.sh" in kernel_image


def test_full_ci_no_longer_waits_for_multiarch_build_before_running_tests() -> None:
    runner = FULL_CI_RUNNER.read_text(encoding="utf-8")

    assert "build-kernel-multiarch.sh" not in runner
    assert "=== Full Python suite (strict database mode) ===" in runner
