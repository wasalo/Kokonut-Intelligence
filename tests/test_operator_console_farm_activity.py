"""Console contracts for the Gateway farm-activity operations panel."""

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


def test_operations_panel_is_separate_and_requires_explicit_location_grants():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="farm-activity-record-operations".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )

    assert panel is not None
    assert "outside the consent-aware Field Collector workflow" in panel.group()
    assert 'scope.resource === "farm_activity" && scope.action === "read"' in source
    assert 'scope.resource === "farm_activity" && scope.action === "read_published"' in source
    assert 'scope.resource === "farm_activity" && scope.action === "read_detail"' in source
    assert 'scope.resource === "farm_activity" && scope.action === "read_published_detail"' in source
    assert 'scope.resource === "farm_activity" && scope.action === "create_draft"' in source
    assert 'scope.resource === "farm_activity" && scope.action === "edit_draft"' in source
    assert "farmActivityRecordCreateLocations.has(locationId)" in source
    assert "farmActivityRecordEditLocations.has(locationId)" in source
    assert "farmActivityRecordCreateLocations.has(locationId))" in source


def test_record_list_and_detail_use_location_scoped_safe_read_routes():
    source = CONSOLE.read_text(encoding="utf-8")
    list_reader = _function(
        source,
        "async function refreshFarmActivityRecords()",
        "async function loadFarmActivityRecord(activityId)",
    )
    detail_reader = _function(
        source,
        "async function loadFarmActivityRecord(activityId)",
        "function renderFarmActivityRecordActions()",
    )

    assert 'new URLSearchParams({ location_id: locationId, limit: "50" })' in list_reader
    assert '"/operator/api/farm-activity-records"' in list_reader
    assert '"/operator/api/farm-activity-records/published"' in list_reader
    assert "farmActivityRecordReadLocations.has(locationId)" in list_reader
    assert "farmActivityRecordPublishedLocations.has(locationId)" in list_reader
    assert 'credentials: "same-origin"' in list_reader
    assert 'cache: "no-store"' in list_reader
    assert "name.textContent = activity.activity_type" in list_reader
    assert "innerHTML" not in list_reader
    assert "farmActivityRecordDetailLocations.has(locationId)" in detail_reader
    assert "farmActivityRecordPublishedDetailLocations.has(locationId)" in detail_reader
    assert '`/operator/api/farm-activity-records/published/${encodeURIComponent(activityId)}`' in detail_reader
    assert '`/operator/api/farm-activity-records/${encodeURIComponent(activityId)}`' in detail_reader
    assert 'credentials: "same-origin"' in detail_reader
    assert 'cache: "no-store"' in detail_reader
    assert "farmActivityRecordContent.textContent = JSON.stringify(content, null, 2)" in detail_reader
    assert "item.append(heading, reason)" in detail_reader
    assert "innerHTML" not in detail_reader


def test_draft_creation_and_correction_are_csrf_protected_and_audited():
    source = CONSOLE.read_text(encoding="utf-8")
    handlers = _function(
        source,
        'farmActivityRecordCreateForm.addEventListener("submit", async (event) => {',
        'farmActivityPromoteForm.addEventListener("submit", async (event) => {',
    )
    editor = _function(
        source,
        "async function saveFarmActivityRecordDraft(event)",
        "async function transitionFarmActivityRecord(action)",
    )

    assert "farmActivityRecordCreateLocations.has(locationId)" in handlers
    assert "POST" in handlers
    assert 'fetch(`/operator/api/farm-activity-records?${params}`' in handlers
    assert 'credentials: "same-origin"' in handlers
    assert 'cache: "no-store"' in handlers
    assert '"X-CSRF-Token": csrf' in handlers
    assert "body: JSON.stringify({ content })" in handlers
    assert 'farmActivityRecordFormContent("create")' in handlers
    assert "Private draft created with an append-only operator event." in handlers
    assert "farmActivityRecordEditLocations.has(locationId)" in editor
    assert '"PATCH"' in editor
    assert '`/operator/api/farm-activity-records/${encodeURIComponent(activity.id)}/draft?${params}`' in editor
    assert '"X-CSRF-Token": csrf' in editor
    assert "body: JSON.stringify({ content, reason })" in editor
    assert 'farmActivityRecordFormContent("edit")' in editor
    assert 'if (!reason)' in editor
    assert "Correction saved with an append-only operator event." in editor

    content_builder = _function(
        source,
        "function farmActivityRecordFormContent(mode)",
        "async function refreshFarmActivityRecords()",
    )
    assert 'plot_id: optionalUuid("plot", "Plot ID")' in content_builder
    assert 'crop_cycle_id: optionalUuid("crop-cycle", "Crop cycle ID")' in content_builder
    assert 'farm_task_id: optionalUuid("task", "Farm task ID")' in content_builder
    assert "materials_used: materials" in content_builder
    assert "evidence_urls: evidence" in content_builder
    assert "JSON.parse(materialsText)" in content_builder
    assert "evidence.length > 100" in content_builder
    assert "url.length > 2048" in content_builder


