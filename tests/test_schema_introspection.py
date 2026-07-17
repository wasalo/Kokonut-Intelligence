"""Tests for the read-only ER schema inventory."""

from services.schema_introspection.inventory import build_inventory, inventory_as_markdown


def _inventory():
    return build_inventory(
        tables=[{"table_name": "farmer"}, {"table_name": "plot"}],
        columns=[
            {"table_name": "farmer", "column_name": "id", "udt_name": "uuid", "is_nullable": "NO", "ordinal_position": 1},
            {"table_name": "farmer", "column_name": "primary_crop_ids", "udt_name": "_uuid", "is_nullable": "YES", "ordinal_position": 2},
            {"table_name": "plot", "column_name": "owner_type", "udt_name": "varchar", "is_nullable": "NO", "ordinal_position": 1},
            {"table_name": "plot", "column_name": "owner_id", "udt_name": "uuid", "is_nullable": "NO", "ordinal_position": 2},
        ],
        primary_keys=[{"table_name": "farmer", "constraint_name": "farmer_pkey", "column_name": "id", "ordinal_position": 1}],
        foreign_keys=[{"table_name": "plot", "column_name": "farmer_id", "referenced_table": "farmer", "referenced_column": "id", "delete_rule": "CASCADE", "constraint_name": "plot_farmer_fkey"}],
        unique_constraints=[],
        indexes=[],
        views=[],
        exclusion_constraints=[],
    )


def test_inventory_detects_polymorphic_and_relationship_shaped_columns():
    report = _inventory()
    assert report["tables"] == ["farmer", "plot"]
    assert report["polymorphic_references"] == [{"table_name": "plot", "type_column": "owner_type", "id_column": "owner_id"}]
    assert report["relationship_shaped_columns"][0]["column_name"] == "primary_crop_ids"
    assert report["tables_without_primary_keys"] == ["plot"]


def test_markdown_inventory_is_deterministic_and_reviewable():
    markdown = inventory_as_markdown(_inventory())
    assert markdown.startswith("# PostgreSQL ER Inventory")
    assert "`plot`: `owner_type` + `owner_id`" in markdown
    assert "`plot.farmer_id` -> `farmer.id` (CASCADE)" in markdown
