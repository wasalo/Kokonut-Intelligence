import ast
import json
from pathlib import Path

import pytest

from scripts.runtime_sql_inventory import (
    _fingerprint_digest,
    _scan_source,
    _serialize,
    _stable_ast_dump,
    _validate_write_review_ledger,
    _write_review_fingerprint,
    build_inventory,
)


def test_runtime_sql_inventory_scans_api_worker_and_cli_sources():
    inventory = build_inventory()
    sources = {site["source"] for site in inventory["execution_sites"]}

    assert inventory["summary"]["source_files"] > 0
    assert inventory["version"] == 2
    assert inventory["summary"]["execution_sites"] == len(inventory["execution_sites"])
    assert any(source.startswith("services/gateway/") for source in sources)
    assert any(source.startswith("services/events/") for source in sources)
    assert any(source.startswith("services/") and source.endswith("cli.py") for source in sources)
    assert inventory["service_packages"]["gateway"]["execution_sites"] > 0


def test_runtime_sql_inventory_records_metadata_without_sql_text(tmp_path: Path):
    source = "services/example.py"
    path = tmp_path / "example.py"
    path.write_text(
        """
def write(conn, dynamic):
    conn.execute(conn.text(\"INSERT INTO public.example_record (name) VALUES (%s)\"), (dynamic,))
    conn.execute(dynamic)
""",
        encoding="utf-8",
    )

    sites = _scan_source(source, path, ["scheduled_module:services.example"])

    assert [site["statement_group"] for site in sites] == [
        "write_candidate",
        "unknown_requires_manual_review",
    ]
    assert sites[0]["candidate_relations"] == ["public.example_record"]
    assert sites[0]["write_target_relations"] == ["public.example_record"]
    assert sites[0]["expression_kind"] == "literal"
    assert sites[0]["operation_refs"] == ["scheduled_module:services.example"]
    assert "sql" not in sites[0]
    assert "static_sql_sha256" in sites[0]
    assert sites[1]["candidate_relations"] == []
    assert sites[1]["write_target_relations"] == []
    assert sites[1]["static_sql_sha256"] is None


def test_runtime_sql_inventory_resolves_static_targets_from_single_local_assignments(tmp_path: Path):
    source = "services/example.py"
    path = tmp_path / "example.py"
    path.write_text(
        '''
def register(conn):
    sql = """INSERT INTO service_registry (name) VALUES (%s)"""
    conn.execute(sql)

def update(conn, fields):
    sql = f"UPDATE service_registry SET {', '.join(fields)} WHERE name = %s"
    conn.execute(sql)
''',
        encoding="utf-8",
    )

    sites = _scan_source(source, path, [])

    assert [site["statement_kind"] for site in sites] == ["INSERT", "UPDATE"]
    assert all(site["candidate_relations"] == ["service_registry"] for site in sites)
    assert all(site["write_target_relations"] == ["service_registry"] for site in sites)
    assert all(
        site["local_query_resolution"] == "single_local_assignment_template"
        for site in sites
    )
    assert all(site["expression_kind"] == "composed_or_variable" for site in sites)
    assert all(site["static_sql_sha256"] is None for site in sites)
    assert all("sql" not in site for site in sites)


