"""Ecological modeling hub tests."""

import re
from pathlib import Path

from services.analytics.ecological_modeling import (
    compute_energy_flow_efficiency,
    compute_population_stability,
    compute_trophic_balance,
    trophic_pyramid_summary,
)
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_ecological_modeling,
    generate_trophic_pyramid,
)

SCHEMA = Path("schemas/postgres/046_ecological_modeling.sql")
SEED = Path("schemas/seeds/046_ecological_modeling.sql")


def test_ecological_modeling_schema_defines_tables_and_views() -> None:
    text = SCHEMA.read_text()
    for table in [
        "ecological_interaction",
        "ecological_model_run",
        "energy_flow_measurement",
        "population_dynamics_record",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text
    for view in [
        "v_public_ecological_interaction_summary",
        "v_public_energy_flow_summary",
        "v_public_population_dynamics_summary",
        "v_public_ecological_model_summary",
        "v_trophic_balance",
        "v_energy_flow_efficiency",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text
    assert "trophic_level" in text
    assert "population_density_per_m2" in text
    assert "strata_layer" in text
    assert "ecological-modeling-v1" in text


def test_ecological_modeling_schema_has_constraints() -> None:
    text = SCHEMA.read_text()
    assert "chk_eco_interaction_type" in text
    assert "chk_eco_interaction_trophic" in text
    assert "chk_eco_interaction_status" in text
    assert "chk_eco_model_type" in text
    assert "chk_eco_model_status" in text
    assert "chk_energy_flow_trophic" in text
    assert "chk_energy_flow_status" in text
    assert "chk_pop_dynamics_trophic" in text
    assert "chk_pop_dynamics_status" in text
    assert "chk_species_trophic_level" in text
    assert "chk_farm_zone_strata" in text
    assert "mutualism" in text
    assert "predation" in text
    assert "facilitation" in text
    assert "emergent" in text
    assert "canopy" in text


def test_ecological_modeling_seed_has_metrics_and_dashboards() -> None:
    text = SEED.read_text()
    for metric in [
        "ecological_interaction_count",
        "trophic_balance_index",
        "energy_flow_efficiency_pct",
        "population_stability_index",
    ]:
        assert metric in text
    for sql in [
        "62_ecological_interactions.sql",
        "63_trophic_pyramid.sql",
    ]:
        assert Path("dashboards/metabase/sql").joinpath(sql).exists()
    for dashboard in [
        "62_ecological_interactions.json",
        "63_trophic_pyramid.json",
    ]:
        assert Path("dashboards/metabase").joinpath(dashboard).exists()


def test_ecological_modeling_seed_has_adelphi_examples() -> None:
    text = SEED.read_text()
    assert "Inga edulis" in text
    assert "Passiflora edulis" in text
    assert "Apis mellifera" in text
    assert "Passer domesticus" in text
    assert "Gallus gallus domesticus" in text
    assert "facilitation" in text
    assert "mutualism" in text
    assert "predation" in text
    assert "trophic_level" in text
    assert "strata_layer" in text
    assert "Adelphi Nutrient Cycling Model" in text
    assert "nutrient_cycling" in text
    assert "projected_soil_nitrogen_3_seasons_ppm" in text


def test_ecological_modeling_report_generators_registered() -> None:
    for report_type in [
        "ecological_modeling",
        "trophic_pyramid",
    ]:
        assert report_type in REPORT_GENERATORS, f"Missing report type: {report_type}"


def test_ecological_modeling_report_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "species_a_name": "Inga edulis",
                    "species_a_trophic": "producer",
                    "species_b_name": "Passiflora edulis",
                    "species_b_trophic": "producer",
                    "interaction_type": "facilitation",
                    "interaction_strength": 0.80,
                    "zone_name": "Syntropic Plot",
                    "location_name": "Kokonut Adelphi",
                }]
            if self.calls == 2:
                return [{
                    "model_name": "Adelphi Nutrient Cycling Model",
                    "model_type": "nutrient_cycling",
                    "run_date": "2026-03-10",
                    "confidence_level": 75.0,
                    "input_parameters": {},
                    "output_predictions": {},
                    "zone_name": "Syntropic Plot",
                    "location_name": "Kokonut Adelphi",
                }]
            if self.calls == 3:
                return [{
                    "species_name": "Apis mellifera",
                    "species_common_name": "Honey bee",
                    "trophic_level": "primary_consumer",
                    "record_date": "2026-03-10",
                    "population_count": 176,
                    "population_density_per_m2": 0.70,
                    "growth_rate_estimate": 0.08,
                    "method": "visual",
                    "plot_name": "Plot A",
                    "location_name": "Kokonut Adelphi",
                }]
            if self.calls == 4:
                return [{
                    "from_trophic_level": "producer",
                    "to_trophic_level": "primary_consumer",
                    "biomass_transferred_kg": 25.00,
                    "conversion_efficiency_pct": 1.67,
                    "measurement_method": "estimation",
                    "zone_name": "Syntropic Plot",
                    "location_name": "Kokonut Adelphi",
                }]
            return []

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_ecological_modeling(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "ecological_modeling"
    assert report["interaction_count"] == 1
    assert "ecological" in report["limitations"][0].lower() or "advisory" in report["limitations"][0].lower()


def test_ecological_modeling_explicit_public_view_projections_preserve_payload() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    expected_columns = {
        "v_public_ecological_interaction_summary": [
            "id", "location_id", "location_name", "zone_id", "zone_name",
            "species_a_name", "species_a_common", "species_a_trophic",
            "species_b_name", "species_b_common", "species_b_trophic",
            "interaction_type", "interaction_strength", "description", "notes",
            "evidence_adequate", "status",
        ],
        "v_public_ecological_model_summary": [
            "id", "location_id", "location_name", "zone_id", "zone_name",
            "model_name", "model_type", "run_date", "confidence_level",
            "input_parameters", "output_predictions", "notes", "status",
        ],
        "v_public_population_dynamics_summary": [
            "id", "location_id", "location_name", "plot_id", "plot_name",
            "species_name", "species_common_name", "trophic_level", "record_date",
            "population_count", "population_density_per_m2", "growth_rate_estimate",
            "method", "notes", "status",
        ],
        "v_public_energy_flow_summary": [
            "id", "location_id", "location_name", "zone_id", "zone_name",
            "measurement_date", "from_trophic_level", "to_trophic_level",
            "biomass_transferred_kg", "conversion_efficiency_pct",
            "measurement_method", "period_start", "period_end", "notes", "status",
        ],
        "v_public_soil_input_retention": [
            "id", "location_id", "location_name", "plot_id", "plot_name",
            "application_date", "input_type", "input_name", "quantity_kg",
            "application_method", "depth_cm", "decomposition_status", "residual_pct",
            "residual_measurement_date", "notes", "status",
        ],
    }

    def make_row(columns, **overrides):
        row = {column: f"{column}-value" for column in columns}
        row.update(overrides)
        return row

    interaction_columns = expected_columns["v_public_ecological_interaction_summary"]
    interactions = [
        make_row(interaction_columns, interaction_type="mutualism", interaction_strength=0.8),
        make_row(interaction_columns, interaction_type="predation", interaction_strength=0.4),
    ]
    model_columns = expected_columns["v_public_ecological_model_summary"]
    models = [
        make_row(
            model_columns,
            model_name="Adelphi Nutrient Cycling Model",
            model_type="nutrient_cycling",
            run_date="2026-02-15",
            confidence_level=75.0,
            input_parameters={"rainfall_mm": 120},
            output_predictions={"soil_n_ppm": 42},
        )
    ]
    population_columns = expected_columns["v_public_population_dynamics_summary"]
    populations = [
        make_row(
            population_columns,
            species_name="Apis mellifera",
            species_common_name="Honey bee",
            trophic_level="primary_consumer",
            record_date="2026-02-20",
            population_count=176,
            population_density_per_m2=0.7,
            growth_rate_estimate=0.08,
            method="visual",
        )
    ]
    energy_columns = expected_columns["v_public_energy_flow_summary"]
    energy_flows = [
        make_row(energy_columns, biomass_transferred_kg=25.0, conversion_efficiency_pct=1.67)
    ]
    soil_columns = expected_columns["v_public_soil_input_retention"]
    soil_inputs = [make_row(soil_columns, residual_pct=62.75)]
    rows_by_view = {
        "v_public_ecological_interaction_summary": interactions,
        "v_public_ecological_model_summary": models,
        "v_public_population_dynamics_summary": populations,
        "v_public_energy_flow_summary": energy_flows,
        "v_public_soil_input_retention": soil_inputs,
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, sql, params=None):
            self.current_query = " ".join(sql.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            for view_name, rows in rows_by_view.items():
                if view_name in self.current_query:
                    return rows
            return []

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_ecological_modeling(
        conn, location_id, period_start="2026-01-01", period_end="2026-03-31"
    )

    calls_by_view = {
        view_name: next(call for call in conn.cursor_value.calls if view_name in call[0])
        for view_name in expected_columns
    }
    for view_name, columns in expected_columns.items():
        sql, params = calls_by_view[view_name]
        projection = re.search(r"SELECT (.*?) FROM " + re.escape(view_name), sql)
        assert projection is not None
        assert [column.strip() for column in projection.group(1).split(",")] == columns
        assert "WHERE location_id = %s" in sql
        if view_name == "v_public_ecological_interaction_summary":
            assert "ORDER BY interaction_strength DESC" in sql
            assert params == (location_id,)
        else:
            date_column = {
                "v_public_ecological_model_summary": "run_date",
                "v_public_population_dynamics_summary": "record_date",
                "v_public_energy_flow_summary": "measurement_date",
                "v_public_soil_input_retention": "application_date",
            }[view_name]
            assert f"{date_column} >= %s::date" in sql
            assert f"{date_column} <= %s::date" in sql
            expected_order = {
                "v_public_ecological_model_summary": "ORDER BY run_date DESC",
                "v_public_population_dynamics_summary": "ORDER BY species_name, record_date",
                "v_public_energy_flow_summary": "ORDER BY measurement_date DESC",
                "v_public_soil_input_retention": "ORDER BY application_date DESC",
            }[view_name]
            assert expected_order in sql
            assert params == (location_id, "2026-01-01", "2026-01-01", "2026-03-31", "2026-03-31")

    assert report["location_name"] == "Kokonut Adelphi"
    assert report["interactions"] == interactions
    assert report["model_runs"] == models
    assert report["population_records"] == populations
    assert report["energy_flows"] == energy_flows
    assert report["soil_inputs"] == soil_inputs
    assert report["interaction_count"] == 2
    assert report["mutualism_count"] == 1
    assert report["predation_count"] == 1
    assert report["trophic_balance_index"] == 0.5
    assert report["soil_input_count"] == 1
    assert report["avg_residual_pct"] == 62.75


def test_trophic_pyramid_report_public_safe() -> None:
    class Cursor:
        calls = 0

        def execute(self, query, params=None):
            self.calls += 1

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            if self.calls == 1:
                return [{
                    "from_trophic_level": "producer",
                    "to_trophic_level": "decomposer",
                    "total_biomass_kg": 180.00,
                    "avg_efficiency_pct": 12.00,
                    "measurement_count": 1,
                    "location_name": "Kokonut Adelphi",
                }]
            if self.calls == 2:
                return [{
                    "trophic_level": "producer",
                    "interaction_count": 3,
                    "avg_strength": 0.70,
                }]
            if self.calls == 3:
                return [{
                    "trophic_level": "primary_consumer",
                    "species_count": 2,
                    "total_individuals": 176,
                }]
            return []

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_trophic_pyramid(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "trophic_pyramid"
    assert report["total_energy_transfers"] == 1
    assert "trophic" in report["limitations"][0].lower() or "energy" in report["limitations"][0].lower()


def test_trophic_balance_analytics() -> None:
    class Cursor:
        def __init__(self):
            self._calls = 0

        def execute(self, query, params=None):
            self._calls += 1

        def fetchall(self):
            return [("mutualism", 3, 0.70), ("predation", 1, 0.30)]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = compute_trophic_balance(Conn(), "test-location")
    assert result["total_interactions"] == 4
    assert result["mutualism_count"] == 3
    assert result["predation_count"] == 1
    # trophic_balance = mutualism / (mutualism + competition) = 3 / (3 + 0) = 1.0
    assert result["trophic_balance_index"] == 1.0


def test_energy_flow_efficiency_analytics() -> None:
    class Cursor:
        def __init__(self):
            self._calls = 0

        def execute(self, query, params=None):
            self._calls += 1

        def fetchall(self):
            return [("producer", "decomposer", 180.0, 12.0, 1)]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = compute_energy_flow_efficiency(Conn(), "test-location")
    assert result["total_transfers"] == 1
    assert result["total_biomass_kg"] == 180.0
    assert result["overall_efficiency_pct"] == 12.0


def test_population_stability_analytics() -> None:
    class Cursor:
        def __init__(self):
            self._calls = 0

        def execute(self, query, params=None):
            self._calls += 1

        def fetchall(self):
            return [("Apis mellifera", "Honey bee", "primary_consumer", 2, 148.0, 39.6, 120, 176, "2025-10-10", "2026-03-10")]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = compute_population_stability(Conn(), "test-location")
    assert result["species_with_sufficient_data"] == 1
    assert 0 <= result["population_stability_index"] <= 1


def test_trophic_pyramid_analytics() -> None:
    class Cursor:
        def __init__(self):
            self._calls = 0

        def execute(self, query, params=None):
            self._calls += 1

        def fetchall(self):
            return [("producer", 5, 1500), ("primary_consumer", 2, 296)]

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    result = trophic_pyramid_summary(Conn(), "test-location")
    assert result["total_levels"] == 2
    assert result["trophic_levels"][0]["trophic_level"] == "producer"
    assert result["trophic_levels"][1]["trophic_level"] == "primary_consumer"


if __name__ == "__main__":
    test_ecological_modeling_schema_defines_tables_and_views()
    test_ecological_modeling_schema_has_constraints()
    test_ecological_modeling_seed_has_metrics_and_dashboards()
    test_ecological_modeling_seed_has_adelphi_examples()
    test_ecological_modeling_report_generators_registered()
    test_ecological_modeling_report_public_safe()
    test_trophic_pyramid_report_public_safe()
    test_trophic_balance_analytics()
    test_energy_flow_efficiency_analytics()
    test_population_stability_analytics()
    test_trophic_pyramid_analytics()
    print("All tests passed.")
