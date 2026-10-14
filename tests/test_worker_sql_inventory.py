"""Direct worker SQL inventory stays deterministic and avoids query contents."""

from __future__ import annotations

import ast
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


def test_dynamic_sql_review_categories_remain_explicit():
    inventory = _load_inventory()
    dynamic = [site for site in inventory["execution_sites"] if site["expression_kind"] != "literal"]
    by_source: dict[str, list[dict]] = {}
    for site in dynamic:
        by_source.setdefault(site["source"], []).append(site)

    assert {source: len(sites) for source, sites in by_source.items()} == {
        "services/analytics/reporting_reader.py": 3,
        "services/cache/cache.py": 1,
        "services/common/database.py": 3,
        "services/events/fork_detector.py": 1,
        "services/events/insight_transfer.py": 2,
        "services/ingestion/data_freshness.py": 5,
        "services/ingestion/ml_anomaly_detector.py": 1,
        "services/metrics/calculators/allocated_shared_cost.py": 1,
        "services/metrics/calculators/attestation_coverage.py": 2,
        "services/metrics/calculators/crop_revenue.py": 1,
        "services/metrics/calculators/digital_lego.py": 2,
        "services/metrics/calculators/direct_crop_cost.py": 1,
        "services/metrics/calculators/first_time_through_yield.py": 1,
        "services/metrics/calculators/governed_lead_time.py": 1,
        "services/metrics/calculators/loss_rate_pct.py": 1,
        "services/metrics/calculators/net_crop_revenue.py": 1,
        "services/metrics/calculators/rework_rate.py": 1,
        "services/metrics/calculators/value_flowed.py": 2,
    }
    assert {site["expression_kind"] for site in by_source["services/common/database.py"]} == {"composed_or_variable"}
    assert (
        sum(site["expression_kind"] == "composed" for site in by_source["services/analytics/reporting_reader.py"]) == 1
    )
    assert sum(site["expression_kind"] == "fstring" for site in by_source["services/ingestion/data_freshness.py"]) == 4


def test_generic_database_sql_wrappers_have_no_unreviewed_worker_callsite():
    closure = build_source_closure()
    sources = {source for operation in closure["operations"] for source in operation["source_files"]}
    query_callers = []
    connection_execute_callers = []

    for source in sorted(sources):
        path = ROOT / source
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=source)
        imported_query_names = set()
        connection_factory_names = set()
        database_module_aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "services.common.database":
                        database_module_aliases[alias.asname or "services"] = alias.name if alias.asname else "services"
                continue
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "services.common.database":
                for alias in node.names:
                    if alias.name in {"query", "query_one"}:
                        imported_query_names.add(alias.asname or alias.name)
                    if alias.name == "get_connection":
                        connection_factory_names.add(alias.asname or alias.name)
            elif node.module == "services.common" and any(alias.name == "database" for alias in node.names):
                for alias in node.names:
                    if alias.name == "database":
                        database_module_aliases[alias.asname or alias.name] = "services.common.database"
            elif node.module == "services.common.cli":
                for alias in node.names:
                    if alias.name == "get_connection":
                        connection_factory_names.add(alias.asname or alias.name)

        connection_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    context = item.context_expr
                    if (
                        isinstance(context, ast.Call)
                        and isinstance(context.func, ast.Name)
                        and context.func.id in connection_factory_names
                        and isinstance(item.optional_vars, ast.Name)
                    ):
                        connection_names.add(item.optional_vars.id)
            elif (
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in connection_factory_names
            ):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                connection_names.update(target.id for target in targets if isinstance(target, ast.Name))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in imported_query_names:
                query_callers.append(f"{source}:{node.lineno}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in {"query", "query_one"}:
                expression = ast.unparse(node.func)
                prefix, separator, suffix = expression.partition(".")
                module = database_module_aliases.get(prefix)
                resolved = f"{module}.{suffix}" if module and separator else expression
                if resolved in {
                    "services.common.database.query",
                    "services.common.database.query_one",
                }:
                    query_callers.append(f"{source}:{node.lineno}")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in connection_names
            ):
                query_arg = node.args[0] if node.args else None
                if not isinstance(query_arg, ast.Constant) or not isinstance(query_arg.value, str):
                    expression_kind = "dynamic"
                else:
                    expression_kind = "literal"
                connection_execute_callers.append((source, node.lineno, expression_kind))

    assert query_callers == []
    assert connection_execute_callers == [("services/metrics/cli.py", 43, "literal")]