def test_runtime_sql_inventory_does_not_guess_dynamic_or_reassigned_identifiers(tmp_path: Path):
    source = "services/example.py"
    path = tmp_path / "example.py"
    path.write_text(
        '''
def dynamic_target(conn, table):
    sql = f"INSERT INTO public.{table} (name) VALUES (%s)"
    conn.execute(sql)

def concatenated_target(conn, table):
    sql = "INSERT INTO public." + table + " (name) VALUES (%s)"
    conn.execute(sql)

def reassigned(conn, enabled):
    if enabled:
        sql = "INSERT INTO service_registry (name) VALUES (%s)"
    else:
        sql = "UPDATE service_registry SET name = %s"
    conn.execute(sql)
''',
        encoding="utf-8",
    )

    sites = _scan_source(source, path, [])
    dynamic_target, concatenated_target, reassigned = sites

    assert dynamic_target["statement_kind"] == "INSERT"
    assert dynamic_target["candidate_relations"] == []
    assert dynamic_target["write_target_relations"] == []
    assert dynamic_target["local_query_resolution"] == "single_local_assignment_template"
    assert concatenated_target["statement_kind"] == "INSERT"
    assert concatenated_target["candidate_relations"] == []
    assert concatenated_target["write_target_relations"] == []
    assert "local_query_resolution" not in concatenated_target
    assert reassigned["statement_kind"] == "UNKNOWN"
    assert reassigned["candidate_relations"] == []
    assert reassigned["write_target_relations"] == []
    assert "local_query_resolution" not in reassigned


def test_unresolved_write_fingerprint_is_stable_across_line_moves_and_contains_no_sql(tmp_path: Path):
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text(
        'def persist(conn, table):\n    conn.execute(f"UPDATE {table} SET value = %s", (1,))\n',
        encoding="utf-8",
    )
    second.write_text(
        '\n\n\ndef persist(conn, table):\n    conn.execute(f"UPDATE {table} SET value = %s", (1,))\n',
        encoding="utf-8",
    )

    first_site = _scan_source(
        "services/example.py", first, [], include_review_fingerprints=True
    )[0]
    second_site = _scan_source(
        "services/example.py", second, [], include_review_fingerprints=True
    )[0]

    assert first_site["write_review_fingerprint"] == second_site["write_review_fingerprint"]
    assert first_site["write_target_relations"] == []
    assert "sql" not in first_site
    assert "query" not in first_site


def test_stable_ast_dump_matches_python_311_ast_dump_without_location_attributes():
    tree = ast.parse(
        'def persist(conn, target):\n'
        '    sql = f"UPDATE {target} SET value = %s"\n'
        '    conn.execute(sql, (1,))\n'
    )

    assert _stable_ast_dump(tree) == (
        "Module(body=[FunctionDef(name='persist', "
        "args=arguments(posonlyargs=[], args=[arg(arg='conn'), arg(arg='target')], "
        "kwonlyargs=[], kw_defaults=[], defaults=[]), "
        "body=[Assign(targets=[Name(id='sql', ctx=Store())], "
        "value=JoinedStr(values=[Constant(value='UPDATE '), "
        "FormattedValue(value=Name(id='target', ctx=Load()), conversion=-1), "
        "Constant(value=' SET value = %s')])), "
        "Expr(value=Call(func=Attribute(value=Name(id='conn', ctx=Load()), "
        "attr='execute', ctx=Load()), args=[Name(id='sql', ctx=Load()), "
        "Tuple(elts=[Constant(value=1)], ctx=Load())], keywords=[]))], "
        "decorator_list=[])], type_ignores=[])"
    )


def test_unresolved_write_fingerprint_ignores_python_312_type_params_field():
    tree = ast.parse(
        'def persist(conn, target):\n'
        '    conn.execute(f"UPDATE {target} SET value = %s", (1,))\n'
    )
    function = tree.body[0]
    query_expression = function.body[0].value.args[0]
    site = {
        "scope": "persist",
        "method": "execute",
        "statement_kind": "UPDATE",
    }

    # Python 3.12 adds an empty type_params field to function nodes. Simulate
    # that AST shape on the test interpreter and prove the fingerprint remains
    # identical to the Python 3.11 representation used by the pinned ledger.
    FunctionDef312 = type(
        "FunctionDef",
        (ast.FunctionDef,),
        {
            "_fields": (
                *[field for field in ast.FunctionDef._fields if field != "type_params"],
                "type_params",
            )
        },
    )
    function_312 = FunctionDef312()
    for field in ast.FunctionDef._fields:
        setattr(function_312, field, getattr(function, field))
    function_312.type_params = []

    assert _stable_ast_dump(function_312) == _stable_ast_dump(function)
    assert _write_review_fingerprint(
        "services/example.py", site, query_expression, function, 1
    ) == _write_review_fingerprint(
        "services/example.py", site, query_expression, function_312, 1
    )

    function_312.type_params = [ast.Name(id="T", ctx=ast.Load())]
    assert "type_params=[Name(id='T', ctx=Load())]" in _stable_ast_dump(
        function_312
    )


