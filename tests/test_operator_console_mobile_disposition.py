"""Source-level contract checks for the mobile disposition inventory UI."""

from pathlib import Path

CONSOLE = Path(__file__).parents[1] / "apps/operator-console/index.html"


def test_inventory_action_uses_its_separate_location_grant():
    source = CONSOLE.read_text()

    assert 'scope.resource === "mobile_collection_retention"' in source
    assert 'scope.action === "inventory"' in source
    assert 'mobileDispositionLocations.has(locationId)' in source
    assert 'inventory.textContent = "Disposition inventory"' in source
    assert "mobilePayloadLocations.has(locationId)" not in source[
        source.index('if (mobileDispositionLocations.has(locationId))') :
        source.index("row.append(form, collected", source.index('if (mobileDispositionLocations.has(locationId))'))
    ]


def test_inventory_display_is_same_origin_read_only_and_content_safe():
    source = CONSOLE.read_text()
    start = source.index("async function loadMobileDispositionInventory(collectionId)")
    end = source.index('document.querySelector("#refresh")', start)
    inventory_reader = source[start:end]

    assert "/disposition-inventory?${params}" in inventory_reader
    assert 'mobileDispositionLocations.has(mobileReviewLocation.value)' in inventory_reader
    assert 'credentials: "same-origin"' in inventory_reader
    assert 'cache: "no-store"' in inventory_reader
    assert "mobileDispositionInventory.textContent = JSON.stringify(result.data, null, 2)" in inventory_reader
    assert "mobilePayloadLocations" not in inventory_reader
    assert "innerHTML" not in inventory_reader
    assert "Known direct database lineage only" in inventory_reader


def test_mobile_operations_inventory_requires_both_location_grants_and_uses_safe_dom():
    source = CONSOLE.read_text()
    start = source.index("async function loadMobileOperationsInventory()")
    end = source.index("async function loadMobileQueue()", start)
    inventory_reader = source[start:end]

    assert 'scope.resource === "mobile_device" && scope.action === "read"' in source
    assert 'scope.resource === "mobile_collection_review" && scope.action === "read"' in source
    assert "mobileReviewLocations.includes(locationId)" in source
    assert "&& /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(locationId)" in source
    assert "/operator/api/mobile/locations/${encodeURIComponent(locationId)}/inventory" in inventory_reader
    assert 'credentials: "same-origin"' in inventory_reader
    assert 'mobileOperations.hidden = false' in source
    assert '"pending_sync_count"' in inventory_reader
    assert '"ineligible_synced_count"' in inventory_reader
    assert "textContent" in inventory_reader
    assert "innerHTML" not in inventory_reader
