"""Keep the Directus extension host contract aligned with the pinned image."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_hook_extension_declares_the_exact_pinned_directus_host() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    package = json.loads((ROOT / "extensions/kokonut-hooks/package.json").read_text())

    match = re.search(r"(?m)^\s+image:\s+directus/directus:([^@\s]+)", compose)
    assert match is not None, "Directus image must remain pinned in the base Compose file"
    assert package["directus:extension"]["host"] == match.group(1)
