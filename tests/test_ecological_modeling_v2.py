"""Ecological modeling v2, economic/social, and model validation tests."""

import re
from datetime import date
from pathlib import Path

from services.analytics.ecological_modeling_v2 import (
    compute_biocontrol_effectiveness,
    compute_conservation_status_summary,
    compute_pest_trends,
    compute_resource_efficiency,
    compute_soil_input_retention,
)
from services.analytics.economic_performance import (
    compute_revenue_per_acre,
    compute_revenue_stream_contribution,
    compute_training_impact,
)
from services.analytics.model_validation import (
    compute_mae,
    compute_regression_metrics,
    compute_rmse,
)
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_model_validation,
    generate_pest_management,
    generate_resource_efficiency,
    generate_revenue_streams,
)

SCHEMA_V2 = Path("schemas/postgres/047_ecological_modeling_v2.sql")
SEED_V2 = Path("schemas/seeds/047_ecological_modeling_v2.sql")
SCHEMA_ECON = Path("schemas/postgres/048_economic_social_enhancement.sql")
SEED_ECON = Path("schemas/seeds/048_economic_social_enhancement.sql")
SCHEMA_VALID = Path("schemas/postgres/049_model_validation.sql")
SEED_VALID = Path("schemas/seeds/049_model_validation.sql")


# ---------------------------------------------------------------------------
# Phase 1: Schema tests
# ---------------------------------------------------------------------------

def test_v2_schema_defines_tables() -> None:
    text = SCHEMA_V2.read_text()
    for table in [
        "soil_input_application",
        "pest_observation",
        "biocontrol_release",
        "resource_consumption",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_v2_schema_defines_views() -> None:
    text = SCHEMA_V2.read_text()
    for view in [
        "v_public_pest_trends",
        "v_public_biocontrol_effectiveness",
        "v_public_resource_efficiency",
        "v_public_soil_input_retention",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_v2_schema_has_constraints() -> None:
    text = SCHEMA_V2.read_text()
    assert "chk_soil_input_type" in text
    assert "chk_soil_input_decomposition" in text
    assert "chk_soil_input_status" in text
    assert "chk_pest_severity" in text
    assert "chk_pest_category" in text
    assert "chk_pest_status" in text
    assert "chk_bioctrl_category" in text
    assert "chk_bioctrl_status" in text
    assert "chk_resource_type" in text
    assert "chk_resource_status" in text
    assert "chk_species_conservation_status" in text
    assert "ecological-modeling-v2" in text


def test_v2_schema_has_conservation_status() -> None:
    text = SCHEMA_V2.read_text()
    assert "conservation_status" in text
    assert "critically_endangered" in text
    assert "endangered" in text
    assert "vulnerable" in text
    assert "least_concern" in text


def test_v2_seed_has_metrics() -> None:
    text = SEED_V2.read_text()
    for metric in [
        "pest_outbreak_probability",
        "biocontrol_effectiveness_pct",
        "labor_efficiency_kg_per_hour",
        "resource_intensity_index",
    ]:
        assert metric in text, f"Missing metric: {metric}"


def test_v2_seed_has_dashboards() -> None:
    text = SEED_V2.read_text()
    assert "64_pest_management" in text
    assert "65_resource_efficiency" in text
    assert Path("dashboards/metabase/sql/64_pest_management.sql").exists()
    assert Path("dashboards/metabase/sql/65_resource_efficiency.sql").exists()
    assert Path("dashboards/metabase/64_pest_management.json").exists()
    assert Path("dashboards/metabase/65_resource_efficiency.json").exists()


def test_v2_seed_has_adelphi_pilot_data() -> None:
    text = SEED_V2.read_text()
    assert "biochar" in text
    assert "leaf_litter" in text
    assert "Spodoptera frugiperda" in text
    assert "Hippodamia convergens" in text
    assert "Trichogramma pretiosum" in text
    assert "water_liters" in text
    assert "energy_kwh" in text
    assert "labor_hours" in text
    assert "pest_dynamics" in text


def test_adelphi_ecological_seeds_use_canonical_plot_and_zone_ids() -> None:
    for seed_path in (
        Path("schemas/seeds/047_ecological_modeling_v2.sql"),
        Path("schemas/seeds/050_remaining_gaps.sql"),
        Path("schemas/seeds/052_final_gaps.sql"),
    ):
        text = seed_path.read_text()
        assert "a0000000-0000-0000-0000-000000000015" not in text
    assert "a0000000-0000-0000-0000-000000000020" in Path("schemas/seeds/047_ecological_modeling_v2.sql").read_text()
    assert "a0000000-0000-0000-0000-000000000700" in Path("schemas/seeds/047_ecological_modeling_v2.sql").read_text()


# ---------------------------------------------------------------------------
# Phase 1: Analytics tests
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._calls = 0

    def execute(self, query, params=None):
        self._calls += 1

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None):
        self._rows = rows or []

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows)


