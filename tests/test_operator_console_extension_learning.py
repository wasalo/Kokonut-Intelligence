"""Console contract for location-scoped extension learning reads."""

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


def test_learning_panel_is_hidden_until_exact_location_read_scope():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(r'<section id="extension-learning".*?</section>', source, re.DOTALL)
    assert panel is not None
    assert 'id="extension-learning" hidden' in panel.group()
    assert 'scope.resource === "extension_learning" && scope.action === "read"' in source
    assert "extensionLearningLocations = new Set(extensionLearningReadLocationIds)" in source
    assert "extensionLearningPeerNetworkCreateLocations = new Set(extensionLearningCreateLocationIds)" in source
    assert "...extensionLearningReadLocationIds" in source
    assert "...extensionLearningCreateLocationIds" in source
    assert "extensionLearning.hidden = false" in source
    assert "participant identities, individual scores, notes" in panel.group()


def test_summary_uses_protected_no_store_route_and_fixed_aggregate_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadExtensionLearningSummary(", "function renderExtensionLearningModule(")
    assert '`/operator/api/extension-learning/${encodeURIComponent(locationId)}/summary`' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "extensionLearningLocations.has(locationId)" in reader
    assert "requestVersion !== extensionLearningSummaryRequestVersion" in reader
    assert "locationId !== extensionLearningLocation.value" in reader
    assert reader.index("extensionLearningSummary.replaceChildren()") < reader.index("await fetch(")
    renderer = _function(source, "function renderExtensionLearningSummary(", "async function loadExtensionLearningSummary(")
    for key in ("learning_progress", "content_delivery", "assessments", "peer_networks"):
        assert f'["{key}"' in renderer
    for field in (
        "module_category", "progress_status", "enrollment_count", "delivery_channel",
        "delivery_status", "delivery_count", "assessment_type", "assessment_count",
        "scored_assessment_count", "network_type", "network_status", "network_count",
        "active_member_count",
    ):
        assert f'["{field}"' in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer
    for private_field in ("operator_id", "participant_id", "score", "notes", "device_id", "delivery_error"):
        assert f"row.{private_field}" not in renderer


def test_module_catalog_is_bounded_paged_and_renders_only_approved_fields():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(source, "async function loadExtensionLearningModules(", "function renderBusinessPlanningCanvas(")
    assert '`/operator/api/extension-learning/${encodeURIComponent(locationId)}/modules?${params}`' in reader
    assert 'new URLSearchParams({ limit: "25", offset: String(offset) })' in reader
    assert "result.has_more !== true" in reader
    assert "extensionLearningOffset > 10000" in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "requestVersion !== extensionLearningCatalogRequestVersion" in reader
    assert "locationId !== extensionLearningLocation.value" in reader
    assert "innerHTML" not in reader
    renderer = _function(source, "function renderExtensionLearningModule(", "async function loadExtensionLearningModules(")
    for field in ("module_name", "category", "difficulty", "content_type", "duration_minutes", "language"):
        assert f'["{field}"' in renderer or f"module.{field}" in renderer
    for private_field in ("module.id", "module.url", "module.description", "module.tags", "module.metadata"):
        assert private_field not in renderer
    assert "textContent" in renderer
    assert "innerHTML" not in renderer


def test_filter_controls_match_server_allowlists_and_refresh_handlers_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    for value in (
        "soil_health", "water_management", "pest_control", "post_harvest",
        "financial_literacy", "agroforestry", "climate_adaptation", "organic_practices",
        "record_keeping", "cooperative_management", "other", "beginner", "intermediate",
        "advanced", "video", "guide", "quiz", "interactive", "audio", "field_practice",
    ):
        assert f'value="{value}"' in source
    assert 'extensionLearningLocation.addEventListener("change"' in source
    assert 'extensionLearningMore.addEventListener("click", () => loadExtensionLearningModules(true))' in source
    assert 'document.querySelector("#extension-learning-refresh").addEventListener("click"' in source
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
