"""Console contract for exact-location non-promotion lifecycle transitions."""

import re
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_stage_transition_panel_requires_both_read_and_transition_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="solution-lifecycle-stage-transitions".*?</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert "non-promotion stages only" in panel.group()
    assert "approved stage-gate workflow" in panel.group()
    assert "separate sunset process" in panel.group()
    assert 'solutionLifecycleStageTransitions.hidden = !solutionLifecycleLocations.has(solutionLifecycleLocation.value)' in source
    assert '|| !solutionLifecycleTransitionLocations.has(solutionLifecycleLocation.value)' in source


def test_target_reader_uses_exact_location_read_no_store_paging_and_stale_guards():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadSolutionLifecycleStageTransitionTargets(",
        "async function loadSolutionLifecycleGates(",
    )
    assert "solutionLifecycleLocations.has(locationId)" in reader
    assert "solutionLifecycleTransitionLocations.has(locationId)" in reader
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/stage-transition-targets?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== solutionLifecycleStageTransitionsRequestVersion" in reader
    assert "locationId !== solutionLifecycleLocation.value" in reader
    assert "result.has_more" in reader and "result.next_offset" in reader
    assert "innerHTML" not in reader


def test_stage_form_excludes_promotion_and_retirement_and_binds_retry_to_exact_payload():
    source = CONSOLE.read_text(encoding="utf-8")
    form = _function(
        source,
        "function createSolutionLifecycleNonpromotionTransitionForm(",
        "async function loadSolutionLifecycleStageTransitionTargets(",
    )
    for stage in (
        "discovered", "triaged", "framed", "experiment_ready", "testing",
        "investment_ready", "pilot_active", "adopting", "maintained", "paused", "failed",
    ):
        assert f'["{stage}"' in form
    for forbidden_stage in ("validated", "funded", "adoption_ready", "scaled", "retired", "superseded"):
        assert f'["{forbidden_stage}"' not in form
    assert "solution_id: solutionId" in form
    assert "expected_from_stage: expectedFromStage" in form
    assert "form.pendingTransition?.fingerprint !== fingerprint" in form
    assert "form.pendingTransition.request_id" in form
    assert "acknowledge.checked" in form
    assert "Array.isArray(evidenceValue)" in form
    assert "method: \"POST\"" in form and "cache: \"no-store\"" in form
    assert '"X-CSRF-Token": csrf' in form
    assert "credentials: \"same-origin\"" in form
    assert "innerHTML" not in form
    assert '`/operator/api/solution-lifecycle/${encodeURIComponent(locationId)}/solutions/${encodeURIComponent(solutionId)}/stage-transition`' in form


def test_rendered_target_card_displays_fixed_metadata_and_never_raw_identity_or_evidence():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function appendSolutionLifecycleStageTransitionTarget(",
        "function createSolutionLifecycleNonpromotionTransitionForm(",
    )
    for field in ("solution_name", "solution_type", "current_stage", "solution_status", "updated_at"):
        assert f"solution.{field}" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    assert "solution.evidence" not in renderer
    assert "operator_id" not in renderer
