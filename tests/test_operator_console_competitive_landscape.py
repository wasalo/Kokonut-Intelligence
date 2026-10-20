"""Console contract for read-only CAP-029 competitive landscapes."""

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


def test_landscape_panel_requires_exact_location_read_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="competitive-landscape-summary".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert "Read-only location landscape metadata and aggregate actor" in panel.group()
    assert 'scope.resource === "competitive_landscape" && scope.action === "read"' in source
    assert "competitiveLandscapeLocations = new Set(competitiveLandscapeLocationIds)" in source
    assert "competitiveLandscapeSummary.hidden = false" in source


def test_reader_uses_protected_no_store_route_stale_guards_and_bounded_pages():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCompetitiveLandscapeSummaries(", "async function loadSession()")
    assert '`/operator/api/competitive-landscape/${encodeURIComponent(locationId)}/summaries?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "competitiveLandscapeLocations.has(locationId)" in reader
    assert "requestVersion !== competitiveLandscapeRequestVersion" in reader
    assert "locationId !== competitiveLandscapeLocation.value" in reader
    assert "nextOffset <= 10000" in reader
    assert "innerHTML" not in reader


def test_table_renders_only_fixed_landscape_aggregate_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadCompetitiveLandscapeSummaries(", "async function loadSession()")
    for field in (
        "industry", "geography", "period_start", "period_end", "landscape_status",
        "confidence", "updated_at", "actor_count", "high_or_critical_actor_count",
        "force_observation_count", "average_force_pressure", "worsening_force_count",
        "signal_count", "unreviewed_critical_signal_count", "verified_advantage_count",
        "average_verified_defensibility", "verified_advantage_outcome_count",
        "latest_verified_outcome_period_end",
    ):
        assert f"landscape.{field}" in reader
    assert "textContent" in reader
    assert "innerHTML" not in reader
    for private_field in (
        "landscape_id", "strategy_plan_id", "actor_name", "description", "source_reference",
        "evidence", "rationale", "advantage_statement", "party_id", "outcome_value",
    ):
        assert f"landscape.{private_field}" not in reader


def test_refresh_location_and_pagination_controls_are_wired_with_unique_ids():
    source = CONSOLE.read_text(encoding="utf-8")
    assert 'competitiveLandscapeLocation.addEventListener("change", () => loadCompetitiveLandscapeSummaries())' in source
    assert 'document.querySelector("#competitive-landscape-refresh").addEventListener("click", () => loadCompetitiveLandscapeSummaries())' in source
    assert 'competitiveLandscapeMore.addEventListener("click", () => loadCompetitiveLandscapeSummaries(true))' in source
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
