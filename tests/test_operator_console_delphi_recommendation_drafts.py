"""Console contracts for location-scoped Delphi recommendation drafts."""

import re
from collections import Counter
from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def _function(source: str, declaration: str, next_declaration: str) -> str:
    start = source.index(declaration)
    end = source.index(next_declaration, start)
    return source[start:end]


def test_draft_form_is_gated_by_its_own_exact_location_grant():
    source = CONSOLE.read_text(encoding="utf-8")
    panel_match = re.search(
        r'<section id="delphi-recommendation-draft-create".*?</section>',
        source,
        re.DOTALL,
    )
    assert panel_match is not None
    panel = panel_match.group()
    assert 'scope.resource === "delphi" && scope.action === "draft"' in source
    assert "delphiRecommendationDraftLocations.has(locationId)" in source
    assert "Draft creation never approves or publishes the text" in panel
    assert "independent reviewer must decide it" in panel
    assert 'scope.action === "review"' in source
    assert "innerHTML" not in panel


def test_study_picker_uses_location_scoped_no_store_pagination():
    source = CONSOLE.read_text(encoding="utf-8")
    reader = _function(
        source,
        "async function loadDelphiRecommendationDraftStudies(append = false)",
        "async function submitDelphiRecommendationDraft()",
    )
    assert "delphiRecommendationDraftLocations.has(locationId)" in reader
    assert '`/operator/api/delphi/${encodeURIComponent(locationId)}/draft-studies?${params}`' in reader
    assert 'new URLSearchParams({ limit: "50", offset: String(delphiRecommendationDraftStudyOffset) })' in reader
    assert 'credentials: "same-origin"' in reader
    assert 'cache: "no-store"' in reader
    assert "delphiRecommendationDraftStudyOffset += studies.length" in reader
    assert 'delphiRecommendationDraftStudiesMore.hidden = result.has_more !== true' in reader
    assert "option.textContent" in reader
    assert "innerHTML" not in reader


def test_draft_submit_uses_csrf_no_store_and_retry_stable_request_id():
    source = CONSOLE.read_text(encoding="utf-8")
    submitter = _function(
        source,
        "async function submitDelphiRecommendationDraft()",
        "async function submitDelphiRecommendationDecision(",
    )
    assert "delphiRecommendationDraftLocations.has(locationId)" in submitter
    assert "delphiRecommendationDraftRequestIds.get(requestKey)" in submitter
    assert "delphiRecommendationDraftRequestIds.set(requestKey, requestId)" in submitter
    assert "delphiRecommendationDraftRequestIds.delete(requestKey)" in submitter
    assert '"X-CSRF-Token": csrf' in submitter
    assert 'cache: "no-store"' in submitter
    assert 'method: "POST"' in submitter
    assert 'credentials: "same-origin"' in submitter
    assert "request_id: requestId" in submitter
    assert "summary: summary || null" in submitter
    assert "recommendation_text: recommendationText" in submitter
    assert "nothing was published" in submitter
    assert "/decision" not in submitter
    assert "decision:" not in submitter


def test_draft_form_controls_are_unique_and_pagination_events_are_wired():
    source = CONSOLE.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', source)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"
    for element_id in (
        "delphi-recommendation-draft-create",
        "delphi-recommendation-draft-location",
        "delphi-recommendation-draft-study",
        "delphi-recommendation-draft-studies-more",
        "delphi-recommendation-draft-summary",
        "delphi-recommendation-draft-text",
        "delphi-recommendation-draft-submit",
        "delphi-recommendation-draft-status",
    ):
        assert f'id="{element_id}"' in source
    assert 'delphiRecommendationDraftLocation.addEventListener("change", () => loadDelphiRecommendationDraftStudies())' in source
    assert 'delphiRecommendationDraftStudiesMore.addEventListener("click", () => loadDelphiRecommendationDraftStudies(true))' in source
    assert 'delphiRecommendationDraftSubmit.addEventListener("click", submitDelphiRecommendationDraft)' in source
