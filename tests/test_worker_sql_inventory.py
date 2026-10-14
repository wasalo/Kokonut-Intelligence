"""Direct worker SQL inventory stays deterministic and avoids query contents."""

from __future__ import annotations

import json
import re

from scripts.worker_source_closure import build_inventory as build_source_closure
from scripts.worker_sql_inventory import ROOT, _serialize, build_inventory

INVENTORY_PATH = ROOT / "docs" / "refactor" / "worker-sql-inventory.json"


def _load_inventory() -> dict:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def test_saved_worker_sql_inventory_matches_current_sources():
    saved = INVENTORY_PATH.read_text(encoding="utf-8")
    assert saved == _serialize(build_inventory())


def test_worker_sql_inventory_covers_source_closure_and_all_execution_sites():
    inventory = _load_inventory()
    closure = build_source_closure()
    expected_operations = {f"{operation['kind']}:{operation['name']}" for operation in closure["operations"]}
    expected_sources = {source for operation in closure["operations"] for source in operation["source_files"]}
    sites = inventory["execution_sites"]

    assert inventory["summary"]["operation_roots"] == len(closure["operations"])
    assert inventory["summary"]["source_files"] == len(expected_sources)
    assert {site["source"] for site in sites} <= expected_sources
    assert len({site["id"] for site in sites}) == len(sites)
    for site in sites:
        assert site["operation_refs"]
        assert set(site["operation_refs"]) <= expected_operations
        assert (ROOT / site["source"]).is_file()
        assert site["expression_kind"] in {"literal", "fstring", "composed", "composed_or_variable"}
        assert isinstance(site["candidate_relations"], list)
        assert "sql" not in site and "query" not in site
        if site["static_sql_sha256"] is not None:
            assert re.fullmatch(r"[0-9a-f]{64}", site["static_sql_sha256"])


def test_dynamic_sql_call_sites_are_visible_without_persisting_query_text():
    inventory = _load_inventory()
    dynamic = [site for site in inventory["execution_sites"] if site["expression_kind"] != "literal"]

    assert dynamic
    assert inventory["summary"]["composed_or_variable_sites"] == len(dynamic)
    assert all(site["static_sql_sha256"] is None for site in dynamic)
    assert all(site["statement_kind"] for site in dynamic)
