"""Source-level checks for selected semantic cardinality rules."""

from pathlib import Path


SQL = Path("schemas/postgres/310_cardinality_temporal_integrity.sql").read_text()


def test_current_kyc_and_role_cardinality_is_explicit():
    assert "uq_kyc_current_approved_method" in SQL
    assert "WHERE verification_status = 'approved'" in SQL
    assert "uq_role_assignment_active_scope" in SQL
    assert "WHERE status = 'active'" in SQL


def test_metric_semantic_uniqueness_and_temporal_checks_exist():
    assert "uq_metric_value_semantic_current" in SQL
    assert "chk_kyc_expiry_after_creation" in SQL
    assert "chk_board_term_order" in SQL
    assert "chk_forecast_version_positive" in SQL
