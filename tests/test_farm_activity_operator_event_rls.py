"""Source contracts for the signed-location event-ledger RLS boundary."""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "schemas/postgres/728_farm_activity_operator_event_signed_location_rls.sql"
INVENTORY = ROOT / "docs/refactor/runtime-sql-inventory.json"
SERVICE = ROOT / "services/gateway/farm_activity_records.py"
CHECKER = ROOT / "scripts/check-farm-activity-operator-event-rls-disposable.py"
SCOPE_FUNCTION_MIGRATION = ROOT / "schemas/postgres/711_location_energy_reading_capture.sql"


def _function_nodes(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _ledger_query_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[int]:
    result = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        if child.func.attr != "execute":
            continue
        if any(
            isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and "farm_activity_operator_event" in value.value
            for value in ast.walk(child)
        ):
            result.append(child.lineno)
    return result


def _context_call_lines(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[int]:
    return [
        child.lineno
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_set_context"
    ]


def test_migration_forces_rls_and_requires_database_signed_location_context():
    sql = MIGRATION.read_text()
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL PRIVILEGES ON TABLE public.farm_activity_operator_event" in sql
    assert "REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I)" in sql
    assert "AS RESTRICTIVE" in sql
    assert "kokonut_security.current_tenant_context()" in sql
    assert "procedure.prosecdef" in sql
    assert "kokonut_mobile_context_owner" in sql
    assert "context.actor_type = 'operator'" in sql
    assert "context.location_id = farm_activity_operator_event.location_id" in sql
    assert "context.actor_id = farm_activity_operator_event.actor_operator_id" in sql
    assert "current_setting('kokonut.location_id'" not in sql
    assert "UPDATE public.farm_activity_operator_event" not in sql
    assert "DELETE FROM public.farm_activity_operator_event" not in sql


def test_inventory_keeps_the_four_direct_event_reads_within_the_gateway_service():
    inventory = json.loads(INVENTORY.read_text())
    sites = [
        site
        for site in inventory["execution_sites"]
        if "farm_activity_operator_event" in site.get("candidate_relations", [])
    ]
    assert len(sites) == 4
    assert {site["source"] for site in sites} == {"services/gateway/farm_activity_records.py"}
    assert {site["statement_kind"] for site in sites} == {"SELECT"}
    assert {site["scope"] for site in sites} == {
        "get_farm_activity_record",
        "create_farm_activity_record",
        "edit_farm_activity_record_draft",
        "transition_farm_activity_record",
    }


def test_each_direct_event_read_sets_operator_context_before_query():
    tree = ast.parse(SERVICE.read_text())
    functions = _function_nodes(tree)
    expected = {
        "get_farm_activity_record",
        "create_farm_activity_record",
        "edit_farm_activity_record_draft",
        "transition_farm_activity_record",
    }
    assert expected <= functions.keys()
    for name in expected:
        function = functions[name]
        query_lines = _ledger_query_lines(function)
        context_lines = _context_call_lines(function)
        assert query_lines, f"{name} no longer contains its inventoried event-ledger query"
        assert context_lines, f"{name} must set signed operator tenant context"
        assert min(context_lines) < min(query_lines), f"{name} reads the event ledger before signed context setup"

    context_helper = functions["_set_context"]
    assert any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "set_operator_tenant_context"
        for child in ast.walk(context_helper)
    )


def test_disposable_checker_uses_internal_only_network_and_cached_images():
    source = CHECKER.read_text()
    assert '"--internal"' in source
    assert '"--pull=never"' in source
    assert '"--publish"' not in source
    assert '"host_ports_published": False' in source


def test_checker_loads_exact_canonical_operator_scope_function():
    spec = importlib.util.spec_from_file_location("farm_activity_event_rls_checker", CHECKER)
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    migration = SCOPE_FUNCTION_MIGRATION.read_text()
    start = migration.index("CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(")
    end = migration.index(
        "GRANT EXECUTE ON FUNCTION public.operator_scope_grant_allows(UUID, TEXT, TEXT, UUID)",
        start,
    )
    assert checker._canonical_operator_scope_grant_function_sql() == migration[start:end].strip()
