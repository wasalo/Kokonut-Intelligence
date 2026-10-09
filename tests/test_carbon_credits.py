"""Carbon credit tests."""

from pathlib import Path
from unittest.mock import MagicMock

SCHEMA = Path("schemas/postgres/078_carbon_credits.sql")
INTEGRITY_SCHEMA = Path("schemas/postgres/163_carbon_retirement_integrity.sql")


def test_schema_file_exists() -> None:
    assert SCHEMA.exists()


def test_schema_has_carbon_credit_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS carbon_credit" in content


def test_schema_has_credit_adjustment_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS credit_adjustment" in content


def test_schema_has_credit_retirement_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS credit_retirement" in content


def test_schema_has_credit_transfer_table() -> None:
    content = SCHEMA.read_text()
    assert "CREATE TABLE IF NOT EXISTS credit_transfer" in content


def test_schema_has_public_view() -> None:
    content = SCHEMA.read_text()
    assert "v_public_carbon_credit_inventory" in content
    assert "v_carbon_credit_balance" in content
    assert "v_credit_adjustment_history" in content


def test_schema_has_level6_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_carbon_credit_public_level6" in content
    assert "evidence_maturity = 6" in content


def test_schema_has_lifecycle_constraints() -> None:
    content = SCHEMA.read_text()
    assert "chk_carbon_credit_lifecycle" in content
    assert "chk_credit_adj_lifecycle" in content
    assert "chk_credit_retire_lifecycle" in content
    assert "chk_credit_xfer_lifecycle" in content


def test_schema_has_adjustment_type_constraint() -> None:
    content = SCHEMA.read_text()
    assert "chk_credit_adj_type" in content
    assert "measurement_update" in content
    assert "reversal" in content


def test_schema_has_buffer_pool() -> None:
    content = SCHEMA.read_text()
    assert "buffer_pool_pct" in content
    assert "chk_carbon_credit_buffer" in content


def test_schema_has_generated_columns() -> None:
    content = SCHEMA.read_text()
    assert "GENERATED ALWAYS AS" in content
    assert "available_tonnes" in content
    assert "total_value_usd" in content


def test_carbon_credits_service_exists() -> None:
    assert Path("services/analytics/carbon_credits.py").exists()


def test_service_has_issue_credit() -> None:
    from services.analytics.carbon_credits import issue_credit
    assert callable(issue_credit)


def test_service_has_adjust_credit() -> None:
    from services.analytics.carbon_credits import adjust_credit
    assert callable(adjust_credit)


def test_service_has_retire_credit() -> None:
    from services.analytics.carbon_credits import retire_credit
    assert callable(retire_credit)


def test_service_has_retirement_review() -> None:
    from services.analytics.carbon_credits import review_retirement
    assert callable(review_retirement)


def test_retirement_integrity_schema() -> None:
    content = INTEGRITY_SCHEMA.read_text()
    assert "reserved_tonnes" in content
    assert "idempotency_key" in content
    assert "reviewer_id <> created_by" in content
    assert "retired_tonnes + reserved_tonnes <= issuable_tonnes" in content


def test_retirement_uses_row_locks_and_conditional_updates() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "SELECT * FROM carbon_credit WHERE id = %s FOR UPDATE" in content
    assert "SELECT * FROM credit_retirement WHERE id = %s FOR UPDATE" in content
    assert "issuable_tonnes - retired_tonnes - reserved_tonnes >= %s" in content
    assert "reserved_tonnes >= %s" in content


def test_draft_retirement_only_reserves_supply() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    draft_section = content[content.index("def retire_credit("):content.index("def review_retirement(")]
    assert "reserved_tonnes = reserved_tonnes + %s" in draft_section
    assert "retired_tonnes = retired_tonnes + %s" not in draft_section


def test_service_has_list_credits() -> None:
    from services.analytics.carbon_credits import list_credits
    assert callable(list_credits)


def test_service_has_get_balance() -> None:
    from services.analytics.carbon_credits import get_balance
    assert callable(get_balance)


def test_service_has_check_adjustments() -> None:
    from services.analytics.carbon_credits import check_adjustments
    assert callable(check_adjustments)


def test_service_has_recompute_sequestration() -> None:
    from services.analytics.carbon_credits import recompute_sequestration
    assert callable(recompute_sequestration)


def test_service_has_cli() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert 'if __name__' in content
    assert "--issue" in content
    assert "--adjust" in content
    assert "--retire" in content
    assert "--list" in content
    assert "--balance" in content


def test_safety_governed_collections() -> None:
    from services.agents.safety import GOVERNED_COLLECTIONS
    assert "carbon_credit" in GOVERNED_COLLECTIONS
    assert "credit_adjustment" in GOVERNED_COLLECTIONS
    assert "credit_retirement" in GOVERNED_COLLECTIONS
    assert "credit_transfer" in GOVERNED_COLLECTIONS


def test_seed_file_exists() -> None:
    assert Path("schemas/seeds/078_carbon_credits.sql").exists()


def test_seed_has_adelphi_credit() -> None:
    content = Path("schemas/seeds/078_carbon_credits.sql").read_text()
    assert "carbon_credit" in content
    assert "KKNT-2026-ADELPHI-0001" in content
    assert "IPCC 2006" in content


def test_service_imports_carbon_balance() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "from .carbon_balance import" in content


def test_service_uses_logging() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "get_logger" in content


def test_retirement_checks_available() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "issuable_tonnes" in content
    assert "retired_tonnes" in content
    assert "available" in content


def test_adjustment_tracks_delta() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "delta_tonnes" in content
    assert "delta_pct" in content
    assert "within_margin" in content


def test_credit_code_generation() -> None:
    content = Path("services/analytics/carbon_credits.py").read_text()
    assert "KKNT-" in content
    assert "_generate_credit_code" in content


def test_public_view_gates_on_farm_registry() -> None:
    content = SCHEMA.read_text()
    assert "farm_registry_record" in content
    assert "status IN ('verified', 'published')" in content


def test_adjustment_trigger_sources() -> None:
    content = SCHEMA.read_text()
    assert "tree_inventory" in content
    assert "soil_carbon_measurement" in content
    assert "ghg_emissions_inventory" in content
    assert "remote_sensing" in content


def test_retirement_review_requires_reviewer() -> None:
    from services.analytics.carbon_credits import review_retirement

    conn = MagicMock()
    result = review_retirement(conn, "retirement", "", "confirm")
    assert result == {"status": "error", "message": "reviewer_id is required"}
    conn.cursor.assert_not_called()


def test_conflicting_terminal_retirement_decision_is_rejected() -> None:
    from services.analytics.carbon_credits import review_retirement

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = {
        "id": "retirement", "status": "verified", "created_by": "requester"
    }

    result = review_retirement(conn, "retirement", "reviewer", "reject")

    assert result["status"] == "error"
    assert "already verified" in result["message"]
    conn.rollback.assert_called_once_with()


def test_same_terminal_retirement_decision_is_idempotent() -> None:
    from services.analytics.carbon_credits import review_retirement

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = {
        "id": "retirement", "status": "rejected", "created_by": "requester"
    }

    result = review_retirement(conn, "retirement", "reviewer", "reject")

    assert result["status"] == "success"
    assert result["idempotent"] is True
