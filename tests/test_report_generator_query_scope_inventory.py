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


def test_classifier_tracks_distinct_sql_branches_for_location_and_network_scope():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    if location_id:
        query = "SELECT * FROM v_location_report WHERE location_id = %s::uuid"
        params = [location_id]
    else:
        query = "SELECT * FROM v_network_report"
        params = []
    query += " ORDER BY created_at DESC"
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    query = analysis["queries"][0]
    assert analysis["classification"] == "conditional_direct_query_scope"
    assert query["relations"] == ["v_location_report", "v_network_report"]
    assert query["location_predicate_visible"] is True
    assert query["location_id_in_bound_expression"] is True
    assert query["location_scope_conditionally_added"] is True
    assert query["bound_location_scope_signal"] is True
    assert query["positional_bind_arity"]["mismatch"] is False
    assert [
        (variant["placeholder_count"], variant["supplied_count"])
        for variant in query["positional_bind_arity"]["variants"]
    ] == [(1, 1), (0, 0)]


def test_classifier_correlates_conditionally_appended_parameters_with_sql_branch():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    query = "SELECT * FROM v_report"
    params = []
    if location_id:
        query += " WHERE location_id = %s"
        params.append(location_id)
    query += " ORDER BY created_at DESC"
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    query = analysis["queries"][0]
    assert query["positional_bind_arity"] == {
        "mismatch": False,
        "variants": [
            {
                "conditional_line": 5,
                "branch": 0,
                "placeholder_count": 1,
                "supplied_count": 1,
                "mismatch": False,
            },
            {
                "conditional_line": 5,
                "branch": 1,
                "placeholder_count": 0,
                "supplied_count": 0,
                "mismatch": False,
            },
        ],
    }


def test_classifier_detects_parameters_appended_on_the_wrong_sql_branch():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    query = "SELECT * FROM v_report"
    params = []
    if location_id:
        query += " WHERE location_id = %s"
    else:
        params.append("unexpected")
    query += " ORDER BY created_at DESC"
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    arity = analysis["queries"][0]["positional_bind_arity"]
    assert arity["mismatch"] is True
    assert [(variant["placeholder_count"], variant["supplied_count"])
            for variant in arity["variants"]] == [(1, 0), (0, 1)]


def test_classifier_leaves_nested_conditional_parameter_mutations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, include_optional):
    query = "SELECT * FROM v_report"
    params = []
    if location_id:
        query += " WHERE location_id = %s"
        if include_optional:
            params.append(location_id)
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_leaves_nested_conditional_sql_mutations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, include_location_filter):
    query = "SELECT * FROM v_report"
    params = []
    if location_id:
        if include_location_filter:
            query += " WHERE location_id = %s"
            params.append(location_id)
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_resolves_literal_if_elif_sql_and_parameter_pairs_without_scope_claim():
    analysis = analyze_function_source(
        '''
def list_rows(conn, org_id=None, location_id=None):
    if location_id and not org_id:
        where, params = "location_id = %s", [location_id]
    elif org_id and not location_id:
        where, params = "organization_id = %s", [org_id]
    else:
        raise ValueError("provide exactly one scope")
    with conn.cursor() as cur:
        cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "list_rows",
    )

    query = analysis["queries"][0]
    assert query["sql_source"] == "static_or_resolved"
    assert query["relations"] == ["farm"]
    assert query["location_predicate_visible"] is True
    assert query["bound_location_scope_signal"] is False
    assert query["positional_bind_arity"] == {
        "mismatch": False,
        "variants": [
            {
                "conditional_line": 3,
                "branch": 0,
                "placeholder_count": 1,
                "supplied_count": 1,
                "mismatch": False,
            },
            {
                "conditional_line": 5,
                "branch": 1,
                "placeholder_count": 1,
                "supplied_count": 1,
                "mismatch": False,
            },
        ],
    }


def test_classifier_detects_tuple_filter_branch_bind_mismatch():
    analysis = analyze_function_source(
        '''
def list_rows(conn, org_id=None, location_id=None):
    if location_id and not org_id:
        where, params = "location_id = %s", [location_id]
    elif org_id and not location_id:
        where, params = "organization_id = %s AND active = %s", [org_id]
    else:
        raise ValueError("provide exactly one scope")
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "list_rows",
    )

    arity = analysis["queries"][0]["positional_bind_arity"]
    assert arity["mismatch"] is True
    assert [item["mismatch"] for item in arity["variants"]] == [False, True]


