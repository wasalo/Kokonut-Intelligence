"""Operator console contract for cooperative management aggregate reads."""

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


def test_panel_requires_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="cooperative-management".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="cooperative-management" hidden' in panel.group()
    assert 'scope.resource === "cooperative_management" && scope.action === "read"' in source
    assert "cooperativeManagementLocations = new Set(cooperativeManagementLocationIds)" in source
    assert "cooperativeManagement.hidden = false" in source
    panel_text = panel.group().lower()
    for private_field in ("member identities", "credentials", "booking details", "gps"):
        assert private_field in panel_text


def test_summary_fetch_is_same_origin_no_store_and_location_correlated():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCooperativeManagementSummary(", "function yieldMonitoringValue(")
    assert '`/operator/api/cooperatives/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "cooperativeManagementLocations.has(locationId)" in reader
    assert "requestVersion !== cooperativeManagementRequestVersion" in reader
    assert "locationId !== cooperativeManagementLocation.value" in reader
    assert "result.location_id !== locationId" in reader
    renderer = _function(source, "function renderCooperativeManagementSummary(", "async function loadCooperativeManagementSummary(")
    for key in ("cooperatives", "assets", "bookings"):
        assert f'["{key}"' in renderer
    for field in (
        "cooperative_type", "cooperative_status", "cooperative_count", "active_member_count",
        "asset_type", "asset_status", "asset_count", "booking_status", "booking_count",
    ):
        assert f'["{field}"' in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    for private_field in ("farmer_id", "member_name", "credential", "purpose", "total_cost", "latitude"):
        assert f"row.{private_field}" not in renderer


def test_location_selector_and_refresh_are_wired_without_duplicate_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'cooperativeManagementLocation.addEventListener("change", loadCooperativeManagementSummary)' in source
    assert 'document.querySelector("#cooperative-management-refresh").addEventListener("click", loadCooperativeManagementSummary)' in source
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
            [node, "--check", script.name], check=False, capture_output=True, text=True
        )
    assert result.returncode == 0, result.stderr
