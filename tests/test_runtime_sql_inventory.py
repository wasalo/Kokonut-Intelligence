import json
from pathlib import Path

from scripts.runtime_sql_inventory import _scan_source, _serialize, build_inventory


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