def test_unresolved_write_fingerprint_changes_when_same_scope_binding_changes(tmp_path: Path):
    first = tmp_path / "first_binding.py"
    second = tmp_path / "second_binding.py"
    first.write_text(
        'def persist(conn):\n'
        '    table = "first_target"\n'
        '    sql = f"UPDATE {table} SET value = %s"\n'
        '    conn.execute(sql)\n',
        encoding="utf-8",
    )
    second.write_text(
        'def persist(conn):\n'
        '    table = "second_target"\n'
        '    sql = f"UPDATE {table} SET value = %s"\n'
        '    conn.execute(sql)\n',
        encoding="utf-8",
    )

    first_site = _scan_source(
        "services/example.py", first, [], include_review_fingerprints=True
    )[0]
    second_site = _scan_source(
        "services/example.py", second, [], include_review_fingerprints=True
    )[0]

    assert first_site["write_review_fingerprint"] != second_site["write_review_fingerprint"]


def test_duplicate_unresolved_calls_have_distinct_fingerprints_and_new_duplicate_is_flagged(
    tmp_path: Path,
):
    path = tmp_path / "duplicates.py"
    source = "services/example.py"
    one_call = (
        'def persist(conn, table):\n'
        '    conn.execute(f"UPDATE {table} SET value = %s")\n'
    )
    two_calls = one_call + '    conn.execute(f"UPDATE {table} SET value = %s")\n'
    path.write_text(one_call, encoding="utf-8")
    first = _scan_source(source, path, [], include_review_fingerprints=True)[0]
    first_fingerprint = first["write_review_fingerprint"]

    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    baseline_candidates = [
        dict(item)
        for item in ledger["legacy_unreviewed"]
    ]
    ledger["reviewed_sites"].append({
        "fingerprint": first_fingerprint,
        "review_status": "reviewed_unresolved",
        "reviewed_by": "test@example.invalid",
        "reviewed_on": "2026-10-28",
        "reason": "Synthetic gate test; this is not an ACL approval.",
    })

    path.write_text(two_calls, encoding="utf-8")
    duplicate_sites = _scan_source(source, path, [], include_review_fingerprints=True)
    duplicate_fingerprints = [site["write_review_fingerprint"] for site in duplicate_sites]
    assert len(set(duplicate_fingerprints)) == 2

    candidates = [
        *baseline_candidates,
        *(
            {
                "fingerprint": site["write_review_fingerprint"],
                "source": site["source"],
                "line": site["line"],
                "scope": site["scope"],
                "statement_kind": site["statement_kind"],
            }
            for site in duplicate_sites
        ),
    ]
    errors = _validate_write_review_ledger(candidates, ledger)
    assert sum("new unresolved SQL write candidate requires explicit review" in error for error in errors) == 2


def test_unresolved_module_level_execute_resolves_assignment_and_is_reviewed(tmp_path: Path):
    path = tmp_path / "module_sql.py"
    path.write_text(
        'sql = f"UPDATE <dynamic_table> SET value = %s"\nconn.execute(sql)\n',
        encoding="utf-8",
    )

    site = _scan_source(
        "services/example.py", path, [], include_review_fingerprints=True
    )[0]

    assert site["statement_kind"] == "UPDATE"
    assert site["scope"] == "module"
    assert site["write_target_relations"] == []
    assert site["module_query_resolution"] == "single_module_constant_template"
    assert site["write_review_fingerprint"]


