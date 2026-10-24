"""Console contract for tenant-scoped nutrient record reads."""

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


def test_nutrient_panel_is_hidden_until_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="nutrient-operations".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="nutrient-operations" hidden' in panel.group()
    assert 'scope.resource === "nutrient_budget" && scope.action === "read"' in source
    assert "nutrientOperationsLocations = new Set(nutrientOperationsLocationIds)" in source
    assert "nutrientOperations.hidden = false" in source
    for view in ("balances", "soil-tests", "inputs", "removals"):
        assert f'value="{view}"' in source


def test_allowlisted_views_map_to_private_bounded_gateway_routes():
    source = CONSOLE.read_text(encoding="utf-8")
    config = _function(source, "function nutrientViewConfig(", "function nutrientCellValue(")
    for fragment in (
        'balances: {', 'route: "balances"', 'rowsKey: "balances"',
        '"soil-tests": {', 'route: "soil-tests"', 'rowsKey: "soil_tests"',
        'inputs: {', 'route: "events/inputs"', 'eventType: "inputs"',
        'removals: {', 'route: "events/removals"', 'eventType: "removals"',
        '...nutrientColumns("nitrogen")', '"measurements.soil_ph"', '"recommendations_kg_ha.potassium"',
        '"nutrients_kg.phosphorus"',
    ):
        assert fragment in config
    assert "Object.prototype.hasOwnProperty.call(configs, view)" in config
    for forbidden in ("event_id", "test_id", "plot_id", "notes", "metadata"):
        assert forbidden not in config


def test_loader_checks_grant_location_view_offset_and_stale_responses():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadNutrientRecords(", "function traceabilityDisplayValue(")
    assert "nutrientOperationsLocations.has(locationId)" in reader
    assert '`/operator/api/nutrients/${encodeURIComponent(locationId)}/${config.route}?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert "nutrientOperationsOffset > 10000" in reader
    assert "result.location_id !== locationId || result.offset !== offset" in reader
    assert "config.eventType && result.event_type !== config.eventType" in reader
    assert "requestVersion !== nutrientOperationsRequestVersion" in reader
    assert "locationId !== nutrientOperationsLocation.value" in reader
    assert "view !== nutrientOperationsView.value" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "nutrientOperationsMore.disabled = false" in reader
    assert "Choose a supported nutrient record view" in reader


def test_cost_display_preserves_classification_and_never_combines_currencies():
    source = CONSOLE.read_text(encoding="utf-8")
    formatter = _function(source, "function nutrientCellValue(", "function renderNutrientHeaders(")
    assert "Number.isFinite(row.cost.amount)" in formatter
    assert "row.cost.currency_code" in formatter
    assert 'row.cost_status === "currency_unclassified"' in formatter
    assert 'Withheld: currency unclassified' in formatter
    assert "innerHTML" not in formatter
    assert "cell.textContent = nutrientCellValue(record, key)" in source


def test_view_location_refresh_and_paging_handlers_and_script_contracts():
    source = CONSOLE.read_text(encoding="utf-8")
    bootstrap = _function(source, "async function loadSession()", "document.querySelector(\"#coordination-summary-refresh\")")
    assert "for (const locationId of nutrientOperationsLocationIds)" in bootstrap
    assert "nutrientOperationsLocation.append(option)" in bootstrap
    assert "await loadNutrientRecords()" in bootstrap
    assert 'nutrientOperationsLocation.addEventListener("change", () => loadNutrientRecords())' in source
    assert 'nutrientOperationsView.addEventListener("change", () => loadNutrientRecords())' in source
    assert 'nutrientOperationsMore.addEventListener("click", () => loadNutrientRecords(true))' in source
    ids = re.findall(r'\bid="([^\"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"

    node = shutil.which("node")
    if node is None:
        return
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
