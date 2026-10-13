"""Source-level contract checks for the governed farm-activity console."""

from html.parser import HTMLParser
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


class _ElementIndex(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.elements[element_id] = (tag, attributes)


def test_draft_editor_is_hidden_by_default_and_exposes_only_declared_form_fields():
    source = CONSOLE.read_text()
    parser = _ElementIndex()
    parser.feed(source)

    tag, editor = parser.elements["farm-activity-draft-edit-form"]
    assert tag == "form"
    assert "hidden" in editor
    for element_id in (
        "farm-activity-edit-type",
        "farm-activity-edit-date",
        "farm-activity-edit-description",
        "farm-activity-edit-labor-hours",
        "farm-activity-edit-notes",
    ):
        assert element_id in parser.elements

    reason_tag, reason = parser.elements["farm-activity-edit-reason"]
    assert reason_tag == "textarea"
    assert "required" in reason
    assert reason.get("maxlength") == "2000"


def test_console_filters_editor_by_edit_and_private_detail_grants_and_draft_state():
    source = CONSOLE.read_text()

    assert 'scope.action === "edit_draft"' in source
    assert "farmActivityDetailLocations.has(locationId)" in source
    assert "mobilePayloadLocations.has(locationId)" in source
    assert 'activity.status !== "draft"' in source
    assert "!farmActivityEditLocations.has(locationId)" in source


def test_console_submits_reasoned_same_origin_patch_with_csrf_and_refreshes_detail():
    source = CONSOLE.read_text()
    start = source.index("async function saveFarmActivityDraftEdit(event)")
    end = source.index("async function loadMobileQueue()", start)
    editor = source[start:end]

    assert "A correction reason is required." in editor
    assert "method: \"PATCH\"" in editor
    assert "credentials: \"same-origin\"" in editor
    assert "cache: \"no-store\"" in editor
    assert '"X-CSRF-Token": csrf' in editor
    assert "JSON.stringify({ content, reason })" in editor
    assert "await refreshFarmActivity()" in editor
    assert "await loadFarmActivity(activityId)" in editor