def test_classifier_leaves_tuple_filter_variants_unresolved_without_fail_closed_else():
    analysis = analyze_function_source(
        '''
def list_rows(conn, location_id):
    if location_id:
        where, params = "location_id = %s", [location_id]
    else:
        params = []
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "list_rows",
    )

    assert analysis["queries"][0]["sql_source"] == "dynamic_or_unresolved"
    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_resolves_literal_filter_pairs_returned_by_local_helper():
    analysis = analyze_function_source(
        '''
def build_filter(location_id=None, org_id=None):
    if location_id and not org_id:
        return "farm.location_id = %s", [location_id]
    if org_id and not location_id:
        return "farm.organization_id = %s", [org_id]
    raise ValueError("provide one scope")

def report(conn, location_id=None, org_id=None):
    where, params = build_filter(location_id, org_id)
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "report",
    )

    query = analysis["queries"][0]
    assert query["sql_source"] == "static_or_resolved"
    assert query["relations"] == ["farm"]
    assert query["bound_location_scope_signal"] is True
    assert query["location_scope_conditionally_added"] is True
    assert [item["bound_location_scope_signal"] for item in query["location_scope_variants"]] == [
        True,
        False,
    ]
    assert query["positional_bind_arity"] == {
        "mismatch": False,
        "variants": [
            {
                "helper_return_line": 4,
                "placeholder_count": 1,
                "supplied_count": 1,
                "mismatch": False,
            },
            {
                "helper_return_line": 6,
                "placeholder_count": 1,
                "supplied_count": 1,
                "mismatch": False,
            },
        ],
    }


