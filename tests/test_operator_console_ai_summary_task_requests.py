"""Console contract for authenticated, manually dispatched synthesis requests."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from services.gateway.ai_summary_task_request import TASK_SUMMARY_TYPES

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


class _TaskOptions(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_select = False
        self.options: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "select" and attributes.get("id") == "ai-summary-task-request-key":
            self.in_select = True
        elif tag == "option" and self.in_select:
            self.options[attributes["value"]] = attributes["data-summary-type"]

    def handle_endtag(self, tag):
        if tag == "select" and self.in_select:
            self.in_select = False


def _request_submitter(source: str) -> str:
    start = source.index("async function submitAiSummaryTaskRequest()")
    end = source.index("async function loadGovernanceTensionQueue(", start)
    return source[start:end]


def test_synthesis_task_options_match_registered_gateway_receipt_contract():
    source = CONSOLE.read_text(encoding="utf-8")
    parser = _TaskOptions()
    parser.feed(source)

    expected = {
        task_key: next(iter(summary_types))
        for task_key, summary_types in TASK_SUMMARY_TYPES.items()
        if task_key != "ai_summary_synthesis"
    }
    assert parser.options == expected


def test_task_request_panel_is_grant_gated_and_does_not_claim_to_dispatch():
    source = CONSOLE.read_text(encoding="utf-8")
    panel = re.search(
        r'<section id="ai-summary-task-request".*?</section>\s*</section>',
        source,
        re.DOTALL,
    )
    assert panel is not None
    assert 'id="ai-summary-task-request" hidden' in panel.group()
    assert 'scope.resource === "ai_summary" && scope.action === "draft"' in source
    assert 'document.querySelector("#ai-summary-task-request").hidden = false' in source
    assert "does not start a worker" in panel.group()
    assert "No worker was started" in source
    assert "manual worker command" in panel.group().lower()


def test_request_uses_csrf_no_store_stable_retry_and_validates_receipt():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _request_submitter(source)
    assert "aiSummaryDraftLocations.has(locationId)" in submitter
    assert "aiSummaryTaskRequestIds.get(requestKey)" in submitter
    assert "aiSummaryTaskRequestIds.set(requestKey, requestId)" in submitter
    assert "aiSummaryTaskRequestIds.delete(requestKey)" in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert 'cache: "no-store"' in submitter
    assert "/synthesis-requests`" in submitter
    assert "result.request_id !== requestId" in submitter
    assert "result.location_id !== locationId" in submitter
    assert "result.task_key !== taskKey" in submitter
    assert "result.summary_type !== summaryType" in submitter
    assert 'result.status !== "authorized"' in submitter
    assert '"--persist-draft --source-only"' in submitter
    assert "innerHTML" not in submitter


def test_controls_are_unique_and_submission_and_copy_handlers_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    assert 'aiSummaryTaskRequestSubmit.addEventListener("click", submitAiSummaryTaskRequest)' in source
    assert '"#ai-summary-task-request-copy").addEventListener("click"' in source


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
