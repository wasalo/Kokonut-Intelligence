"""Console contract for read-only CAP-036 evidence views."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_sequential_evidence_panel_requires_exact_scoped_read_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="sequential-evidence".*?</section>\s*</section>', source, re.DOTALL)
    assert panel is not None
    assert "Statements, evidence values, likelihoods, probabilities, source references, and identities are not shown." in panel.group()
    assert 'scope.resource === "sequential_evidence" && scope.action === "read"' in source
    assert "sequentialEvidenceLocations = new Set(sequentialEvidenceLocationIds)" in source
    assert 'sequentialEvidence.hidden = false' in source


def test_summary_and_timeline_use_only_allowlisted_no_store_reads():
    source = CONSOLE.read_text(encoding="utf-8")
    summary = _function(source, "async function loadSequentialEvidenceSummary()", "async function loadSequentialEvidenceTimeline(")
    timeline = _function(source, "async function loadSequentialEvidenceTimeline(append = false)", "async function loadSequentialEvidence()")
    assert '`/operator/api/sequential-evidence/${encodeURIComponent(locationId)}/summary`' in summary
    assert '`/operator/api/sequential-evidence/${encodeURIComponent(locationId)}/events?${params}`' in timeline
    for reader in (summary, timeline):
        assert 'credentials: "same-origin"' in reader
        assert 'cache: "no-store"' in reader
        assert "sequentialEvidenceLocations.has(locationId)" in reader
        assert "innerHTML" not in reader
    renderer = _function(source, "function renderSequentialEvidenceSummary(summary)", "function appendSequentialEvidenceRow(item)")
    for key in (
        "hypothesis_count", "hypothesis_status_counts", "evidence_event_count",
        "evidence_quality_counts", "applied_evidence_event_count", "posterior_update_count",
        "latest_decision_action_counts",
    ):
        assert key in renderer
    assert "Object.entries" not in renderer


def test_timeline_renders_only_redacted_sequence_and_review_metadata():
    source = CONSOLE.read_text(encoding="utf-8")
    row = _function(source, "function appendSequentialEvidenceRow(item)", "function sequentialEvidenceRequestError(")
    for key in (
        "hypothesis_sequence", "subject_type", "evidence_sequence", "observed_at", "ingested_at",
        "evidence_class", "quality_status", "posterior_update_sequence", "calculation_version",
        "posterior_updated_at",
    ):
        assert f"item.{key}" in row
    for private_key in ("hypothesis_id", "event_id", "source_ref", "likelihood", "probability", "party_id"):
        assert private_key not in row
    assert "threshold actions are advisory" in source.lower()


def test_location_change_and_pagination_controls_are_wired_and_bounded():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'sequentialEvidenceLocation.addEventListener("change", loadSequentialEvidence)' in source
    assert 'sequentialEvidenceTimelineMore.addEventListener("click", () => loadSequentialEvidenceTimeline(true))' in source
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in source
    assert "nextOffset <= 10000" in source
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_inline_javascript_parses_when_node_is_available():
    node = shutil.which("node")
    if node is None:
        return
    source = CONSOLE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", source, re.DOTALL)
    assert len(scripts) == 1
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", encoding="utf-8") as script:
        script.write(scripts[0])
        script.flush()
        result = subprocess.run(
            [node, "--check", script.name],
            check=False,
            capture_output=True,
            text=True,
        )
    assert result.returncode == 0, result.stderr
