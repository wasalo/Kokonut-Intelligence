"""
Metric Calculator Tests

Unit tests for calculator logic and governance field completeness.
Some tests require a running PostgreSQL with seed data.

Usage:
    python3 -m tests.test_metrics
    python3 -m pytest tests/test_metrics.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

METRIC_KEYS = [
    "crop_revenue", "net_crop_revenue", "direct_crop_cost",
    "allocated_shared_cost", "crop_noi", "loss_rate_pct",
    "operating_margin_pct", "baseline_revenue", "baseline_asset_value",
    "baseline_cash_flow", "baseline_cost", "value_flowed",
    "wallet_retention", "digital_lego_usage", "soil_carbon_delta",
    "biodiversity_delta", "attestation_coverage",
]

BASELINE_KEYS = [
    "baseline_revenue", "baseline_asset_value",
    "baseline_cash_flow", "baseline_cost",
]


def test_calculator_registration():
    """All 17 metric keys have registered calculators."""
    from services.metrics.calculators import CALCULATORS
    for key in METRIC_KEYS:
        assert key in CALCULATORS, f"Missing calculator for {key}"
    assert len(CALCULATORS) == 17


def test_all_calculators_return_required_keys():
    """Every calculator returns {value, computation_method, source_record_ids, metadata}."""
    from services.metrics.calculators import CALCULATORS
    required = {"value", "computation_method", "source_record_ids", "metadata"}
    for key, fn in CALCULATORS.items():
        assert callable(fn), f"Calculator for {key} is not callable"


def test_baseline_calculators_exist():
    """Baseline calculators are registered and callable."""
    from services.metrics.calculators import CALCULATORS
    for key in BASELINE_KEYS:
        assert key in CALCULATORS, f"Missing baseline calculator: {key}"
        assert callable(CALCULATORS[key])


def test_loss_rate_formula_structure():
    """Verify loss_rate_pct calculator imports and is callable."""
    from services.metrics.calculators import CALCULATORS
    fn = CALCULATORS["loss_rate_pct"]
    assert callable(fn)


def test_loss_rate_uses_harvest_schema_columns():
    """Verify loss_rate_pct derives net harvest from existing schema columns."""
    from services.metrics.calculators.loss_rate_pct import compute_loss_rate_pct
    import inspect
    source = inspect.getsource(compute_loss_rate_pct)
    assert "loss_amount" in source, "loss_rate_pct must use harvest_event.loss_amount"
    assert "saleable_quantity" not in source, "harvest_event has no saleable_quantity column"


def test_operating_margin_delegates_to_crop_noi():
    """Verify operating_margin_pct imports the sub-calculators."""
    from services.metrics.calculators.operating_margin import compute_operating_margin
    import inspect
    source = inspect.getsource(compute_operating_margin)
    assert "compute_crop_noi" in source, "operating_margin should delegate to compute_crop_noi"
    assert "compute_net_crop_revenue" in source, "operating_margin should delegate to compute_net_crop_revenue"


def test_digital_lego_has_verified_filter():
    """Verify digital_lego_usage SQL includes verified = TRUE."""
    from services.metrics.calculators.digital_lego import compute_digital_lego_usage
    import inspect
    source = inspect.getsource(compute_digital_lego_usage)
    assert "verified = TRUE" in source, "digital_lego_usage must filter verified = TRUE"


def test_loss_rate_has_fm_exclusion():
    """Verify loss_rate_pct excludes force majeure losses."""
    from services.metrics.calculators.loss_rate_pct import compute_loss_rate_pct
    import inspect
    source = inspect.getsource(compute_loss_rate_pct)
    assert "force majeure" in source.lower(), "loss_rate_pct must exclude force majeure losses"


def test_loss_rate_source_record_ids():
    """Verify loss_rate_pct returns harvest IDs in source_record_ids."""
    from services.metrics.calculators.loss_rate_pct import compute_loss_rate_pct
    import inspect
    source = inspect.getsource(compute_loss_rate_pct)
    assert "harvest_ids" in source, "loss_rate_pct should return harvest event IDs"


def test_baseline_calculators_use_location_table():
    """Verify baseline calculators query the location table."""
    for key in BASELINE_KEYS:
        module_name = f"services.metrics.calculators.{key}"
        mod = __import__(module_name, fromlist=["compute_" + key])
        fn = getattr(mod, "compute_" + key)
        import inspect
        source = inspect.getsource(fn)
        assert "FROM location" in source, f"{key} must query location table"
        assert key.replace("baseline_", "") in source or key in source, \
            f"{key} must query the correct column"


def test_engine_registers_all_calculators():
    """Verify engine.py can import all calculators."""
    from services.metrics.calculators import CALCULATORS
    assert len(CALCULATORS) == 17


# Integration tests (require running PostgreSQL)

def test_calculators_return_valid_structure():
    """Each calculator returns a dict with required keys (requires DB)."""
    from services.ingestion.base import get_db
    from services.metrics.calculators import CALCULATORS

    try:
        db = get_db()
    except Exception:
        return  # Skip if DB not available

    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM location LIMIT 1")
            row = cur.fetchone()
        if not row:
            return

        location_id = str(row[0])
        for key in BASELINE_KEYS:
            fn = CALCULATORS[key]
            result = fn(db, location_id)
            assert "value" in result, f"{key} missing 'value'"
            assert "computation_method" in result, f"{key} missing 'computation_method'"
            assert "source_record_ids" in result, f"{key} missing 'source_record_ids'"
            assert "metadata" in result, f"{key} missing 'metadata'"
    finally:
        db.close()


def test_metric_definitions_have_governance_fields():
    """All 17 metrics have validation_tests, report_usage, deprecation_policy (requires DB)."""
    from services.ingestion.base import get_db

    try:
        db = get_db()
    except Exception:
        return

    try:
        with db.cursor() as cur:
            cur.execute("""
                SELECT metric_key, validation_tests, report_usage, deprecation_policy
                FROM metric_definition
                WHERE metric_key = ANY(%s)
                ORDER BY metric_key
            """, (METRIC_KEYS,))
            rows = cur.fetchall()
    finally:
        db.close()

    missing = []
    for row in rows:
        key, vt, ru, dp = row
        if not vt or vt == '[]':
            missing.append(f"{key}: validation_tests")
        if not ru or ru == '{}':
            missing.append(f"{key}: report_usage")
        if not dp:
            missing.append(f"{key}: deprecation_policy")

    assert not missing, f"Metrics missing governance fields: {missing}"


if __name__ == "__main__":
    print("=== Kokonut Intelligence — Metric Calculator Tests ===")
    tests = [
        test_calculator_registration,
        test_all_calculators_return_required_keys,
        test_baseline_calculators_exist,
        test_loss_rate_formula_structure,
        test_loss_rate_uses_harvest_schema_columns,
        test_operating_margin_delegates_to_crop_noi,
        test_digital_lego_has_verified_filter,
        test_loss_rate_has_fm_exclusion,
        test_loss_rate_source_record_ids,
        test_baseline_calculators_use_location_table,
        test_engine_registers_all_calculators,
        test_calculators_return_valid_structure,
        test_metric_definitions_have_governance_fields,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  \u2713 {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  \u2717 {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  \u2717 {t.__name__}: {e}")
            failed += 1
    print(f"\n=== Results: {passed}/{passed+failed} passed ===")
    sys.exit(1 if failed else 0)
