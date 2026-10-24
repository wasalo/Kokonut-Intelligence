"""CAP-006 ecology console panels remain separately scoped and text-only."""

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

SOURCE = Path("apps/operator-console/index.html").read_text()


def test_landscape_pollinator_panels_are_hidden_and_split_by_exact_grant():
    parent = re.search(r'<section id="landscape-pollinator".*?</section>\s*</section>', SOURCE, re.DOTALL)
    assert parent
    assert 'id="landscape-pollinator" hidden' in parent.group()
    assert 'id="landscape-conservation" hidden' in parent.group()
    assert 'id="pollinator-health" hidden' in parent.group()
    assert 'scope.resource === "landscape_conservation" && scope.action === "read"' in SOURCE
    assert 'scope.resource === "pollinator_health" && scope.action === "read"' in SOURCE
    assert "Inventories are descriptive" in parent.group()
    assert "Names, plots, geometry, species, products, notes, and arbitrary metadata are excluded." in parent.group()


def test_landscape_and_pollinator_loaders_check_location_staleness_and_no_store():
    cases = [
        ("loadLandscapeConservationSummary", "landscapeConservationLocations", "landscapeConservationRequestVersion", "/operator/api/landscape/", "result.habitats"),
        ("loadPollinatorHealthSummary", "pollinatorHealthLocations", "pollinatorHealthRequestVersion", "/operator/api/pollinators/", "result.verified_observations"),
    ]
    for name, locations, request_version, path, contract in cases:
        loader = re.search(rf"async function {name}\(\).*?\n      }}", SOURCE, re.DOTALL)
        assert loader, name
        body = loader.group()
        assert f"{locations}.has(locationId)" in body
        assert path in body
        assert 'cache: "no-store"' in body
        assert "result.location_id !== locationId" in body
        assert f"requestVersion !== {request_version}" in body
        assert contract in body


def test_ecology_panels_use_allowlists_and_fixed_text_rendering():
    landscape = re.search(r"function renderLandscapeSummary\(summary\).*?\n      }", SOURCE, re.DOTALL)
    pollinator = re.search(r"function renderPollinatorSummary\(summary\).*?\n      }", SOURCE, re.DOTALL)
    table_renderer = re.search(r"function renderEcologySections\(container, sections\).*?\n      }", SOURCE, re.DOTALL)
    assert landscape and pollinator and table_renderer
    assert "habitatTypes.has(row.habitat_type)" in landscape.group()
    assert "habitatStatuses.has(row.status)" in landscape.group()
    assert "reviewedStatuses.has(row.status)" in pollinator.group()
    assert "toxicities.has(row.toxicity_class)" in pollinator.group()
    assert 'summary.observation_trends' in pollinator.group()
    assert 'summary.pesticide_risk_summary.risk_distribution' in pollinator.group()
    assert 'summary.active_hive_summary' in pollinator.group()
    assert 'result.observation_trends' in SOURCE
    assert 'validRiskCounts' in SOURCE
    assert "cell.textContent = value" in table_renderer.group()
    assert ".innerHTML" not in table_renderer.group()


def test_landscape_dashboard_calculations_are_validated_and_labeled_as_compatibility_summaries():
    landscape = re.search(r"function renderLandscapeSummary\(summary\).*?\n      }", SOURCE, re.DOTALL)
    loader = re.search(r"async function loadLandscapeConservationSummary\(\).*?\n      }", SOURCE, re.DOTALL)
    assert landscape and loader
    for field in ("active_habitats", "active_corridors", "verified_buffer_checks"):
        assert f"calculations.{field}" in landscape.group()
        assert f"result.dashboard_calculations.{field}" in loader.group()
    assert "Number.isSafeInteger" in landscape.group()
    assert "row.compliant_checks <= row.total_checks" in landscape.group()
    assert "row.compliance_pct <= 100" in landscape.group()
    assert "legacy connectivity ratio" in landscape.group().lower()
    assert "not a network metric" in SOURCE.lower()
    assert "Verified compliance (%)" in landscape.group()


def test_ecology_panels_refresh_on_change_and_have_unique_ids():
    assert 'document.querySelector("#landscape-conservation-refresh").addEventListener("click", loadLandscapeConservationSummary)' in SOURCE
    assert 'landscapeConservationLocation.addEventListener("change", loadLandscapeConservationSummary)' in SOURCE
    assert 'document.querySelector("#pollinator-health-refresh").addEventListener("click", loadPollinatorHealthSummary)' in SOURCE
    assert 'pollinatorHealthLocation.addEventListener("change", loadPollinatorHealthSummary)' in SOURCE
    ids = re.findall(r'\bid="([^"]+)"', SOURCE)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_inline_console_javascript_passes_node_syntax_check():
    node = shutil.which("node")
    assert node, "Node.js is required for the operator-console JavaScript syntax check"
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", SOURCE, re.IGNORECASE | re.DOTALL)
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
