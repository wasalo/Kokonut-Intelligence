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
    assert "Summaries are location-scoped and aggregate-only." in parent.group()
    assert "Observation capture requires a separate create grant" in parent.group()


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
    assert 'pollinatorHealthLocation.addEventListener("change", () =>' in SOURCE
    ids = re.findall(r'\bid="([^"]+)"', SOURCE)
    duplicates = [element_id for element_id, count in Counter(ids).items() if count > 1]
    assert not duplicates, f"Duplicate operator console IDs: {duplicates}"


def test_pollinator_capture_is_separately_grant_gated_and_uses_stable_csrf_retry():
    assert 'scope.resource === "pollinator_health" && scope.action === "read"' in SOURCE
    assert 'scope.resource === "pollinator_health" && scope.action === "create"' in SOURCE
    assert 'id="pollinator-observation-capture" hidden' in SOURCE
    assert 'pollinatorObservationCapture.hidden = !canCreate' in SOURCE
    assert 'pollinatorHealthSummary.hidden = !canRead' in SOURCE
    submit = re.search(r"async function submitPollinatorObservation\(event\).*?\n      }", SOURCE, re.DOTALL)
    assert submit
    assert "pollinatorHealthCreateLocations.has(locationId)" in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert "pollinatorObservationPending.fingerprint !== fingerprint" in submit.group()
    assert 'result.status !== "recorded"' in submit.group()
    assert "Retrying unchanged input reuses the same request ID." in submit.group()
    assert 'await loadPollinatorHealthSummary()' in submit.group()
    assert 'pollinatorHealthLocation.addEventListener("change", () =>' in SOURCE
    for field in (
        "pollinator_type", "observation_method", "duration_minutes", "observation_date",
        "plot_id", "species_name", "weather_conditions", "temperature_c", "hive_record_id", "notes",
    ):
        assert f"{field}:" in submit.group()
    assert "It has not been verified or published." in submit.group()


def test_pesticide_report_capture_is_recorded_only_and_uses_same_create_boundary():
    assert 'id="pesticide-impact-capture" hidden' in SOURCE
    assert 'pesticideImpactCapture.hidden = !canCreate' in SOURCE
    assert "It does not approve or recommend pesticide use" in SOURCE
    assert "independent review" in SOURCE
    submit = re.search(r"async function submitPesticideImpactReport\(event\).*?\n      }", SOURCE, re.DOTALL)
    assert submit
    assert "pollinatorHealthCreateLocations.has(locationId)" in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert "pesticideImpactPending.fingerprint !== fingerprint" in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert 'result.status !== "recorded"' in submit.group()
    assert "Retrying unchanged input reuses the same request ID." in submit.group()
    assert "It has not been independently reviewed or published." in submit.group()
    assert "mortality_observed: pesticideImpactCaptureForm.querySelector" in submit.group()
    assert "toxicity_class:" in submit.group()


def test_habitat_capture_is_separately_grant_gated_and_explicitly_self_reported():
    assert 'id="pollinator-habitat-capture" hidden' in SOURCE
    assert "pollinatorHabitatCapture.hidden = !canCreate" in SOURCE
    assert "self-reported habitat inventory as active" in SOURCE
    assert "does not mean the habitat or an ecological outcome has been independently verified" in SOURCE
    submit = re.search(r"async function submitPollinatorHabitat\(event\).*?\n      }", SOURCE, re.DOTALL)
    assert submit
    assert "pollinatorHealthCreateLocations.has(locationId)" in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert "pollinatorHabitatPending.fingerprint !== fingerprint" in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert 'result.status !== "active"' in submit.group()
    assert "Retrying unchanged input reuses the same request ID." in submit.group()
    assert "has not been independently verified." in submit.group()
    assert "plant_species:" in submit.group()
    assert 'water_source: pollinatorHabitatCaptureForm.querySelector' in submit.group()


