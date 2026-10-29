"""Console contracts for private report snapshot exports."""

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


def test_export_panel_is_separate_and_marks_private_location_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="report-exports".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "verified or published report snapshot" in panel.group()
    assert "separate location grants" in panel.group()
    assert "never published or shared" in panel.group()
    for action in ("read", "create", "download"):
        assert f'reportExportScopeLocations("{action}")' in source
        assert f"reportExport{action.title()}Locations = new Set" in source
    assert "reportExportLocationHas(reportExportReadLocations, locationId)" in source
    assert "reportExportCreateLocations, candidate.location_id" in source
    assert "reportExportDownloadLocations, item.location_id" in source


def test_candidate_reader_validates_exact_page_and_location_with_no_store():
    source = CONSOLE.read_text(encoding="utf-8")
    candidate = _function(
        source,
        "async function loadReportExportCandidates(",
        "async function loadReportExportRequests(",
    )
    validator = _function(source, "function isReportExportCandidate(", "function isReportExportSummary(")

    assert 'reportExportReadLocations, locationId' in candidate
    assert 'new URLSearchParams({ location_id: locationId, limit: "25", offset: String(offset) })' in candidate
    assert '`/operator/api/report-export-snapshots?${params}`' in candidate
    assert 'credentials: "same-origin"' in candidate
    assert 'cache: "no-store"' in candidate
    assert "result.location_id !== locationId" in candidate
    assert "result.offset !== offset" in candidate
    assert "reportExportCandidateOffset <= 5000" in candidate
    assert "isReportExportCandidate(item, locationId)" in candidate
    assert "Object.keys(value).sort().join(",") !== reportExportCandidateFields" in validator
    assert '"verified", "published"' in validator
    assert "snapshot_hash" in validator and "location_id === locationId" in validator
    assert "innerHTML" not in candidate


def test_create_uses_csrf_and_persistent_idempotency_and_refreshes_status():
    source = CONSOLE.read_text(encoding="utf-8")
    create = _function(source, "async function createReportExport(", "async function downloadReportExport(")

    assert "reportExportCreateLocations, locationId" in create
    assert "reportExportCandidatesById.get(candidate.snapshot_id) !== candidate" in create
    assert "sessionStorage.getItem(storageKey)" in create
    assert "sessionStorage.setItem(storageKey, idempotencyKey)" in create
    assert 'method: "POST"' in create
    assert 'credentials: "same-origin"' in create
    assert 'cache: "no-store"' in create
    assert '"X-CSRF-Token": csrf' in create
    assert "report_snapshot_id: candidate.snapshot_id, idempotency_key: idempotencyKey" in create
    assert "sessionStorage.removeItem(storageKey)" in create
    assert "await loadReportExportRequests()" in create
    assert create.rfind("sessionStorage.removeItem(storageKey)") > create.index(
        "await loadReportExportRequests()"
    )
    assert "The export was accepted, but its status is not confirmed yet" in create


def test_requests_poll_and_download_only_completed_private_artifacts():
    source = CONSOLE.read_text(encoding="utf-8")
    requests = _function(
        source,
        "async function loadReportExportRequests(",
        "async function refreshReportExports()",
    )
    summary = _function(source, "function isReportExportSummary(", "function reportExportLocationHas(")
    download = _function(source, "async function downloadReportExport(", "function renderIdentity(")

    assert 'cache: "no-store"' in requests
    assert "result.location_id !== locationId" in requests
    assert "isReportExportSummary(item, locationId)" in requests
    assert '"pending", "processing", "retryable"' in source
    assert "window.setTimeout(() => loadReportExportRequests({ poll: true }), 5000)" in source
    assert "Object.keys(value).sort().join(",") !== reportExportRequestFields" in summary
    assert "value.location_id === locationId" in summary
    assert 'item.status !== "completed"' in download
    assert "reportExportDownloadLocations, locationId" in download
    assert 'cache: "no-store"' in download
    assert 'content-type"' in download.lower()
    assert "524288" in download and "blob.size" in download
    assert "URL.createObjectURL(blob)" in download
    assert "anchor.download = `kokonut-report-export-${item.request_id}.json`" in download
    assert "innerHTML" not in download


def test_panel_ids_and_refresh_pagination_are_wired_once():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    setup = _function(
        source,
        'document.querySelector("#report-export-refresh").addEventListener',
        'document.querySelector("#delphi-recommendation-review-refresh").addEventListener',
    )
    for element_id in (
        "report-exports", "report-export-location", "report-export-refresh",
        "report-export-status", "report-export-candidates", "report-export-more",
        "report-export-requests",
    ):
        assert f'id="{element_id}"' in source
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    assert "refreshReportExports" in setup
    assert "loadReportExportCandidates({ append: true" in setup


def test_inline_console_javascript_passes_node_syntax_check():
    node = shutil.which("node")
    assert node, "Node.js is required for the operator-console JavaScript syntax check"
    source = CONSOLE.read_text(encoding="utf-8")
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", source, re.IGNORECASE | re.DOTALL)
    assert len(scripts) == 1, "Expected the console to contain one inline application script"

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