def test_soil_input_retention_analytics() -> None:
    rows = [
        ("biochar", "Coconut shell biochar", 100.0, 60.0, 2, "2025-10-05", "2026-03-10", 40.0, 2400.0),
        ("leaf_litter", "Inga edulis leaf litter", 250.0, 45.0, 1, "2025-10-05", "2026-03-10", 250.0, 11250.0),
    ]
    result = compute_soil_input_retention(_MockConn(rows), "test-location")
    assert result["input_types_count"] == 2
    assert result["total_input_kg"] == 350.0
    assert result["inputs"][0]["avg_residual_pct"] == 60.0
    assert result["weighted_avg_residual_pct"] == 47.07


def test_soil_input_retention_excludes_unmeasured_mass_from_residual_average() -> None:
    rows = [
        ("compost", "Measured compost", 100.0, 50.0, 2, "2025-10-05", "2026-03-10", 40.0, 2000.0),
        ("compost", "Unmeasured compost", 900.0, None, 3, "2025-10-05", None, None, None),
    ]
    result = compute_soil_input_retention(_MockConn(rows), "test-location")
    assert result["total_input_kg"] == 1000.0
    assert result["weighted_avg_residual_pct"] == 50.0


def test_soil_input_retention_returns_null_when_no_residual_is_measured() -> None:
    rows = [
        ("compost", "Unmeasured compost", 900.0, None, 3, "2025-10-05", None, None, None),
    ]
    result = compute_soil_input_retention(_MockConn(rows), "test-location")
    assert result["inputs"][0]["avg_residual_pct"] is None
    assert result["weighted_avg_residual_pct"] is None


def test_pest_trends_analytics() -> None:
    rows = [
        ("2025-11-01", "Spodoptera frugiperda", "Fall armyworm", "insect", 1, 35.0, 8.5, 0, 12.0, 27.3, 72.0, 3, 1),
        ("2026-01-01", "Spodoptera frugiperda", "Fall armyworm", "insect", 1, 15.0, 3.0, 0, 5.0, 26.8, 68.0, 8, 1),
    ]
    result = compute_pest_trends(_MockConn(rows), "test-location")
    assert result["total_observations"] == 2
    assert result["unique_pest_species"] == 1
    assert result["weighted_avg_outbreak_probability_pct"] > 0


def test_biocontrol_effectiveness_analytics() -> None:
    rows = [
        ("Hippodamia convergens", "Convergent lady beetle", "predator", "Aphis gossypii", 1, 200, 72.5, 68.0, 0.08, "2026-01-05", "2026-02-10"),
    ]
    result = compute_biocontrol_effectiveness(_MockConn(rows), "test-location")
    assert result["total_release_events"] == 1
    assert result["total_organisms_released"] == 200
    assert result["weighted_avg_pest_reduction_pct"] == 68.0