def test_lifecycle_buttons_follow_state_grants_and_human_reason_boundaries():
    source = CONSOLE.read_text(encoding="utf-8")
    renderer = _function(
        source,
        "function renderFarmActivityRecordActions()",
        "async function saveFarmActivityRecordDraft(event)",
    )
    transition = _function(
        source,
        "async function transitionFarmActivityRecord(action)",
        "async function loadMobileOperationsInventory()",
    )

    for status in ('activity.status === "draft"', 'activity.status === "submitted"',
                   'activity.status === "verified"', 'activity.status === "rejected"'):
        assert status in renderer
    assert "farmActivityRecordActionLocations.get(action)?.has(locationId)" in renderer
    for action in ("submit", "verify", "reject", "request-rework", "publish", "close-exception"):
        assert f'"{action}"' in renderer
    assert '"reject", "request-rework", "close-exception"' in transition
    assert "A reason is required for this decision." in transition
    assert "window.confirm(confirmations[action])" in transition
    assert '`/operator/api/farm-activity-records/${encodeURIComponent(activity.id)}/${action}?${params}`' in transition
    assert '"X-CSRF-Token": csrf' in transition
    assert 'cache: "no-store"' in transition


def test_panel_dom_ids_and_refresh_detail_actions_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    setup = _function(
        source,
        'document.querySelector("#farm-activity-record-refresh").addEventListener',
        'farmActivityPromoteForm.addEventListener("submit", async (event) => {',
    )
    list_reader = _function(
        source,
        "async function refreshFarmActivityRecords()",
        "async function loadFarmActivityRecord(activityId)",
    )
    create_handler = _function(
        source,
        'farmActivityRecordCreateForm.addEventListener("submit", async (event) => {',
        'farmActivityPromoteForm.addEventListener("submit", async (event) => {',
    )

    assert not duplicates, f"Duplicate console DOM ids: {duplicates}"
    for element_id in (
        "farm-activity-record-operations",
        "farm-activity-record-location",
        "farm-activity-record-refresh",
        "farm-activity-record-queue",
        "farm-activity-record-detail",
        "farm-activity-record-events",
        "farm-activity-record-create-form",
        "farm-activity-record-create-plot",
        "farm-activity-record-create-crop-cycle",
        "farm-activity-record-create-task",
        "farm-activity-record-create-materials",
        "farm-activity-record-create-evidence",
        "farm-activity-record-edit-form",
        "farm-activity-record-edit-plot",
        "farm-activity-record-edit-crop-cycle",
        "farm-activity-record-edit-task",
        "farm-activity-record-edit-materials",
        "farm-activity-record-edit-evidence",
        "farm-activity-record-transition-actions",
    ):
        assert f'id="{element_id}"' in source
    assert "refreshFarmActivityRecords" in setup
    assert "farmActivityRecordLocation.addEventListener(\"change\", refreshFarmActivityRecords)" in setup
    assert 'open.addEventListener("click", () => loadFarmActivityRecord(activity.id))' in list_reader
    assert "row.append(name, date, lifecycle, source, updated, action)" in list_reader
    assert "await refreshFarmActivityRecords();" in create_handler
    assert "await loadFarmActivityRecord(result.data.id);" in create_handler


def test_task_link_is_restored_when_editing_and_sent_on_create_and_update():
    source = CONSOLE.read_text(encoding="utf-8")
    detail_reader = _function(
        source,
        "async function loadFarmActivityRecord(activityId)",
        "function renderFarmActivityRecordActions()",
    )
    content_builder = _function(
        source,
        "function farmActivityRecordFormContent(mode)",
        "async function refreshFarmActivityRecords()",
    )
    assert 'document.querySelector("#farm-activity-record-edit-task").value = currentFarmActivityRecord.farm_task_id || ""' in detail_reader
    assert 'farm_task_id: optionalUuid("task", "Farm task ID")' in content_builder


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