def test_module_constant_query_resolves_inside_function_and_is_fingerprinted(tmp_path: Path):
    sources = [
        'query = "UPDATE <dynamic_table> SET value = %s"\n'
        'def persist(conn):\n    conn.execute(query, (1,))\n',
        'query = "UPDATE <other_dynamic_table> SET value = %s"\n'
        'def persist(conn):\n    conn.execute(query, (1,))\n',
    ]
    sites = []
    for index, source_text in enumerate(sources):
        path = tmp_path / f"module_constant_{index}.py"
        path.write_text(source_text, encoding="utf-8")
        sites.append(
            _scan_source(
                "services/example.py", path, [], include_review_fingerprints=True
            )[0]
        )

    assert all(site["statement_kind"] == "UPDATE" for site in sites)
    assert all(site["write_target_relations"] == [] for site in sites)
    assert all(
        site["module_query_resolution"] == "single_module_constant_template"
        for site in sites
    )
    assert all(site["write_review_fingerprint"] for site in sites)
    assert sites[0]["write_review_fingerprint"] != sites[1]["write_review_fingerprint"]
    assert all("query" not in site and "sql" not in site for site in sites)


@pytest.mark.parametrize(
    "source_text",
    [
        'if enabled:\n    query = "INSERT INTO example_record VALUES (%s)"\n'
        'def persist(conn):\n    conn.execute(query, (1,))\n',
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'if enabled:\n    query = "DELETE FROM example_record"\n'
        'def persist(conn):\n    conn.execute(query)\n',
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'query = "DELETE FROM example_record"\n'
        'def persist(conn):\n    conn.execute(query)\n',
        'from query_source import query\n'
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'def persist(conn):\n    conn.execute(query)\n',
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'def change():\n    global query\n    query = "DELETE FROM example_record"\n'
        'def persist(conn):\n    conn.execute(query)\n',
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'def persist(conn, query):\n    conn.execute(query)\n',
        'query = "INSERT INTO example_record VALUES (%s)"\n'
        'def persist(conn):\n    from query_source import query\n    conn.execute(query)\n',
        'query = build_query()\n'
        'def persist(conn):\n    conn.execute(query)\n',
        'query = f"UPDATE {table} SET value = %s"\n'
        'def persist(conn):\n    conn.execute(query, (1,))\n',
    ],
)
def test_module_constant_resolution_fails_closed_for_ambiguous_bindings(
    tmp_path: Path, source_text: str
):
    path = tmp_path / "ambiguous_module_sql.py"
    path.write_text(source_text, encoding="utf-8")

    site = _scan_source("services/example.py", path, [])[0]

    assert site["statement_kind"] == "UNKNOWN"
    assert site["candidate_relations"] == []
    assert site["write_target_relations"] == []
    assert "module_query_resolution" not in site


def test_unresolved_write_ledger_requires_explicit_review_for_new_sites():
    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    current = [
        {"fingerprint": item["fingerprint"]}
        for item in [*ledger["legacy_unreviewed"], *ledger["reviewed_sites"]]
    ]
    new_site = {
        "fingerprint": "f" * 64,
        "source": "services/example.py",
        "line": 10,
        "scope": "persist",
        "method": "execute",
        "statement_kind": "UPDATE",
        "expression_kind": "fstring",
    }
    errors = _validate_write_review_ledger([*current, new_site], ledger)
    assert any("new unresolved SQL write candidate requires explicit review" in error for error in errors)

    ledger["reviewed_sites"].append({
        "fingerprint": new_site["fingerprint"],
        "review_status": "reviewed_unresolved",
        "reviewed_by": "reviewer@example.test",
        "reviewed_on": "2026-10-28",
        "reason": "Keep tracked for a later source fix; this is not an ACL approval.",
    })
    assert _validate_write_review_ledger([*current, new_site], ledger) == []


