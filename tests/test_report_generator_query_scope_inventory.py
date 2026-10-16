"""Source-only query-scope inventory tests; no service imports or database access."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_generator_query_scope_inventory import (  # noqa: E402
    analyze_function_source,
    build_inventory,
    main,
)


def test_classifier_finds_bound_location_filter_and_allows_explicit_global_rows():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    cur = conn.cursor()
    cur.execute("SELECT id FROM location WHERE id = %s", (location_id,))
    params = (location_id,)
    query = "SELECT * FROM v_report WHERE location_id = %s OR location_id IS NULL"
    cur.execute(query, params)
    cur.execute("SELECT * FROM v_report WHERE location_id = %s", ("all",))
    cur.execute("SELECT * FROM shared_reference")
''',
        "generate",
    )

    assert analysis["classification"] == "mixed_direct_query_scope"
    assert analysis["direct_query_count"] == 4
    assert analysis["queries_with_bound_location_scope_signal"] == 2
    assert analysis["queries"][0]["location_row_lookup_by_id"] is True
    assert analysis["queries"][0]["bound_location_scope_signal"] is True
    assert analysis["queries"][1]["location_predicate_visible"] is True
    assert analysis["queries"][1]["global_null_rows_allowed"] is True
    assert analysis["queries"][1]["location_id_in_bound_expression"] is True
    assert analysis["queries"][2]["location_predicate_visible"] is True
    assert analysis["queries"][2]["location_id_in_bound_expression"] is False
    assert analysis["queries"][2]["bound_location_scope_signal"] is False
    assert analysis["queries"][3]["bound_location_scope_signal"] is False


def test_classifier_resolves_fstrings_and_marks_dynamic_relations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, view_name):
    cur = conn.cursor()
    params = (location_id,)
    where = "location_id = %s"
    sql = f"SELECT * FROM v_report WHERE {where}"
    cur.execute(sql, params)
    cur.execute(f"SELECT * FROM {view_name}")
''',
        "generate",
    )

    assert analysis["classification"] == "partial_or_unresolved_direct_query_scope"
    assert analysis["queries"][0]["location_predicate_visible"] is True
    assert analysis["queries"][0]["location_id_in_bound_expression"] is True
    assert analysis["queries"][0]["relations"] == ["v_report"]
    assert analysis["queries"][1]["sql_source"] == "dynamic_or_unresolved"
    assert analysis["unresolved_query_count"] == 1


def test_classifier_marks_query_and_bind_added_only_for_location_scope():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    query = "SELECT * FROM v_report"
    params = []
    if location_id:
        query += " WHERE location_id = %s"
        params.append(location_id)
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    assert analysis["classification"] == "conditional_direct_query_scope"
    assert analysis["conditional_scope_query_count"] == 1
    assert analysis["queries"][0]["location_predicate_visible"] is True
    assert analysis["queries"][0]["location_id_in_bound_expression"] is True
    assert analysis["queries"][0]["location_scope_conditionally_added"] is True
    assert analysis["queries"][0]["bound_location_scope_signal"] is True


def test_classifier_recognizes_location_scopes_expressed_through_indirect_keys():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM v_scope WHERE scope_type = 'location' AND scope_id = %s",
        (location_id,),
    )
    cur.execute(
        "SELECT * FROM party_identifier WHERE identifier_type = 'location_id' AND identifier_value = %s",
        (location_id,),
    )
''',
        "generate",
    )

    assert analysis["direct_query_count"] == 2
    assert analysis["queries_with_bound_location_scope_signal"] == 2
    assert all(query["indirect_location_scope_visible"] for query in analysis["queries"])


def test_classifier_recognizes_location_subject_id_scope():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM attestation_record "
        "WHERE subject_type = 'location' AND subject_id = %s",
        (location_id,),
    )
    cur.execute(
        "SELECT * FROM attestation_record "
        "WHERE subject_type = 'person' AND subject_id = %s",
        (location_id,),
    )
''',
        "generate",
    )

    assert analysis["direct_query_count"] == 2
    assert analysis["queries_with_bound_location_scope_signal"] == 1
    assert analysis["queries"][0]["indirect_location_scope_visible"] is True
    assert analysis["queries"][0]["bound_location_scope_signal"] is True
    assert analysis["queries"][1]["indirect_location_scope_visible"] is False


def test_registry_wide_inventory_links_direct_queries_to_actual_source_lines():
    inventory = build_inventory()

    assert inventory["summary"]["registered_report_types"] == 94
    assert inventory["summary"]["direct_query_sites"] == 177
    assert inventory["summary"]["query_sites_with_bound_location_scope_signal"] > 0
    assert inventory["summary"]["unresolved_query_sites"] == 0
    reports = {report["report_type"]: report for report in inventory["reports"]}
    farm_summary = reports["farm_summary"]
    assert farm_summary["source_file"] == "services/export/reports/core.py"
    assert any(query["line"] > farm_summary["source_line"] for query in farm_summary["queries"])
    assert any(
        helper["callable"] == "get_pest_management_report"
        and helper["location_id_name_visible_in_arguments"]
        for helper in reports["pest_management"]["helper_calls"]
    )


def test_inventory_output_and_freshness_check_are_deterministic(tmp_path):
    output = tmp_path / "query-scope-inventory.json"

    assert main(["--output", str(output)]) == 0
    first = output.read_text(encoding="utf-8")
    assert main(["--check", str(output)]) == 0
    assert json.loads(first)["summary"]["registered_report_types"] == 94
    assert "SELECT" not in first

    output.write_text(first + " ", encoding="utf-8")
    assert main(["--check", str(output)]) == 1