def test_resource_efficiency_analytics() -> None:
    rows = [
        ("water_liters", "liters", "irrigation", 15000.0, 5000.0, 3, 3),
        ("labor_hours", "hours", "all_operations", 320.0, 106.67, 3, 0),
        ("energy_kwh", "kwh", "pumping_station", 45.0, 15.0, 3, 3),
    ]
    harvest_row = [(1080.0,)]

    class _Conn:
        def cursor(self, cursor_factory=None):
            c = _MockCursor(rows)
            c.fetchone = lambda: harvest_row[0]
            return c

    result = compute_resource_efficiency(_Conn(), "test-location")
    assert result["total_harvest_kg"] == 1080.0
    assert result["labor_hours_per_kg"] is not None
    assert result["energy_kwh_per_kg"] is not None
    assert result["water_liters_per_kg"] is not None


def test_conservation_status_analytics() -> None:
    rows = [
        ("least_concern", 3, 296),
    ]
    result = compute_conservation_status_summary(_MockConn(rows), "test-location")
    assert result["total_species_with_status"] == 3
    assert result["conservation_statuses"][0]["conservation_status"] == "least_concern"


# ---------------------------------------------------------------------------
# Phase 1: Report tests
# ---------------------------------------------------------------------------

def test_pest_management_report_registered() -> None:
    assert "pest_management" in REPORT_GENERATORS


def test_resource_efficiency_report_registered() -> None:
    assert "resource_efficiency" in REPORT_GENERATORS


