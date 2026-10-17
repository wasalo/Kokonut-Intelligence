import json
from pathlib import Path

from scripts.runtime_sql_inventory import _scan_source, _serialize, build_inventory


def test_runtime_sql_inventory_scans_api_worker_and_cli_sources():
    inventory = build_inventory()
    sources = {site["source"] for site in inventory["execution_sites"]}

    assert inventory["summary"]["source_files"] > 0
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
    assert sites[0]["expression_kind"] == "literal"
    assert sites[0]["operation_refs"] == ["scheduled_module:services.example"]
    assert "sql" not in sites[0]
    assert "static_sql_sha256" in sites[0]
    assert sites[1]["candidate_relations"] == []
    assert sites[1]["static_sql_sha256"] is None


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
    assert packages["credit_class"]["candidate_relation_names"] == 29
    assert packages["credit_class"]["non_literal_sites"] == 10
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