def test_unresolved_write_ledger_rejects_silent_legacy_baseline_growth():
    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    current = [
        {"fingerprint": item["fingerprint"]}
        for item in ledger["legacy_unreviewed"]
    ]
    new_fingerprint = "e" * 64
    ledger["legacy_unreviewed"].append({
        "fingerprint": new_fingerprint,
        "review_status": "preexisting_unreviewed",
        "reason": "Injected baseline entry; this is not an ACL approval.",
    })
    ledger["legacy_fingerprint_sha256"] = _fingerprint_digest(
        [item["fingerprint"] for item in ledger["legacy_unreviewed"]]
    )

    errors = _validate_write_review_ledger(
        [*current, {"fingerprint": new_fingerprint}],
        ledger,
    )
    assert any("legacy unresolved-write baseline changed" in error for error in errors)


def test_unresolved_write_ledger_rejects_unhashable_fingerprints_cleanly():
    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    original = json.loads(ledger_path.read_text(encoding="utf-8"))
    current = [
        {"fingerprint": item["fingerprint"]}
        for item in original["legacy_unreviewed"]
    ]

    for malformed_fingerprint in ([], {"unexpected": "object"}):
        ledger = json.loads(json.dumps(original))
        ledger["legacy_unreviewed"].append({
            "fingerprint": malformed_fingerprint,
            "review_status": "preexisting_unreviewed",
            "reason": "Malformed test entry; this is not an ACL approval.",
        })

        errors = _validate_write_review_ledger(current, ledger)

        assert any(
            "legacy unresolved-write entries require SHA-256 fingerprints" in error
            for error in errors
        )


def test_unresolved_write_ledger_rejects_duplicate_current_fingerprints():
    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    current = [
        {"fingerprint": item["fingerprint"]}
        for item in ledger["legacy_unreviewed"]
    ]
    duplicate = {
        "fingerprint": "c" * 64,
        "source": "services/example.py",
        "line": 12,
        "scope": "persist",
        "statement_kind": "UPDATE",
    }

    errors = _validate_write_review_ledger([*current, duplicate, duplicate.copy()], ledger)

    assert "current unresolved-write fingerprints must be unique" in errors


def test_ci_check_script_wires_runtime_sql_inventory_gate():
    script = Path("scripts/ci-check.sh").read_text(encoding="utf-8")

    assert (
        'check "Runtime SQL inventory and unresolved-write review ledger" '
        '"python3 $SCRIPT_DIR/runtime_sql_inventory.py --check '
        '$PROJECT_DIR/docs/refactor/runtime-sql-inventory.json"'
    ) in script


def test_reviewed_unresolved_site_requires_all_review_metadata():
    ledger_path = Path("docs/refactor/runtime-sql-unresolved-write-review.json")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    current = [
        {"fingerprint": item["fingerprint"]}
        for item in ledger["legacy_unreviewed"]
    ]
    fingerprint = "d" * 64
    ledger["reviewed_sites"].append({
        "fingerprint": fingerprint,
        "review_status": "reviewed_unresolved",
        "reason": "This is not an ACL approval.",
    })

    errors = _validate_write_review_ledger(
        [*current, {"fingerprint": fingerprint}],
        ledger,
    )
    assert any("requires reviewed_by" in error for error in errors)
    assert any("requires reviewed_on" in error for error in errors)


def test_runtime_sql_inventory_contains_no_service_catalog_writer():
    sites = [
        site for site in build_inventory()["execution_sites"]
        if site["source"] == "services/analytics/service_catalog.py"
    ]

    assert not any(
        "service_registry" in site.get("write_target_relations", [])
        for site in sites
    )
    assert all(site["statement_kind"] == "SELECT" for site in sites)


