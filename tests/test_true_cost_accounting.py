"""True Cost Accounting tests: schema, seeds, analytics across all 5 phases."""

from pathlib import Path

from services.analytics.true_cost_accounting import (
    compute_hidden_cost_summary,
    compute_human_capital_score,
    compute_natural_capital_valuation,
    compute_social_impact_valuation,
    compute_true_cost_statement,
)
from services.analytics.life_cycle import (
    compute_lca_summary,
    compute_product_carbon_footprint,
    compute_water_footprint,
)
from services.analytics.gri_reporting import (
    compute_gri_compliance_score,
    compute_materiality_matrix,
)
from services.analytics.systems_thinking import (
    compute_capital_flow_summary,
    compute_cross_capital_dependencies,
    compute_system_resilience,
)

SCHEMA = Path("schemas/postgres/062_true_cost_accounting.sql")
SEED = Path("schemas/seeds/062_true_cost_accounting.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in [
        "hidden_cost_observation", "natural_capital_valuation", "social_impact_valuation",
        "worker_safety_observation", "living_wage_benchmark", "lca_assessment",
        "gri_indicator", "materiality_assessment", "capital_flow_observation",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_hidden_costs", "v_public_natural_capital_valuation",
        "v_public_social_impact_valuation", "v_true_cost_statement",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (cost_category IN" in text
    assert "CHECK (capital_type IN" in text
    assert "CHECK (impact_category IN" in text
    assert "CHECK (incident_type IN" in text
    assert "CHECK (lifecycle_stage IN" in text
    assert "CHECK (from_capital IN" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_hidden_costs() -> None:
    text = SEED.read_text()
    assert "soil_degradation" in text
    assert "biodiversity_loss" in text
    assert "pesticide_exposure" in text
    assert "cultural_erosion" in text
    assert "replacement_cost" in text


def test_seed_has_natural_capital() -> None:
    text = SEED.read_text()
    assert "carbon" in text
    assert "biodiversity" in text
    assert "water" in text
    assert "soil" in text
    assert "pollination" in text
    assert "57.53" in text  # carbon quantity
    assert "25.00" in text  # carbon price


def test_seed_has_social_impact() -> None:
    text = SEED.read_text()
    assert "training" in text
    assert "governance" in text
    assert "cultural_preservation" in text
    assert "health" in text
    assert "community" in text


def test_seed_has_gri_indicators() -> None:
    text = SEED.read_text()
    assert "GRI 301-1" in text
    assert "GRI 302-1" in text
    assert "GRI 403-1" in text
    assert "GRI 404-1" in text


def test_seed_has_materiality() -> None:
    text = SEED.read_text()
    assert "Soil Health" in text
    assert "Fair Wages" in text
    assert "Organic Certification" in text


def test_seed_has_capital_flows() -> None:
    text = SEED.read_text()
    assert "financial" in text
    assert "natural" in text
    assert "human" in text
    assert "social" in text


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

class _MockCursor:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def execute(self, query, params=None):
        pass

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._single

    def close(self):
        pass


class _MockConn:
    def __init__(self, rows=None, single=None):
        self._rows = rows or []
        self._single = single

    def cursor(self, cursor_factory=None):
        return _MockCursor(self._rows, self._single)


def test_true_cost_statement() -> None:
    result = compute_true_cost_statement(_MockConn(single=(0,)), "test-location")
    assert "market_costs_usd" in result
    assert "hidden_costs_usd" in result
    assert "natural_capital_value_usd" in result
    assert "true_profit_usd" in result


def test_hidden_cost_summary() -> None:
    rows = [("environmental", "soil_degradation", 2, 450.0, 225.0)]

    class _HCCConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = rows
                elif self._calls == 2:
                    c._single = (2, 450.0)
            c.execute = execute
            return c

    result = compute_hidden_cost_summary(_HCCConn(), "test-location")
    assert result["total_hidden_costs_usd"] == 450.0
    assert result["total_observations"] == 2


def test_natural_capital_valuation() -> None:
    rows = [("carbon", 1, 57.53, 25.0, 1438.25), ("biodiversity", 1, 37.0, 35.0, 1295.0)]

    class _NCVConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = rows
                elif self._calls == 2:
                    c._single = (2733.25,)
            c.execute = execute
            return c

    result = compute_natural_capital_valuation(_NCVConn(), "test-location")
    assert result["total_natural_capital_value_usd"] == 2733.25
    assert len(result["by_type"]) == 2


def test_social_impact_valuation() -> None:
    rows = [("training", 1, 12, 2400.0, 2400.0)]

    class _SIVConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = rows
                elif self._calls == 2:
                    c._single = (2400.0, 12)
            c.execute = execute
            return c

    result = compute_social_impact_valuation(_SIVConn(), "test-location")
    assert result["total_social_impact_value_usd"] == 2400.0
    assert result["total_beneficiaries"] == 12


def test_product_carbon_footprint() -> None:
    rows = [
        ("cultivation", 150.0, 1.57, 25000.0, 50.0, 10.0),
        ("harvest", 30.0, 2.5, 500.0, 10.0, 50.0),
    ]
    result = compute_product_carbon_footprint(_MockConn(rows=rows), "test-location")
    assert result["total_carbon_kg_co2e"] == 180.0
    assert len(result["stages"]) == 2


def test_human_capital_score() -> None:
    class _HCConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = (4, 36, 64.0)  # training sessions, hours, improvement
                elif self._calls == 2:
                    c._single = (0, 0)  # safety serious, moderate
                elif self._calls == 3:
                    c._single = (2.50,)  # living wage
                elif self._calls == 4:
                    c._single = (5.0,)  # avg wage
                elif self._calls == 5:
                    c._single = (7.0,)  # wellbeing score
            c.execute = execute
            return c

    result = compute_human_capital_score(_HCConn(), "test-location")
    assert result["human_capital_score"] > 0
    assert result["training_sessions"] == 4


def test_water_footprint() -> None:
    rows = [("cultivation", 25000.0, 1.57)]

    class _WFConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = rows
                elif self._calls == 2:
                    c._rows = [("borehole", 50000.0, 85.0, 90.0)]
            c.execute = execute
            return c

    result = compute_water_footprint(_WFConn(), "test-location")
    assert result["total_water_footprint_liters"] == 25000.0


def test_lca_summary() -> None:
    rows = [
        ("input_production", 1, 500.0, 25.0, 0.0, 5.0, 0.0),
        ("cultivation", 1, 1.57, 150.0, 25000.0, 50.0, 10.0),
    ]
    result = compute_lca_summary(_MockConn(rows=rows), "test-location")
    assert result["total_assessments"] == 2
    assert result["total_carbon_kg_co2e"] == 175.0


def test_gri_compliance_score() -> None:
    indicators = [
        ("GRI 301-1", "GRI 301", "Materials", "expense_event", "amount", "quantitative"),
    ]
    result = compute_gri_compliance_score(_MockConn(rows=indicators), "test-location")
    assert result["total_indicators"] == 1
    assert "compliance_pct" in result


def test_materiality_matrix() -> None:
    rows = [
        ("farmers", "Soil Health", "environmental", 5, 5, "high", None),
        ("workers", "Fair Wages", "social", 5, 4, "high", None),
    ]
    result = compute_materiality_matrix(_MockConn(rows=rows), "test-location")
    assert result["total_topics"] == 2
    assert result["high_priority"] == 2


def test_capital_flow_summary() -> None:
    rows = [
        ("financial", "natural", "investment", 2, 2000.0),
        ("natural", "financial", "regeneration", 1, 1438.25),
    ]

    class _CFConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._rows = rows
                elif self._calls == 2:
                    c._rows = [("financial", 2000.0)]
                elif self._calls == 3:
                    c._rows = [("natural", 1438.25)]
            c.execute = execute
            return c

    result = compute_capital_flow_summary(_CFConn(), "test-location")
    assert result["total_flows"] == 2
    assert result["total_flow_value_usd"] == 3438.25


def test_cross_capital_dependencies() -> None:
    rows = [
        ("financial", "natural", "investment", 2000.0),
        ("natural", "financial", "regeneration", 1438.25),
    ]
    result = compute_cross_capital_dependencies(_MockConn(rows=rows), "test-location")
    assert result["cross_capital_value_usd"] == 3438.25
    assert result["interdependency_ratio"] > 0


def test_system_resilience() -> None:
    class _ResilienceConn:
        def __init__(self):
            self._calls = 0
        def cursor(self, cursor_factory=None):
            c = _MockCursor()
            def execute(query, params=None):
                self._calls += 1
                if self._calls == 1:
                    c._single = (3,)  # nc_types
                elif self._calls == 2:
                    c._single = (4,)  # training
                elif self._calls == 3:
                    c._single = (4,)  # staff
                elif self._calls == 4:
                    c._single = (3,)  # social types
                elif self._calls == 5:
                    c._single = (2,)  # governance
                elif self._calls == 6:
                    c._single = (3,)  # assets
                elif self._calls == 7:
                    c._single = (9200.0,)  # revenue
                elif self._calls == 8:
                    c._single = (5,)  # flow diversity
            c.execute = execute
            return c

    result = compute_system_resilience(_ResilienceConn(), "test-location")
    assert result["system_resilience_score"] > 0
    assert result["status"] in ("highly_resilient", "resilient", "moderately_resilient", "vulnerable", "critical")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_seed_has_hidden_costs()
    test_seed_has_natural_capital()
    test_seed_has_social_impact()
    test_seed_has_gri_indicators()
    test_seed_has_materiality()
    test_seed_has_capital_flows()
    test_true_cost_statement()
    test_hidden_cost_summary()
    test_natural_capital_valuation()
    test_social_impact_valuation()
    test_product_carbon_footprint()
    test_water_footprint()
    test_lca_summary()
    test_gri_compliance_score()
    test_materiality_matrix()
    test_capital_flow_summary()
    test_cross_capital_dependencies()
    test_system_resilience()
    print("All tests passed.")
