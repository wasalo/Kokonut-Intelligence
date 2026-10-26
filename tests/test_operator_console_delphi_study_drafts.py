"""Console contracts for private, location-scoped Delphi study drafts."""

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


def test_study_creation_panel_uses_exact_location_draft_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel_match = re.search(
        r'<section id="delphi-study-draft-create".*?</section>',
        source,
        re.DOTALL,
    )
    assert panel_match is not None
    panel = panel_match.group()
    assert 'scope.resource === "delphi" && scope.action === "draft"' in source
    assert "delphiStudyDraftLocations.has(locationId)" in source
    assert "Saving does not open participation" in panel
    assert "add panel members, or publish results" in panel
    assert 'id="delphi-study-draft-title"' in panel
    assert 'id="delphi-study-draft-description"' in panel
    assert 'id="delphi-study-draft-duration"' in panel
    assert 'id="delphi-study-draft-participants"' in panel
    assert "innerHTML" not in panel


def test_study_create_submit_uses_csrf_no_store_and_exact_retry_key():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiStudyDraft()",
        "async function loadDelphiConsentNoticeDraftStudies(",
    )
    assert "delphiStudyDraftLocations.has(locationId)" in submitter
    assert "delphiStudyDraftRequestIds.get(requestKey)" in submitter
    assert "delphiStudyDraftRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiStudyDraftRequestIds.delete(requestKey)" in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert 'method: "POST"' in submitter
    assert "request_id: requestId" in submitter
    assert "stopping_criteria:" in submitter
    assert "result.status !== \"draft\"" in submitter
    assert "result.replayed" in submitter
    assert "closed and unpublished" in submitter
    assert "/decision" not in submitter
    assert "innerHTML" not in submitter


def test_study_form_ids_are_unique_and_submit_event_is_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    assert 'delphiStudyDraftSubmit.addEventListener("click", submitDelphiStudyDraft)' in source
    for element_id in (
        "delphi-study-draft-create",
        "delphi-study-draft-location",
        "delphi-study-draft-title",
        "delphi-study-draft-description",
        "delphi-study-draft-variation",
        "delphi-study-draft-facilitator",
        "delphi-study-draft-duration",
        "delphi-study-draft-stability",
        "delphi-study-draft-participants",
        "delphi-study-draft-iqr",
        "delphi-study-draft-submit",
        "delphi-study-draft-status",
    ):
        assert f'id="{element_id}"' in source


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