def test_classifier_does_not_bind_location_scope_to_an_organization_argument():
    analysis = analyze_function_source(
        '''
def build_filter(location_id, org_id):
    return "farm.location_id = %s", [org_id]

def report(conn, location_id, org_id):
    where, params = build_filter(location_id, org_id)
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "report",
    )

    query = analysis["queries"][0]
    assert query["bound_location_scope_signal"] is False
    assert query["location_scope_variants"] == [
        {
            "helper_return_line": 3,
            "location_predicate_visible": True,
            "location_id_bound": False,
            "bound_location_scope_signal": False,
        }
    ]


def test_classifier_recognizes_location_alias_filter_only_when_joined_to_location():
    analysis = analyze_function_source(
        '''
def build_filter(location_id):
    return "l.id = %s", [location_id]

def report(conn, location_id):
    where, params = build_filter(location_id)
    cur = conn.cursor()
    cur.execute(
        f"SELECT t.id FROM threat t JOIN location l ON l.id = t.location_id WHERE {where}",
        params,
    )
''',
        "report",
    )

    query = analysis["queries"][0]
    assert query["bound_location_scope_signal"] is True
    assert query["location_scope_variants"][0]["location_predicate_visible"] is True

    unjoined = analyze_function_source(
        '''
def build_filter(location_id):
    return "l.id = %s", [location_id]

def report(conn, location_id):
    where, params = build_filter(location_id)
    cur = conn.cursor()
    cur.execute(f"SELECT t.id FROM threat t WHERE {where}", params)
''',
        "report",
    )["queries"][0]
    assert unjoined["bound_location_scope_signal"] is False


def test_classifier_leaves_local_helper_filter_unresolved_when_return_is_dynamic():
    analysis = analyze_function_source(
        '''
def build_filter(location_id):
    if location_id:
        return make_filter(location_id), [location_id]
    raise ValueError("location required")

def report(conn, location_id):
    where, params = build_filter(location_id)
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "report",
    )

    assert analysis["queries"][0]["sql_source"] == "dynamic_or_unresolved"
    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_leaves_local_helper_filter_unresolved_when_a_path_falls_through():
    analysis = analyze_function_source(
        '''
def build_filter(location_id):
    if location_id:
        return "location_id = %s", [location_id]

def report(conn, location_id):
    where, params = build_filter(location_id)
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM farm WHERE {where}", params)
''',
        "report",
    )

    assert analysis["queries"][0]["sql_source"] == "dynamic_or_unresolved"
    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_resolves_formatted_sql_identifiers_from_literal_local_callers():
    analysis = analyze_function_source(
        '''
def load(conn, view_name, location_id=None, order_by="id"):
    cur = conn.cursor()
    if location_id:
        cur.execute(
            f"SELECT * FROM {view_name} WHERE location_id = %s ORDER BY {order_by}",
            (location_id,),
        )
    else:
        cur.execute(f"SELECT * FROM {view_name} ORDER BY {order_by}")

def report_one(conn, location_id):
    return load(conn, "v_public_one", location_id, "created_at DESC")

def report_two(conn):
    return load(conn, "v_public_two", None, "name")
''',
        "load",
    )

    location_query, network_query = analysis["queries"]
    assert location_query["sql_source"] == "static_or_resolved"
    assert location_query["relations"] == ["v_public_one", "v_public_two"]
    assert location_query["bound_location_scope_signal"] is False
    assert location_query["positional_bind_arity"]["mismatch"] is False
    assert [
        (item["caller"], item["placeholder_count"], item["supplied_count"])
        for item in location_query["positional_bind_arity"]["variants"]
    ] == [("report_one", 1, 1), ("report_two", 1, 1)]
    assert network_query["sql_source"] == "static_or_resolved"
    assert network_query["relations"] == ["v_public_one", "v_public_two"]
    assert network_query["bound_location_scope_signal"] is False
    assert network_query["positional_bind_arity"]["mismatch"] is False
    assert [
        (item["caller"], item["placeholder_count"], item["supplied_count"])
        for item in network_query["positional_bind_arity"]["variants"]
    ] == [("report_one", 0, 0), ("report_two", 0, 0)]


def test_classifier_keeps_formatted_sql_unresolved_if_any_local_caller_is_dynamic():
    analysis = analyze_function_source(
        '''
def load(conn, view_name):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {view_name}")

def report_one(conn):
    return load(conn, "v_public_one")

def report_two(conn, view_name):
    return load(conn, view_name)
''',
        "load",
    )

    assert analysis["queries"][0]["sql_source"] == "dynamic_or_unresolved"
    assert analysis["queries"][0]["positional_bind_arity"] is None


def test_classifier_does_not_pair_location_filter_and_bind_from_different_branches():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    if location_id:
        query = "SELECT * FROM v_report WHERE display_name = %s"
        params = [location_id]
    else:
        query = "SELECT * FROM v_report WHERE location_id = %s"
        params = ["network"]
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    query = analysis["queries"][0]
    assert query["location_predicate_visible"] is True
    assert query["location_id_in_bound_expression"] is True
    assert query["bound_location_scope_signal"] is False


def test_classifier_requires_scope_filter_on_the_present_location_branch():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    if location_id:
        query = "SELECT * FROM v_report WHERE display_name = %s"
    else:
        query = "SELECT * FROM v_report WHERE location_id = %s"
    params = [location_id]
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    query = analysis["queries"][0]
    assert query["location_predicate_visible"] is True
    assert query["location_id_in_bound_expression"] is True
    assert query["bound_location_scope_signal"] is False


def test_classifier_does_not_keep_stale_scope_after_unconditional_sql_reassignment():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    if location_id:
        query = "SELECT * FROM v_location_report WHERE location_id = %s::uuid"
        params = [location_id]
    else:
        query = "SELECT * FROM v_network_report"
        params = []
    query = "SELECT * FROM v_unscoped_report"
    params = []
    cur = conn.cursor()
    cur.execute(query, params)