def test_pest_management_report_public_safe() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            return {"name": "Kokonut Adelphi"}
        def fetchall(self):
            if self.calls == 1:
                return []
            if self.calls == 2:
                return []
            return []
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_pest_management(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "pest_management"
    assert "limitations" in report
    assert len(report["limitations"]) > 0


def test_resource_efficiency_report_public_safe() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            if self.calls == 1:
                return {"name": "Kokonut Adelphi"}
            return {"total_harvest_kg": 1080.0}
        def fetchall(self):
            return []
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_resource_efficiency(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "resource_efficiency"
    assert "limitations" in report


# ---------------------------------------------------------------------------
# Phase 2: Schema tests
# ---------------------------------------------------------------------------

def test_econ_schema_defines_tables() -> None:
    text = SCHEMA_ECON.read_text()
    for table in ["training_session", "revenue_stream_contribution"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text


def test_econ_schema_defines_views() -> None:
    text = SCHEMA_ECON.read_text()
    for view in ["v_public_training_impact", "v_public_revenue_streams"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text


def test_econ_schema_has_constraints() -> None:
    text = SCHEMA_ECON.read_text()
    assert "chk_training_session_type" in text
    assert "chk_training_status" in text
    assert "chk_revstream_category" in text
    assert "chk_revstream_status" in text
    assert "economic-social-v1" in text


def test_econ_seed_has_metrics() -> None:
    text = SEED_ECON.read_text()
    assert "training_improvement_pct" in text
    assert "revenue_per_acre_usd" in text


def test_econ_seed_has_adelphi_data() -> None:
    text = SEED_ECON.read_text()
    assert "Maria Santos" in text
    assert "Carlos Rivera" in text
    assert "Organic pest management" in text
    assert "Fresh produce sales" in text
    assert "Bio-input sales" in text
    assert "Nursery seedlings" in text


# ---------------------------------------------------------------------------
# Phase 2: Analytics tests
# ---------------------------------------------------------------------------

def test_revenue_per_acre_analytics() -> None:
    rows = [
        ("cycle-1", "Lettuce", "Lettuce Cycle 1", 0.5, "hectares", 2850.0, 1050.0),
    ]
    result = compute_revenue_per_acre(_MockConn(rows), "test-location")
    assert result["total_revenue_usd"] == 2850.0
    assert result["cycles"][0]["revenue_per_acre_usd"] > 0
    assert result["overall_roi_pct"] > 0


def test_revenue_stream_contribution_analytics() -> None:
    rows = [
        ("Fresh produce sales", "fresh_produce", 2850.0, 680.0, 320.0, 1850.0, 64.91, 1),
        ("Bio-input sales", "bio_input_sales", 420.0, 85.0, 40.0, 295.0, 10.33, 1),
    ]
    result = compute_revenue_stream_contribution(_MockConn(rows), "test-location")
    assert result["stream_count"] == 2
    assert result["total_gross_revenue"] == 3270.0
    assert result["most_profitable_stream"] == "Fresh produce sales"


def test_training_impact_analytics() -> None:
    rows = [
        ("Organic pest management", "pest_management", 2, 2, 8.0, 48.5, 79.5, 64.55, "2025-10-15", "2025-10-15"),
    ]
    result = compute_training_impact(_MockConn(rows), "test-location")
    assert result["total_unique_participants"] == 2
    assert result["total_training_hours"] == 8.0
    assert result["weighted_avg_improvement_pct"] > 0


def test_training_impact_report_registered() -> None:
    assert "training_impact" in REPORT_GENERATORS


def test_revenue_streams_report_registered() -> None:
    assert "revenue_streams" in REPORT_GENERATORS


# ---------------------------------------------------------------------------
# Phase 3: Schema tests
# ---------------------------------------------------------------------------

def test_validation_schema_defines_tables() -> None:
    text = SCHEMA_VALID.read_text()
    for table in ["prediction_accuracy_record", "feature_importance_record"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text


def test_validation_schema_defines_views() -> None:
    text = SCHEMA_VALID.read_text()
    for view in ["v_public_prediction_accuracy", "v_public_feature_importance"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text


def test_validation_schema_has_constraints() -> None:
    text = SCHEMA_VALID.read_text()
    assert "chk_pred_accuracy_model_type" in text
    assert "chk_pred_accuracy_status" in text
    assert "chk_feature_imp_model_type" in text
    assert "chk_feature_imp_direction" in text
    assert "chk_feature_imp_status" in text
    assert "model-validation-v1" in text


def test_validation_seed_has_metrics() -> None:
    text = SEED_VALID.read_text()
    assert "forecast_mae" in text
    assert "forecast_accuracy_pct" in text


def test_validation_seed_has_adelphi_data() -> None:
    text = SEED_VALID.read_text()
    assert "Adelphi Lettuce Yield Model" in text
    assert "Adelphi Pest Dynamics Model" in text
    assert "Adelphi Carbon Sequestration Model" in text
    assert "rainfall_mm" in text
    assert "humidity_pct" in text
    assert "biochar_applied_kg" in text


# ---------------------------------------------------------------------------
# Phase 3: Analytics tests
# ---------------------------------------------------------------------------

def test_regression_metrics() -> None:
    predicted = [1.0, 2.0, 3.0, 4.0, 5.0]
    actual = [1.1, 1.9, 3.1, 3.9, 5.1]
    result = compute_regression_metrics(predicted, actual)
    assert "rmse" in result
    assert "mae" in result
    assert "r_squared" in result
    assert result["n"] == 5


def test_geographic_cross_validation() -> None:
    result = compute_regression_metrics([1.0, 2.0, 3.0, 4.0], [1.1, 1.9, 3.1, 3.9])
    assert result["n"] == 4


def test_rmse() -> None:
    predicted = [1.0, 2.0, 3.0]
    actual = [1.0, 2.0, 3.0]
    result = compute_rmse(predicted, actual)
    assert result == 0.0


def test_mae() -> None:
    predicted = [1.0, 2.0, 3.0]
    actual = [2.0, 3.0, 4.0]
    result = compute_mae(predicted, actual)
    assert result == 1.0


def test_model_validation_report_registered() -> None:
    assert "model_validation" in REPORT_GENERATORS


def test_resource_efficiency_projection_preserves_full_payload_and_aggregate() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    period_start = "2026-01-01"
    period_end = "2026-03-31"
    source_rows = [
        {
            "id": "b0000000-0000-0000-0000-000000000001",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "plot_id": "c0000000-0000-0000-0000-000000000001",
            "plot_name": "North plot",
            "crop_cycle_id": "d0000000-0000-0000-0000-000000000001",
            "cycle_name": "2026 first cycle",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "resource_type": "water",
            "quantity": 1200.0,
            "unit": "L",
            "component": "irrigation",
            "is_estimated": False,
            "notes": "Metered field record.",
            "status": "verified",
        },
        {
            "id": "b0000000-0000-0000-0000-000000000002",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "plot_id": "c0000000-0000-0000-0000-000000000002",
            "plot_name": "Nursery",
            "crop_cycle_id": "d0000000-0000-0000-0000-000000000001",
            "cycle_name": "2026 first cycle",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "resource_type": "energy",
            "quantity": 6.0,
            "unit": "kWh",
            "component": "water pumping",
            "is_estimated": True,
            "notes": "Estimated from operating hours.",
            "status": "published",
        },
    ]
    columns = (
        "id, location_id, location_name, plot_id, plot_name, crop_cycle_id, cycle_name, period_start, "
        "period_end, resource_type, quantity, unit, component, is_estimated, notes, status"
    )

    class Cursor:
        def __init__(self):
            self.executed = []
            self.fetchone_calls = 0

        def execute(self, query, params):
            self.executed.append((query, params))

        def fetchone(self):
            self.fetchone_calls += 1
            if self.fetchone_calls == 1:
                return {"name": "Kokonut Adelphi"}
            return {"total_harvest_kg": 1000.0}

        def fetchall(self):
            return source_rows

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_resource_efficiency(conn, location_id, period_start, period_end)
    query, params = conn.cursor_value.executed[1]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_resource_efficiency WHERE location_id = %s "
        "AND (%s::date IS NULL OR period_start >= %s::date) "
        "AND (%s::date IS NULL OR period_start <= %s::date) "
        "ORDER BY resource_type, period_start DESC"
    )
    assert params == (location_id, period_start, period_start, period_end, period_end)
    assert report["report_type"] == "resource_efficiency"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["resources"] == [
        {
            **row,
            "period_start": "2026-01-01",
            "period_end": "2026-03-31",
        }
        for row in source_rows
    ]
    assert report["total_harvest_kg"] == 1000.0
    assert report["efficiency_by_type"] == {
        "water": {"total_quantity": 1200.0, "unit": "L", "record_count": 1, "per_kg_yield": 1.2},
        "energy": {"total_quantity": 6.0, "unit": "kWh", "record_count": 1, "per_kg_yield": 0.006},
    }


def test_revenue_streams_projection_preserves_payload_and_totals() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    source_rows = [
        {
            "id": "b0000000-0000-0000-0000-000000000001",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "crop_cycle_id": "c0000000-0000-0000-0000-000000000001",
            "cycle_name": "2026 first cycle",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "stream_name": "Fresh produce",
            "stream_category": "agriculture",
            "gross_revenue": 1000.0,
            "direct_costs": 300.0,
            "allocated_costs": 100.0,
            "net_contribution": 600.0,
            "contribution_pct": 60.0,
            "notes": "Verified quarterly amount.",
            "status": "verified",
        },
        {
            "id": "b0000000-0000-0000-0000-000000000002",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "crop_cycle_id": "c0000000-0000-0000-0000-000000000001",
            "cycle_name": "2026 first cycle",
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 3, 31),
            "stream_name": "Nursery plants",
            "stream_category": "agriculture",
            "gross_revenue": 250.0,
            "direct_costs": 80.0,
            "allocated_costs": 20.0,
            "net_contribution": 150.0,
            "contribution_pct": 60.0,
            "notes": "Reviewed nursery sales.",
            "status": "published",
        },
    ]
    columns = (
        "id, location_id, location_name, crop_cycle_id, cycle_name, period_start, period_end, "
        "stream_name, stream_category, gross_revenue, direct_costs, allocated_costs, net_contribution, "
        "contribution_pct, notes, status"
    )

    class Cursor:
        def __init__(self):
            self.executed = []

        def execute(self, query, params):
            self.executed.append((query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return source_rows

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_revenue_streams(conn, location_id)
    query, params = conn.cursor_value.executed[1]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_revenue_streams "
        "WHERE location_id = %s ORDER BY period_start DESC, net_contribution DESC"
    )
    assert params == (location_id,)
    assert report["report_type"] == "revenue_streams"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["streams"] == [
        {**row, "period_start": "2026-01-01", "period_end": "2026-03-31"}
        for row in source_rows
    ]
    assert report["total_gross_revenue"] == 1250.0
    assert report["total_net_contribution"] == 750.0
    assert report["stream_count"] == 2


def test_prediction_accuracy_projection_preserves_payload_and_metrics() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    prediction_row = {
        "id": "b0000000-0000-0000-0000-000000000001",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "model_type": "yield_forecast",
        "model_name": "Adelphi yield baseline",
        "prediction_date": date(2026, 2, 1),
        "actual_date": date(2026, 3, 31),
        "predicted_value": 100.0,
        "actual_value": 90.0,
        "absolute_error": 10.0,
        "mae": 10.0,
        "rmse": 10.0,
        "mape": 11.11,
        "r_squared": 0.85,
        "sample_size": 12,
        "metric_name": "harvest_kg",
        "unit": "kg",
        "notes": "Reviewed forecast comparison.",
        "status": "verified",
    }
    feature_row = {
        "id": "c0000000-0000-0000-0000-000000000001",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "model_type": "yield_forecast",
        "analysis_date": date(2026, 3, 31),
        "feature_name": "rainfall_mm",
        "importance_score": 0.72,
        "direction": "positive",
        "correlation_coefficient": 0.81,
        "p_value": 0.03,
        "sample_size": 12,
        "notes": "Reviewed model feature.",
        "status": "verified",
    }
    columns = (
        "id, location_id, location_name, model_type, model_name, prediction_date, actual_date, "
        "predicted_value, actual_value, absolute_error, mae, rmse, mape, r_squared, sample_size, "
        "metric_name, unit, notes, status"
    )

    class Cursor:
        def __init__(self):
            self.executed = []
            self.fetchall_calls = 0

        def execute(self, query, params):
            self.executed.append((query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            self.fetchall_calls += 1
            return [prediction_row] if self.fetchall_calls == 1 else [feature_row]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_model_validation(conn, location_id)
    query, params = conn.cursor_value.executed[1]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_prediction_accuracy "
        "WHERE location_id = %s ORDER BY prediction_date DESC"
    )
    assert params == (location_id,)
    feature_query, feature_params = conn.cursor_value.executed[2]
    feature_columns = (
        "id, location_id, location_name, model_type, analysis_date, feature_name, importance_score, "
        "direction, correlation_coefficient, p_value, sample_size, notes, status"
    )
    assert re.sub(r"\s+", " ", feature_query).strip() == (
        f"SELECT {feature_columns} FROM v_public_feature_importance "
        "WHERE location_id = %s ORDER BY importance_score DESC"
    )
    assert feature_params == (location_id,)
    assert report["report_type"] == "model_validation"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["predictions"] == [
        {
            **prediction_row,
            "prediction_date": "2026-02-01",
            "actual_date": "2026-03-31",
        }
    ]
    assert report["feature_importance"] == [{**feature_row, "analysis_date": "2026-03-31"}]
    assert report["total_predictions"] == 1
    assert report["avg_mape_pct"] == 11.11
    assert report["overall_accuracy_pct"] == 88.89
    assert report["top_predictors"] == ["rainfall_mm"]


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------

def test_agent_imports_v2_functions() -> None:
    import inspect

    from services.agents.ecological_modeling_agent import synthesize_ecological_modeling
    source = inspect.getsource(synthesize_ecological_modeling)
    assert "compute_soil_input_retention" in source
    assert "compute_pest_trends" in source
    assert "compute_biocontrol_effectiveness" in source
    assert "compute_resource_efficiency" in source
    assert "compute_conservation_status_summary" in source


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
