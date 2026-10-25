"""Operator-console contracts for Delphi questionnaire item drafts."""

import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_item_editor_requires_read_and_draft_grants_for_same_location():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="delphi-study-item-create".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'scope.resource === "delphi" && scope.action === "read"' in source
    assert 'scope.resource === "delphi" && scope.action === "draft"' in source
    assert "delphiStudyItemLocationIds = [...delphiReadLocationIds]" in source
    assert "filter((locationId) => delphiStudyDraftLocations.has(locationId))" in source
    assert "Target-entity links are not available in this form." in panel.group()


def test_study_loader_is_bounded_scoped_and_exposes_only_drafts():
    source = CONSOLE.read_text(encoding="utf-8")
    loader = _function(
        source,
        "async function loadDelphiStudyItemStudies(append = false)",
        "async function submitDelphiStudyItem()",
    )
    assert "delphiStudyItemLocations.has(locationId)" in loader
    assert 'limit: "50"' in loader
    assert "delphiStudyItemOffset" in loader
    assert "/operator/api/delphi/${encodeURIComponent(locationId)}/studies?${params}" in loader
    assert 'cache: "no-store"' in loader
    assert 'credentials: "same-origin"' in loader
    assert "requestVersion !== delphiStudyItemRequestVersion" in loader
    assert "result.location_id !== locationId" in loader
    assert 'study.status !== "draft"' in loader
    assert "option.textContent" in loader
    assert "innerHTML" not in loader


def test_item_submit_checks_draft_scope_and_bounded_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiStudyItem()",
        "function refreshDelphiStudyLifecycleControls()",
    )
    assert "delphiStudyItemLocations.has(locationId)" in submitter
    assert 'selected?.dataset?.status !== "draft"' in submitter
    assert "label.length > 255" in submitter
    assert "description.length > 4000" in submitter
    assert "minValue >= maxValue" in submitter
    assert "min_value: minValue" in submitter and "max_value: maxValue" in submitter
    assert "target_entity" not in submitter


def test_item_post_uses_csrf_no_store_stable_retry_and_response_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiStudyItem()",
        "function refreshDelphiStudyLifecycleControls()",
    )
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert 'method: "POST"' in submitter
    assert "delphiStudyItemRequestIds.get(requestKey)" in submitter
    assert "delphiStudyItemRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiStudyItemRequestIds.delete(requestKey)" in submitter
    assert "/items`" in submitter
    assert "result.location_id !== locationId" in submitter
    assert "result.study_id !== studyId" in submitter
    assert "result.item_type !== payload.item_type" in submitter
    assert "Retrying unchanged values will reuse the same request ID." in submitter


def test_item_editor_has_unique_ids_and_event_handlers():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-study-item-create",
        "delphi-study-item-location",
        "delphi-study-item-study",
        "delphi-study-item-type",
        "delphi-study-item-scale",
        "delphi-study-item-label",
        "delphi-study-item-description",
        "delphi-study-item-min",
        "delphi-study-item-max",
        "delphi-study-item-submit",
        "delphi-study-item-status",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiStudyItemSubmit.addEventListener("click", submitDelphiStudyItem)' in source


def test_inline_javascript_parses_with_node(tmp_path):
    node = shutil.which("node")
    if node is None:
        return
    source = CONSOLE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    script = tmp_path / "operator-console.js"
    script.write_text(scripts[0], encoding="utf-8")
    subprocess.run([node, "--check", str(script)], check=True, capture_output=True, text=True)