''',
        "generate",
    )

    query = analysis["queries"][0]
    assert analysis["classification"] == "no_bound_location_scope_visible"
    assert query["relations"] == ["v_unscoped_report"]
    assert query["location_scope_conditionally_added"] is False
    assert query["bound_location_scope_signal"] is False


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


def test_classifier_reports_extra_static_positional_parameters():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    cur = conn.cursor()
    cur.execute("SELECT id FROM location", (location_id,))
''',
        "generate",
    )

    assert analysis["static_positional_arity_site_count"] == 1
    assert analysis["positional_arity_mismatch_count"] == 1
    assert analysis["queries"][0]["positional_bind_arity"] == {
        "placeholder_count": 0,
        "supplied_count": 1,
        "mismatch": True,
    }


def test_classifier_ignores_placeholders_inside_sql_literals_and_comments():
    analysis = analyze_function_source(
        '''
def generate(conn, first_id, second_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT '%s' /* %s */ FROM sample WHERE first_id = %s -- %s\\n"
        "AND second_id = %s",
        (first_id, second_id),
    )
''',
        "generate",
    )

    assert analysis["queries"][0]["positional_bind_arity"] == {
        "placeholder_count": 2,
        "supplied_count": 2,
        "mismatch": False,
    }


def test_classifier_checks_named_mapping_and_ignores_quoted_or_commented_placeholders():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    conn.execute(
        "SELECT ':literal' FROM location WHERE id = :location_id -- :comment",
        {"location_id": location_id},
    )
''',
        "generate",
    )

    assert analysis["static_positional_arity_site_count"] == 0
    assert analysis["positional_arity_mismatch_count"] == 0
    assert analysis["static_named_bind_contract_site_count"] == 1
    assert analysis["named_bind_contract_mismatch_count"] == 0
    assert analysis["queries"][0]["positional_bind_arity"] is None
    assert analysis["queries"][0]["named_bind_contract"] == {
        "required_names": ["location_id"],
        "supplied_names": ["location_id"],
        "base_required_names": ["location_id"],
        "base_supplied_names": ["location_id"],
        "variants": [],
        "mismatch": False,
    }


def test_classifier_checks_psycopg_named_placeholder_mapping():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id):
    conn.execute("SELECT id FROM location WHERE id = %(location_id)s", {"location_id": location_id})
''',
        "generate",
    )

    assert analysis["static_named_bind_contract_site_count"] == 1
    assert analysis["named_bind_contract_mismatch_count"] == 0
    assert analysis["queries"][0]["named_bind_contract"]["required_names"] == ["location_id"]


def test_classifier_resolves_literal_module_sql_constants_without_overriding_locals():
    resolved = analyze_function_source(
        '''
ACTIVE_FILTER = "status = 'published' AND sold_at IS NULL"

def generate(conn, location_id):
    conn.execute(
        f"SELECT id FROM market_listing WHERE location_id = %s AND {ACTIVE_FILTER}",
        (location_id,),
    )
''',
        "generate",
    )
    shadowed = analyze_function_source(
        '''
ACTIVE_FILTER = "status = 'published'"

def generate(conn, ACTIVE_FILTER):
    conn.execute(f"SELECT id FROM market_listing WHERE {ACTIVE_FILTER}", ())
''',
        "generate",
    )
    dynamic = analyze_function_source(
        '''
ACTIVE_FILTER = load_filter()

def generate(conn):
    conn.execute(f"SELECT id FROM market_listing WHERE {ACTIVE_FILTER}", ())
''',
        "generate",
    )

    assert resolved["queries"][0]["sql_source"] == "static_or_resolved"
    assert resolved["queries"][0]["positional_bind_arity"]["mismatch"] is False
    assert resolved["queries"][0]["bound_location_scope_signal"] is True
    assert shadowed["queries"][0]["sql_source"] == "dynamic_or_unresolved"
    assert dynamic["queries"][0]["sql_source"] == "dynamic_or_unresolved"