def test_runtime_sql_inventory_separates_dml_targets_from_referenced_tables(tmp_path: Path):
    source = "services/example.py"
    path = tmp_path / "example.py"
    path.write_text(
        '''
def write(conn):
    conn.execute("INSERT INTO public.advisory_recommendation (rule_id) "
                 "SELECT id FROM public.advisory_rule")
    conn.execute("UPDATE public.advisory_recommendation SET status = %s "
                 "FROM public.location WHERE location.id = advisory_recommendation.location_id")
    conn.execute("DELETE FROM public.advisory_recommendation "
                 "USING public.location WHERE location.id = advisory_recommendation.location_id")
    conn.execute("MERGE INTO public.advisory_recommendation AS target "
                 "USING public.location AS source ON target.location_id = source.id "
                 "WHEN MATCHED THEN UPDATE SET status = 'expired'")
''',
        encoding="utf-8",
    )

    sites = _scan_source(source, path, [])

    assert [site["statement_kind"] for site in sites] == [
        "INSERT", "UPDATE", "DELETE", "MERGE"
    ]
    assert sites[0]["candidate_relations"] == [
        "public.advisory_recommendation", "public.advisory_rule"
    ]
    assert sites[0]["write_target_relations"] == ["public.advisory_recommendation"]
    assert sites[1]["write_target_relations"] == ["public.advisory_recommendation"]
    assert sites[2]["write_target_relations"] == ["public.advisory_recommendation"]
    assert sites[3]["write_target_relations"] == ["public.advisory_recommendation"]


def test_runtime_sql_inventory_tracks_truncate_targets_separately(tmp_path: Path):
    source = "services/example.py"
    path = tmp_path / "example.py"
    path.write_text(
        '''
def clear(conn):
    conn.execute("TRUNCATE TABLE public.first_table, public.second_table RESTART IDENTITY CASCADE")
''',
        encoding="utf-8",
    )

    site = _scan_source(source, path, [])[0]

    assert site["statement_kind"] == "TRUNCATE"
    assert site["statement_group"] == "write_candidate"
    assert site["write_target_relations"] == [
        "public.first_table",
        "public.second_table",
    ]


def test_inventory_does_not_classify_real_insert_select_sources_as_write_targets():
    sites = {
        site["id"]: site for site in build_inventory()["execution_sites"]
    }
    advisory_insert = sites["services/analytics/advisor.py:371:4"]
    farm_template_insert = sites["services/analytics/multi_farm.py:39:4"]

    assert "advisory_rule" in advisory_insert["candidate_relations"]
    assert advisory_insert["write_target_relations"] == [
        "advisory_recommendation"
    ]
    assert "farm" in farm_template_insert["candidate_relations"]
    assert farm_template_insert["write_target_relations"] == [
        "farm_template_instance"
    ]


def test_crop_family_runtime_queries_are_reads_only():
    sites = [
        site for site in build_inventory()["execution_sites"]
        if "crop_family" in site["candidate_relations"]
    ]

    assert len(sites) == 8
    assert {site["statement_kind"] for site in sites} == {"SELECT"}
    assert all("crop_family" not in site["write_target_relations"] for site in sites)


def test_runtime_sql_inventory_groups_relation_candidates_without_query_values():
    inventory = build_inventory()

    for site in inventory["execution_sites"]:
        assert "sql" not in site
        assert "query" not in site
        assert "parameters" not in site
    for relation, summary in inventory["relation_candidates"].items():
        assert relation
        assert summary["execution_site_count"] > 0
        assert summary["statement_groups"]


def test_runtime_sql_inventory_surfaces_remaining_dynamic_queries():
    packages = build_inventory()["service_packages"]

    assert packages["analytics"]["execution_sites"] > packages["gateway"]["execution_sites"]
    assert packages["credit_class"]["candidate_relation_names"] == 30
    assert packages["credit_class"]["non_literal_sites"] == 12
    assert packages["data_stream"]["candidate_relation_names"] == 9
    assert packages["data_stream"]["non_literal_sites"] == 6


def test_runtime_sql_inventory_serializes_compact_json_lines():
    inventory = {
        "version": 1,
        "relation_candidates": {"public.example": {"execution_site_count": 1}},
        "execution_sites": [{"id": "services/example.py:1:0", "statement_kind": "SELECT"}],
    }

    serialized = _serialize(inventory)

    assert json.loads(serialized) == inventory
    assert len(serialized.splitlines()) < 12
    assert len([line for line in serialized.splitlines() if "services/example.py" in line]) == 1
