"""Focused Python SDK wire-contract parity tests independent of other suites."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path
from typing import Optional
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

SDK_PATH = Path(__file__).resolve().parents[1] / "sdk" / "python"
sys.path.insert(0, str(SDK_PATH))
KokonutClient = import_module("kokonut").KokonutClient


@pytest.mark.parametrize(
    ("fields", "expected_params", "expected_query"),
    [
        (None, {}, {}),
        ([], {"fields": "[]"}, {"fields": ["[]"]}),
        (["id", "name"], {"fields": "id,name"}, {"fields": ["id,name"]}),
    ],
)
def test_get_item_projection_wire_shape_matches_typescript(
    fields: Optional[list[str]],
    expected_params: dict[str, str],
    expected_query: dict[str, list[str]],
) -> None:
    client = KokonutClient("https://directus.invalid")
    response = Mock()
    response.ok = True
    response.json.return_value = {"data": {"id": "location-1"}}
    client.session.get = Mock(return_value=response)

    assert client.get_item("location", "location-1", fields=fields) == {
        "id": "location-1"
    }

    request = client.session.get.call_args
    assert request.args == ("https://directus.invalid/items/location/location-1",)
    assert request.kwargs["params"] == expected_params
    prepared = requests.Request(
        "GET", request.args[0], params=request.kwargs["params"]
    ).prepare()
    assert parse_qs(urlsplit(prepared.url).query) == expected_query
