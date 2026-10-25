"""Operator-console contracts for Delphi study lifecycle actions."""

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_lifecycle_panel_requires_read_and_exact_location_action_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    match = re.search(r'<section id="delphi-study-lifecycle".*?</section>', source, re.DOTALL)
    assert match is not None
    panel = match.group()
    assert 'scope.resource === "delphi" && scope.action === "read"' in source
    assert 'scope.resource === "delphi" && scope.action === "open"' in source
    assert 'scope.resource === "delphi" && scope.action === "close"' in source
    assert "delphiReadLocationIds" in source
    assert "delphiOpenLocationIds.has(locationId)" in source
    assert "delphiCloseLocationIds.has(locationId)" in source
    assert "delphiStudyLifecycleLocations.has(locationId)" in source
    assert "a closed study cannot be reopened" in panel


def test_study_list_is_location_scoped_no_store_and_bounded():
    source = CONSOLE.read_text(encoding="utf-8")
    loader = _function(
        source,
        "async function loadDelphiStudyLifecycleStudies(append = false)",
        "async function submitDelphiStudyLifecycle(action)",
    )
    assert "delphiStudyLifecycleLocations.has(locationId)" in loader
    assert 'limit: "50"' in loader
    assert "delphiStudyLifecycleOffset" in loader
    assert "/operator/api/delphi/${encodeURIComponent(locationId)}/studies?${params}" in loader
    assert 'cache: "no-store"' in loader
    assert 'credentials: "same-origin"' in loader
    assert "result.location_id !== locationId" in loader
    assert '"draft", "open", "closed"' in loader
    assert "textContent" in loader
    assert "innerHTML" not in loader


def test_transition_uses_csrf_no_store_confirm_and_retry_stable_request_id():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiStudyLifecycle(action)",
        "async function loadDelphiRecommendationDraftStudies(",
    )
    assert 'action !== "open" && action !== "close"' in submitter
    assert 'grants?.[action]' in submitter
    assert "selected?.dataset?.status !== expectedStatus" in submitter
    assert "window.confirm(confirmation)" in submitter
    assert "delphiStudyLifecycleRequestIds.get(requestKey)" in submitter
    assert "delphiStudyLifecycleRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiStudyLifecycleRequestIds.delete(requestKey)" in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert 'method: "POST"' in submitter
    assert "body: JSON.stringify({ request_id: requestId })" in submitter
    assert "result.location_id !== locationId" in submitter
    assert "result.status !== resultStatus" in submitter
    assert "Retrying this action will reuse its request ID." in submitter


def test_closed_state_is_terminal_and_action_controls_follow_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    controls = _function(
        source,
        "function refreshDelphiStudyLifecycleControls()",
        "async function loadDelphiStudyLifecycleOpenReadiness()",
    )
    assert '!grants?.open || status !== "draft"' in controls
    assert 'grants?.close || status !== "open"' in controls
    submitter = _function(
        source,
        "async function submitDelphiStudyLifecycle(action)",
        "async function loadDelphiRecommendationDraftStudies(",
    )
    assert 'action === "open" ? "open" : "closed"' in submitter
    assert "result.closed_at !== null" in submitter
    assert "Closed Delphi study cannot be reopened" in submitter or "cannot be reopened" in source


def test_open_button_fails_closed_until_current_safe_readiness_is_confirmed():
    source = CONSOLE.read_text(encoding="utf-8")
    controls = _function(
        source,
        "function refreshDelphiStudyLifecycleControls()",
        "async function loadDelphiStudyLifecycleOpenReadiness()",
    )
    readiness = _function(
        source,
        "async function loadDelphiStudyLifecycleOpenReadiness()",
        "async function loadDelphiStudyLifecycleStudies(",
    )
    submitter = _function(
        source,
        "async function submitDelphiStudyLifecycle(action)",
        "async function loadDelphiRecommendationDraftStudies(",
    )
    assert "!readinessMatches" in controls
    assert "eligible_to_open !== true" in controls
    assert "/open-readiness" in readiness
    assert 'cache: "no-store"' in readiness
    assert 'credentials: "same-origin"' in readiness
    assert "delphiStudyLifecycleReadinessRequestVersion" in readiness
    assert "consented_panel_below_minimum" in readiness
    assert "minimum_participants_invalid" in readiness
    assert "participant_count" not in readiness and "consented_count" not in readiness
    assert "loadDelphiStudyLifecycleOpenReadiness()" in submitter
    assert "freshReadiness?.eligible_to_open !== true" in submitter
    assert 'delphiStudyLifecycleStudy.addEventListener("change", () =>' in source


def test_lifecycle_controls_have_unique_ids_and_event_handlers():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-study-lifecycle",
        "delphi-study-lifecycle-location",
        "delphi-study-lifecycle-study",
        "delphi-study-lifecycle-more",
        "delphi-study-lifecycle-open",
        "delphi-study-lifecycle-close",
        "delphi-study-lifecycle-readiness",
        "delphi-study-lifecycle-status",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiStudyLifecycleOpen.addEventListener("click", () => submitDelphiStudyLifecycle("open"))' in source
    assert 'delphiStudyLifecycleClose.addEventListener("click", () => submitDelphiStudyLifecycle("close"))' in source


def test_inline_javascript_parses_with_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")
    source = CONSOLE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    script = tmp_path / "operator-console.js"
    script.write_text(scripts[0], encoding="utf-8")
    subprocess.run([node, "--check", str(script)], check=True, capture_output=True, text=True)
