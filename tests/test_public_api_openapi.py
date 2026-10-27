"""Regression checks for the intentionally public native API snapshot."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_public_api_openapi import build_public_api_spec

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_openapi_snapshot_matches_only_public_read_routes() -> None:
    spec = build_public_api_spec()
    checked_in = json.loads(
        (ROOT / "docs/refactor/native-public-api-v1.openapi.json").read_text(
            encoding="utf-8"
        )
    )

    assert spec == checked_in
    assert "/api/v1/governance/baal/config" not in spec["paths"]
    assert "/api/v1/governance/baal/proposals" not in spec["paths"]
    for operations in spec["paths"].values():
        assert set(operations) == {"get"}
        policy = operations["get"]["x-kokonut-policy"]
        assert policy["public"] is True
        assert policy["action"] == "read"
