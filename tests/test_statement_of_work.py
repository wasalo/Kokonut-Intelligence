"""Statement of Work tests: schema, seeds, report generator."""

from pathlib import Path

import pytest

SCHEMA = Path("schemas/postgres/063_statement_of_work.sql")
FIX_MIGRATION = Path("schemas/postgres/320_consent_lifecycle_public_gates.sql")
FINANCIAL_GATES_MIGRATION = Path("schemas/postgres/321_public_financial_governance.sql")
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


def test_public_views_require_a_verified_registry_record() -> None:
    text = FIX_MIGRATION.read_text()
    assert "AND (fr.id IS NULL OR fr.status IN ('verified', 'published'))" not in text
    assert "EXISTS (SELECT 1 FROM farm_registry_record" in text


def test_public_cross_farm_portfolio_uses_governed_revenue_only() -> None:
    text = FINANCIAL_GATES_MIGRATION.read_text()
    assert "re.status IN ('verified', 'published')" in text
    assert "fr.status IN ('verified', 'published')" in text
    assert "cfp.*" not in text


def test_public_cross_farm_portfolio_preserves_view_column_contract() -> None:
    text = FINANCIAL_GATES_MIGRATION.read_text()
    for column in [
        "cfp.id",
        "cfp.portfolio_name",
        "cfp.total_farm_count",
        "cfp.total_area_m2",
        "cfp.total_trees",
        "cfp.total_revenue_usd",
        "cfp.total_carbon_sequestered",
        "cfp.avg_regen_score",
        "cfp.avg_ebf_score",
        "cfp.regions_covered",
        "cfp.last_computed_at",
        "cfp.metadata",
        "cfp.created_at",
        "cfp.updated_at",
    ]:
        assert column in text, f"View column contract missing: {column}"
    assert "COUNT(DISTINCT f.id)::INTEGER" not in text


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


class _StatementOfWorkCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        normalized = " ".join(query.split())
        self.connection.queries.append((normalized, params))
        if "FROM location" in normalized:
            self.rows = [{"name": "Kokonut Genesis"}]
        elif "FROM statement_of_work" in normalized:
            self.rows = [self.connection.sow_row]
        elif "FROM financial_sustainability_plan" in normalized:
            self.rows = []
        elif "FROM sow_deliverable" in normalized:
            self.rows = self.connection.child_rows["sow_deliverable"]
        elif "FROM sow_payment_schedule" in normalized:
            self.rows = self.connection.child_rows["sow_payment_schedule"]
        elif "FROM sow_change_request" in normalized:
            self.rows = self.connection.child_rows["sow_change_request"]
        elif any(
            f"FROM {table}" in normalized
            for table in (
                "objective",
                "farm_task",
                "development_phase",
                "framework_step",
                "staff",
                "partner",
                "forecast_output",
                "sow_deliverable",
                "sow_payment_schedule",
                "sow_change_request",
            )
        ):
            self.rows = []
        else:
            raise AssertionError(f"unexpected Statement of Work query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _StatementOfWorkConnection:
    def __init__(self, sow_row, child_rows=None):
        self.sow_row = sow_row
        self.child_rows = {
            "sow_deliverable": [],
            "sow_payment_schedule": [],
            "sow_change_request": [],
        }
        self.child_rows.update(child_rows or {})
        self.queries = []

    def cursor(self, **_kwargs):
        return _StatementOfWorkCursor(self)


def test_report_projects_current_sow_columns_and_preserves_row_payload():
    from services.export.reports.operations import generate_statement_of_work

    columns = [
        "id",
        "location_id",
        "sow_name",
        "sow_version",
        "effective_date",
        "expiration_date",
        "client_name",
        "contractor_name",
        "total_contract_value",
        "currency",
        "payment_terms",
        "status",
        "metadata",
        "source_system",
        "source_id",
        "source_raw",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    sow_row = {column: f"value-{index}" for index, column in enumerate(columns)}
    connection = _StatementOfWorkConnection(sow_row)

    report = generate_statement_of_work(
        connection, "11111111-1111-4111-8111-111111111111"
    )

    sow_query, sow_params = next(
        (query, params)
        for query, params in connection.queries
        if "FROM statement_of_work" in query
    )
    projection = sow_query.split(" FROM ", maxsplit=1)[0]
    assert projection == "SELECT " + ", ".join(columns)
    assert sow_params == ("11111111-1111-4111-8111-111111111111",)
    assert report["sow"] == sow_row


@pytest.mark.parametrize(
    ("table", "report_field", "ordering", "columns"),
    [
        (
            "sow_deliverable",
            "deliverables",
            "due_date",
            [
                "id",
                "sow_id",
                "deliverable_name",
                "description",
                "acceptance_criteria",
                "due_date",
                "delivered_at",
                "status",
                "notes",
                "metadata",
                "source_system",
                "source_id",
                "source_raw",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "sow_payment_schedule",
            "payment_schedule",
            "due_date",
            [
                "id",
                "sow_id",
                "milestone_name",
                "amount",
                "due_date",
                "payment_status",
                "invoice_number",
                "paid_at",
                "metadata",
                "source_system",
                "source_id",
                "source_raw",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "sow_change_request",
            "change_requests",
            "created_at",
            [
                "id",
                "sow_id",
                "change_name",
                "description",
                "impact_on_timeline",
                "impact_on_budget",
                "requested_by",
                "status",
                "decided_at",
                "metadata",
                "source_system",
                "source_id",
                "source_raw",
                "created_at",
                "updated_at",
            ],
        ),
    ],
)
def test_report_projects_current_sow_child_columns_and_preserves_payload(
    table, report_field, ordering, columns
):
    from services.export.reports.operations import generate_statement_of_work

    child_row = {column: f"value-{index}" for index, column in enumerate(columns)}
    connection = _StatementOfWorkConnection(
        sow_row={"id": "sow-1"},
        child_rows={table: [child_row]},
    )

    report = generate_statement_of_work(
        connection, "11111111-1111-4111-8111-111111111111"
    )

    child_query, child_params = next(
        (query, params)
        for query, params in connection.queries
        if f"FROM {table}" in query
    )
    projection = child_query.split(" FROM ", maxsplit=1)[0]
    assert projection == "SELECT " + ", ".join(columns)
    assert f"WHERE sow_id = %s ORDER BY {ordering}" in child_query
    assert child_params == ("sow-1",)
    assert report[report_field] == [child_row]


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