def test_hive_capture_is_grant_gated_self_reported_and_uses_stable_retry():
    assert 'id="pollinator-hive-capture" hidden' in SOURCE
    assert "pollinatorHiveCapture.hidden = !canCreate" in SOURCE
    assert "self-reported and have not been independently verified" in SOURCE
    submit = re.search(r"async function submitPollinatorHive\(event\).*?\n      }", SOURCE, re.DOTALL)
    assert submit
    assert "pollinatorHealthCreateLocations.has(locationId)" in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert "pollinatorHivePending.fingerprint !== fingerprint" in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert 'result.status !== "active"' in submit.group()
    assert "Retrying unchanged input reuses the same request ID." in submit.group()
    assert "have not been independently verified" in submit.group()
    assert "colony_strength_score:" in submit.group()
    assert "pollinatorHiveCaptureForm.reset()" in submit.group()


def test_hive_inspection_capture_is_grant_gated_recorded_and_uses_stable_retry():
    assert 'id="pollinator-hive-inspection-capture" hidden' in SOURCE
    assert "pollinatorHiveInspectionCapture.hidden = !canCreate" in SOURCE
    assert "do not independently verify hive health" in SOURCE
    submit = re.search(
        r"async function submitPollinatorHiveInspection\(event\).*?\n      }",
        SOURCE,
        re.DOTALL,
    )
    assert submit
    assert "pollinatorHealthCreateLocations.has(locationId)" in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert 'method: "POST", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert "pollinatorHiveInspectionPending.fingerprint !== fingerprint" in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert 'result.status !== "recorded"' in submit.group()
    assert "Retrying unchanged input reuses the same request ID." in submit.group()
    assert "independently verified" in submit.group()
    assert "Saving the inspection as a recorded observation" in submit.group()
    assert "pollinatorHiveInspectionForm.reset()" in submit.group()
    for field in (
        "inspection_date", "colony_strength", "colony_strength_score", "queen_status",
        "queen_seen", "varroa_count", "brood_pattern", "honey_stores", "disease_signs",
        "temperament", "population_estimate", "swarm_cells", "notes",
    ):
        assert f"{field}:" in submit.group()


def test_habitat_lifecycle_detail_and_edit_have_separate_grants_and_audited_updates():
    assert 'id="pollinator-habitat-management" hidden' in SOURCE
    assert 'pollinatorHabitatManagement.hidden = !canReadDetails' in SOURCE
    assert 'scope.action === "read_detail"' in SOURCE
    assert 'scope.action === "edit"' in SOURCE
    loader = re.search(
        r"async function loadPollinatorHealthHabitatDetails\(append = false\).*?\n      }",
        SOURCE,
        re.DOTALL,
    )
    assert loader
    assert 'cache: "no-store"' in loader.group()
    assert "pollinatorHealthEditLocations.has(locationId)" in loader.group()
    assert "item.plant_species" not in loader.group()
    submit = re.search(
        r"async function submitPollinatorHabitatLifecycle\(event\).*?\n      }",
        SOURCE,
        re.DOTALL,
    )
    assert submit
    assert "pollinatorHealthEditLocations.has(locationId)" in submit.group()
    assert 'method: "PATCH", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert "expected_updated_at" in submit.group()
    assert "does not verify ecological condition or outcomes" in SOURCE


def test_managed_hive_lifecycle_is_grant_gated_audited_and_separate_from_inspections():
    assert 'id="pollinator-hive-management" hidden' in SOURCE
    assert "pollinatorHiveManagement.hidden = !canReadDetails" in SOURCE
    loader = re.search(
        r"async function loadPollinatorHealthHiveDetails\(append = false\).*?\n      }",
        SOURCE,
        re.DOTALL,
    )
    assert loader
    assert "pollinatorHealthDetailLocations.has(locationId)" in loader.group()
    assert 'cache: "no-store"' in loader.group()
    assert "result.location_id !== locationId" in loader.group()
    assert "item.metadata" not in loader.group()
    submit = re.search(
        r"async function submitPollinatorHiveLifecycle\(event\).*?\n      }",
        SOURCE,
        re.DOTALL,
    )
    assert submit
    assert "pollinatorHealthEditLocations.has(locationId)" in submit.group()
    assert 'method: "PATCH", credentials: "same-origin", cache: "no-store"' in submit.group()
    assert '"X-CSRF-Token": csrf' in submit.group()
    assert "expected_updated_at" in submit.group()
    assert "crypto.randomUUID()" in submit.group()
    assert "does not verify colony health" in submit.group()
    assert "inspections remain separate recorded observations" in SOURCE


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
