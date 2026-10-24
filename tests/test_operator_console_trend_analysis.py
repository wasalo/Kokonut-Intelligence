"""Console contract for saved location-scoped trend estimates."""

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


def test_panel_requires_exact_read_scope_and_marks_outputs_advisory():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="trend-analysis".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="trend-analysis" hidden' in panel.group()
    assert 'scope.resource === "trend_analysis" && scope.action === "read"' in source
    assert "trendAnalysis.hidden = false" in source
    assert "does not rerun a model or independently verify" in panel.group()


def test_estimate_reader_is_bounded_scoped_and_text_only():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadTrendEstimates(", "function yieldMonitoringValue(")
    assert '`/operator/api/trends/${encodeURIComponent(locationId)}/estimates?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "trendAnalysisLocations.has(locationId)" in reader
    assert "result.location_id !== locationId" in reader
    assert "result.items.length > 25" in reader
    assert "result.offset !== offset" in reader
    assert "requestVersion !== trendAnalysisRequestVersion" in reader
    assert "locationId !== trendAnalysisLocation.value" in reader
    renderer = _function(source, "function renderTrendEstimate(", "async function loadTrendEstimates(")
    for field in (
        "metric_key", "direction", "confidence_level", "slope", "r_squared", "data_points",
        "time_unit", "period_start", "period_end", "computed_at",
    ):
        assert f'["{field}"' in renderer or f"estimate.{field}" in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    assert "estimate.metadata" not in renderer and "estimate.computed_by" not in renderer


def test_refresh_and_pagination_are_wired_without_duplicate_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'trendAnalysisLocation.addEventListener("change", () => loadTrendEstimates())' in source
    assert 'trendAnalysisMore.addEventListener("click", () => loadTrendEstimates(true))' in source
    assert 'document.querySelector("#trend-analysis-refresh").addEventListener("click", () => loadTrendEstimates())' in source
    ids = re.findall(r'\bid="([^\"]+)"', source)
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
