"""Statement of Work tests: schema, seeds, report generator."""

from pathlib import Path

SCHEMA = Path("schemas/postgres/063_statement_of_work.sql")
SEED = Path("schemas/seeds/063_statement_of_work.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in ["statement_of_work", "sow_deliverable", "sow_payment_schedule", "sow_change_request"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in ["v_public_statement_of_work", "v_public_sow_deliverables", "v_public_sow_payment_schedule"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (status IN ('draft', 'submitted', 'active'" in text
    assert "CHECK (status IN ('pending', 'delivered', 'accepted', 'rejected'))" in text
    assert "CHECK (payment_status IN ('pending', 'paid', 'overdue', 'cancelled'))" in text
    assert "CHECK (status IN ('proposed', 'approved', 'rejected', 'implemented'))" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


def test_schema_has_cascade_deletes() -> None:
    text = SCHEMA.read_text()
    assert "REFERENCES statement_of_work(id) ON DELETE CASCADE" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_sow() -> None:
    text = SEED.read_text()
    assert "Adelphi Syntropic Farm Establishment SOW" in text
    assert "Kokonut DAO" in text
    assert "Adelphi Farm Operations Team" in text
    assert "45000.00" in text


def test_seed_has_deliverables() -> None:
    text = SEED.read_text()
    assert "Soil Assessment" in text
    assert "Syntropic Planting Plan" in text
    assert "Quarterly Impact Report" in text
    assert "acceptance_criteria" in text


def test_seed_has_payment_schedule() -> None:
    text = SEED.read_text()
    assert "30% Upon Signing" in text
    assert "40% Midpoint Review" in text
    assert "30% Upon Completion" in text
    assert "13500.00" in text
    assert "18000.00" in text


def test_seed_has_change_request() -> None:
    text = SEED.read_text()
    assert "Scope Extension: Add Biofactory Zone" in text
    assert "approved" in text
    assert "5000.00" in text


# ---------------------------------------------------------------------------
# Report generator tests
# ---------------------------------------------------------------------------

def test_report_type_registered() -> None:
    import importlib
    mod = importlib.import_module("services.export.report_generator")
    assert "statement_of_work" in mod.REPORT_GENERATORS
    assert hasattr(mod, "generate_statement_of_work")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_schema_has_cascade_deletes()
    test_seed_has_sow()
    test_seed_has_deliverables()
    test_seed_has_payment_schedule()
    test_seed_has_change_request()
    test_report_type_registered()
    print("All tests passed.")