def test_classifier_correlates_optional_sql_fragment_and_parameter_appends():
    analysis = analyze_function_source(
        '''
def generate(conn, first_id=None, second_id=None):
    clauses = []
    params = []
    if first_id:
        clauses.append("first_id = %s")
        params.append(first_id)
    if second_id:
        clauses.append("second_id = %s")
        params.append(second_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM sample{where}", params)
''',
        "generate",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "static_or_resolved"
    assert query["positional_bind_arity"]["mismatch"] is False
    assert len(query["positional_bind_arity"]["variants"]) == 4
    assert {
        (variant["placeholder_count"], variant["supplied_count"])
        for variant in query["positional_bind_arity"]["variants"]
    } == {(0, 0), (1, 1), (2, 2)}


def test_classifier_detects_optional_sql_and_parameter_guard_mismatch():
    analysis = analyze_function_source(
        '''
def generate(conn, first_id=None, second_id=None):
    clauses = []
    params = []
    if first_id:
        clauses.append("first_id = %s")
    if second_id:
        params.append(second_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM sample{where}", params)
''',
        "generate",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "static_or_resolved"
    assert query["positional_bind_arity"]["mismatch"] is True
    assert any(variant["mismatch"] for variant in query["positional_bind_arity"]["variants"])


def test_classifier_leaves_nested_optional_list_mutations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, first_id=None, include_filter=False):
    clauses = []
    params = []
    if first_id:
        if include_filter:
            clauses.append("first_id = %s")
            params.append(first_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM sample{where}", params)
''',
        "generate",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "dynamic_or_unresolved"
    assert query["positional_bind_arity"] is None


def test_classifier_leaves_aliased_parameter_list_mutations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, first_id=None):
    clauses = []
    params = []
    aliases = list(params)
    if first_id:
        clauses.append("first_id = %s")
        params.append(first_id)
        aliases.append(first_id)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM sample{where}", params)
''',
        "generate",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "dynamic_or_unresolved"
    assert query["positional_bind_arity"] is None


def test_classifier_resolves_local_query_wrapper_literal_callsites():
    analysis = analyze_function_source(
        '''
def rows(cur, sql, params):
    cur.execute(sql, params)

def cockpit(cur, organization_id):
    demand = rows(
        cur,
        "SELECT location_id FROM production_market_match WHERE organization_id = %s",
        (organization_id,),
    )
    plans = rows(cur, "SELECT id FROM financial_plan", ())
''',
        "rows",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "static_or_resolved"
    assert query["positional_bind_arity"]["mismatch"] is False
    assert [
        (variant["caller"], variant["placeholder_count"], variant["supplied_count"])
        for variant in query["positional_bind_arity"]["variants"]
    ] == [("cockpit", 1, 1), ("cockpit", 0, 0)]


def test_classifier_does_not_resolve_wrapper_with_dynamic_callsite():
    analysis = analyze_function_source(
        '''
def rows(cur, sql, params):
    cur.execute(sql, params)

def cockpit(cur, sql, params):
    return rows(cur, sql, params)

def another_caller(cur):
    sql = "SELECT id FROM sample"
    return rows(cur, sql, ())
''',
        "rows",
    )
    query = analysis["queries"][0]

    assert query["sql_source"] == "dynamic_or_unresolved"
    assert query["positional_bind_arity"] is None


def test_classifier_correlates_named_binds_with_condition_list_and_mapping_branches():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, period_start, period_end):
    conditions = ["dsp.location_id = :location_id"]
    params = {"location_id": location_id}
    if period_start:
        conditions.append("dsp.created_at >= :period_start")
        params["period_start"] = period_start
    if period_end:
        conditions.append("dsp.created_at <= :period_end")
        params["period_end"] = period_end
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM data_stream_post dsp WHERE {where}"
    conn.execute(sql, params)
''',
        "generate",
    )

    contract = analysis["queries"][0]["named_bind_contract"]
    assert contract["mismatch"] is False
    assert contract["base_required_names"] == ["location_id"]
    assert contract["base_supplied_names"] == ["location_id"]
    assert [
        (variant["required_names"], variant["supplied_names"], variant["mismatch"])
        for variant in contract["variants"]
    ] == [
        (["location_id", "period_start"], ["location_id", "period_start"], False),
        (["location_id", "period_end"], ["location_id", "period_end"], False),
    ]


def test_classifier_detects_named_mapping_keys_added_on_the_wrong_branch():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, period_start, period_end):
    conditions = ["dsp.location_id = :location_id"]
    params = {"location_id": location_id}
    if period_start:
        conditions.append("dsp.created_at >= :period_start")
        params["period_end"] = period_end
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM data_stream_post dsp WHERE {where}"
    conn.execute(sql, params)
''',
        "generate",
    )

    contract = analysis["queries"][0]["named_bind_contract"]
    assert contract["mismatch"] is True
    assert any(variant["mismatch"] for variant in contract["variants"])


def test_classifier_leaves_nested_named_bind_mutations_unresolved():
    analysis = analyze_function_source(
        '''
def generate(conn, location_id, period_start, include_period):
    conditions = ["dsp.location_id = :location_id"]
    params = {"location_id": location_id}
    if period_start:
        if include_period:
            conditions.append("dsp.created_at >= :period_start")
            params["period_start"] = period_start
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM data_stream_post dsp WHERE {where}"
    conn.execute(sql, params)
''',
        "generate",
    )

    assert analysis["queries"][0]["named_bind_contract"] is None


def test_classifier_leaves_unrecognized_list_and_mapping_mutations_unresolved():
    list_mutation = analyze_function_source(
        '''
def generate(conn, location_id, period_start):
    conditions = ["dsp.location_id = :location_id"]
    params = {"location_id": location_id}
    if period_start:
        conditions += ["dsp.created_at >= :period_start"]
        params["period_start"] = period_start
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM data_stream_post dsp WHERE {where}"
    conn.execute(sql, params)
''',
        "generate",
    )
    mapping_mutation = analyze_function_source(
        '''
def generate(conn, location_id, period_start):
    conditions = ["dsp.location_id = :location_id"]
    params = {"location_id": location_id}
    if period_start:
        conditions.append("dsp.created_at >= :period_start")
        params.update({"period_start": period_start})
    where = " AND ".join(conditions)
    sql = f"SELECT * FROM data_stream_post dsp WHERE {where}"
    conn.execute(sql, params)
''',
        "generate",
    )

    assert list_mutation["queries"][0]["named_bind_contract"] is None
    assert mapping_mutation["queries"][0]["named_bind_contract"] is None


def test_registry_wide_inventory_links_direct_queries_to_actual_source_lines():
    inventory = build_inventory()

    assert inventory["summary"]["registered_report_types"] == 94
    assert inventory["summary"]["direct_query_sites"] == 176
    assert inventory["summary"]["static_positional_arity_sites"] == 175
    assert inventory["summary"]["positional_arity_mismatch_sites"] == 0
    assert inventory["summary"]["static_named_bind_contract_sites"] == 1
    assert inventory["summary"]["named_bind_contract_mismatch_sites"] == 0
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
    branch_built_reports = {
        "stakeholder_engagement",
        "stakeholder_grievance",
        "stakeholder_decision_lineage",
        "stakeholder_outcomes",
        "stakeholder_landscape",
    }
    for report_type in branch_built_reports:
        assert all(
            query["positional_bind_arity"] is not None
            for query in reports[report_type]["queries"]
        )
    unresolved_arity = [
        (report["report_type"], query["line"])
        for report in reports.values()
        for query in report["queries"]
        if query["positional_bind_arity"] is None
    ]
    assert unresolved_arity == [("data_stream_summary", 29)]
    assert reports["data_stream_summary"]["queries"][0]["named_bind_contract"]["mismatch"] is False


def test_inventory_output_and_freshness_check_are_deterministic(tmp_path):
    output = tmp_path / "query-scope-inventory.json"

    assert main(["--output", str(output)]) == 0
    first = output.read_text(encoding="utf-8")
    assert main(["--check", str(output)]) == 0
    assert json.loads(first)["summary"]["registered_report_types"] == 94
    assert "SELECT" not in first

    output.write_text(first + " ", encoding="utf-8")
    assert main(["--check", str(output)]) == 1
