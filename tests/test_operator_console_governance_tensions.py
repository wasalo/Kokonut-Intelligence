"""Console contract for read-only CAP-024 governance tension review."""

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


def test_governance_review_panel_is_read_only_and_grant_scoped():
    source = CONSOLE.read_text(encoding="utf-8")
    panel_match = re.search(
        r'<section id="governance-tension-review".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )
    assert panel_match is not None
    panel = panel_match.group()
    assert "Reporter identities, evidence payloads, and private event notes are omitted." in panel
    assert "does not triage, assign, resolve, verify, or approve tensions" in panel
    assert 'scope.resource === "governance_tension" && scope.action === "read"' in source
    assert "governanceTensionReadLocations.has(locationId)" in source
    assert "innerHTML" not in source


def test_queue_and_detail_use_private_scoped_no_store_routes():
    source = CONSOLE.read_text(encoding="utf-8")
    queue_reader = _function(
        source,
        "async function loadGovernanceTensionQueue(append = false)",
        "async function loadGovernanceTensionDetail(tensionId)",
    )
    detail_reader = _function(
        source,
        "async function loadGovernanceTensionDetail(tensionId)",
        "async function loadQueue()",
    )
    assert "governanceTensionReadLocations.has(locationId)" in queue_reader
    assert '`/operator/api/governance/${encodeURIComponent(locationId)}/tensions?${params}`' in queue_reader
    assert 'params.set("cursor", governanceTensionNextCursor)' in queue_reader
    assert 'params.set("status", governanceTensionStatusFilter.value)' in queue_reader
    assert 'cache: "no-store"' in queue_reader
    assert 'credentials: "same-origin"' in queue_reader
    assert 'open.textContent = "Review"' in queue_reader
    assert "innerHTML" not in queue_reader
    assert '`/operator/api/governance/${encodeURIComponent(locationId)}/tensions/${encodeURIComponent(tensionId)}`' in detail_reader
    assert 'cache: "no-store"' in detail_reader
    assert 'credentials: "same-origin"' in detail_reader
    assert "governanceTensionDescription.textContent = tension.description" in detail_reader
    assert "event.actor_party_id" not in detail_reader
    assert "event.note" not in detail_reader
    assert "innerHTML" not in detail_reader


def test_console_ids_are_unique_and_queue_controls_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "governance-tension-review",
        "governance-tension-location",
        "governance-tension-status-filter",
        "governance-tension-refresh",
        "governance-tension-queue",
        "governance-tension-more",
        "governance-tension-detail",
        "governance-tension-fields",
        "governance-tension-description",
        "governance-tension-events",
    ):
        assert f'id="{element_id}"' in source
    assert 'governanceTensionLocation.addEventListener("change", () => loadGovernanceTensionQueue())' in source
    assert 'governanceTensionStatusFilter.addEventListener("change", () => loadGovernanceTensionQueue())' in source
    assert 'governanceTensionMore.addEventListener("click", () => loadGovernanceTensionQueue(true))' in source


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
