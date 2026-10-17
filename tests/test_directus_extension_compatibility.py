"""Keep the Directus extension host contract aligned with the pinned image."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_hook_extension_declares_the_exact_pinned_directus_host() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    package = json.loads((ROOT / "extensions/kokonut-hooks/package.json").read_text())

    image = compose["services"]["directus"]["image"]
    match = re.search(r"^directus/directus:([^@\s]+)", image)
    assert match is not None, "Directus image must remain pinned in the base Compose file"
    assert package["directus:extension"]["host"] == match.group(1)


def test_extensions_use_directus_12_discoverable_package_mounts() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    service = compose["services"]["directus"]
    mounts = set(service["volumes"])
    hook_package = json.loads((ROOT / "extensions/kokonut-hooks/package.json").read_text())
    endpoint_package = json.loads(
        (ROOT / "extensions/endpoints/kokonut-field-collector/package.json").read_text()
    )
    pinned_version = re.search(r"^directus/directus:([^@\s]+)", service["image"])
    assert pinned_version is not None

    assert hook_package["name"] == "directus-extension-kokonut-hooks"
    assert endpoint_package["name"] == "directus-extension-endpoint-kokonut-field-collector"
    assert hook_package["directus:extension"]["host"] == pinned_version.group(1)
    assert endpoint_package["directus:extension"]["host"] == pinned_version.group(1)
    assert endpoint_package["directus:extension"]["path"] == "index.js"
    assert (
        "./extensions/kokonut-hooks:/directus/extensions/directus-extension-kokonut-hooks:ro"
        in mounts
    )
    assert (
        "./extensions/endpoints/kokonut-field-collector:/directus/extensions/"
        "directus-extension-endpoint-kokonut-field-collector:ro"
    ) in mounts
    assert "./extensions:/directus/extensions" not in mounts
    assert "directus-extension build" in hook_package["scripts"]["build"]
