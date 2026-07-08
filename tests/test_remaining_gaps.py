"""Remaining gaps tests: leaf litter, livestock, decomposition, predation, token rewards, reward calibration."""

from pathlib import Path

from services.analytics.livestock_feed import (
    compute_feed_conversion_ratio,
    compute_feed_intake_summary,
)
from services.analytics.reward_calibration import (
    compute_reward_calibration,
    compute_reward_calibration_model,
    compute_reward_metric_correlation,
)
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_livestock_feed,
    generate_token_rewards,
    generate_reward_calibration,
)

SCHEMA = Path("schemas/postgres/050_remaining_gaps.sql")
SEED = Path("schemas/seeds/050_remaining_gaps.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in [
        "leaf_litter_measurement",
        "livestock_group",
        "feed_intake_record",
        "decomposition_measurement",
        "token_reward_distribution",
        "reward_calibration_model",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in [
        "v_public_leaf_litter_measurements",
        "v_public_livestock_feed_intake",
        "v_public_decomposition_measurements",
        "v_public_token_reward_distribution",
        "v_public_reward_calibration",
    ]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_has_constraints() -> None:
    text = SCHEMA.read_text()
    assert "chk_leaf_litter_decomposition" in text
    assert "chk_leaf_litter_status" in text
    assert "chk_livestock_status" in text
    assert "chk_feed_intake_status" in text
    assert "chk_decomp_status" in text
    assert "chk_token_reward_type" in text
    assert "chk_token_reward_distribution_status" in text
    assert "chk_reward_cal_type" in text
    assert "chk_reward_cal_status" in text
    assert "remaining-gaps-v1" in text


def test_schema_has_predation_rate_columns() -> None:
    text = SCHEMA.read_text()
    assert "predation_count" in text
    assert "predation_rate_per_day" in text


def test_schema_has_decomposition_auto_compute() -> None:
    text = SCHEMA.read_text()
    assert "GENERATED ALWAYS AS" in text
    assert "decomposition_rate_kg_per_day" in text
    assert "mass_loss_pct" in text
    assert "deployment_days" in text


def test_schema_has_token_reward_fields() -> None:
    text = SCHEMA.read_text()
    assert "recipient_address" in text
    assert "is_onchain" in text
    assert "tx_hash" in text
    assert "distribution_method" in text
    assert "linked_metric_key" in text
    assert "linked_metric_value" in text


def test_schema_has_reward_calibration_fields() -> None:
    text = SCHEMA.read_text()
    assert "calibration_score" in text
    assert "token_per_unit_output" in text
    assert "input_metrics" in text
    assert "output_weights" in text


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_metrics() -> None:
    text = SEED.read_text()
    for metric in [
        "leaf_litter_rate_kg_per_day",
        "feed_conversion_ratio",
        "decomposition_rate_pct_per_day",
        "predation_rate_per_day",
        "token_rewards_per_epoch",
        "reward_calibration_score",
    ]:
        assert metric in text, f"Missing metric: {metric}"


def test_seed_has_dashboards() -> None:
    text = SEED.read_text()
    assert "66_livestock_feed_intake" in text
    assert "67_token_reward_distribution" in text
    assert Path("dashboards/metabase/sql/66_livestock_feed_intake.sql").exists()
    assert Path("dashboards/metabase/sql/67_token_reward_distribution.sql").exists()
    assert Path("dashboards/metabase/66_livestock_feed_intake.json").exists()
    assert Path("dashboards/metabase/67_token_reward_distribution.json").exists()


def test_seed_has_adelphi_data() -> None:
    text = SEED.read_text()
    assert "LITTER-001" in text
    assert "Adelphi Free-Range Flock" in text
    assert "Maria Santos" in text
    assert "Carlos Rivera" in text
    assert "Adelphi Farm Collective" in text
    assert "Adelphi Q1 2026 Calibration" in text
    assert "Inga edulis" in text
    assert "Gallus gallus domesticus" in text
    assert "vKKN" in text
    assert "linear_weighted" in text


# ---------------------------------------------------------------------------
# Analytics tests
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


def test_feed_intake_summary_analytics() -> None:
    rows = [
        ("g1", "Adelphi Flock", "Gallus gallus domesticus", "RIR", 15, "mixed_feed", 2, 175.0, 87.5, 0.065, "2025-12-31", "2026-03-31"),
    ]
    result = compute_feed_intake_summary(_MockConn(rows), "test-location")
    assert result["total_groups"] == 1
    assert result["total_animals"] == 15
    assert result["total_feed_kg"] == 175.0


def test_feed_conversion_ratio_analytics() -> None:
    rows = [
        ("g1", "Adelphi Flock", "Gallus gallus domesticus", 15, 2.2, 175.0, 90, 0.065),
    ]
    result = compute_feed_conversion_ratio(_MockConn(rows), "test-location")
    assert len(result["groups"]) == 1
    assert result["groups"][0]["total_feed_kg"] == 175.0
    assert result["groups"][0]["feeding_days"] == 90


def test_reward_calibration_analytics() -> None:
    rows = [
        ("labor", "vKKN", 1, 150.0, 75.0, 150.0, "labor_hours", 160.0, "dao_backend", 0, 1),
        ("training", "vKKN", 1, 50.0, 25.0, 50.0, "training_improvement_pct", 55.77, "dao_backend", 0, 1),
    ]
    result = compute_reward_calibration(_MockConn(rows), "test-location")
    assert result["total_distributions"] == 2
    assert result["total_tokens"] == 200.0


def test_reward_calibration_model_analytics() -> None:
    rows = [
        ("Adelphi Q1", "linear_weighted", "2026-03-10", {}, {}, 0.7825, 400.0, 0.0333, "2026-Q1", 72.0),
    ]
    result = compute_reward_calibration_model(_MockConn(rows), "test-location")
    assert result["total_model_runs"] == 1
    assert result["latest_calibration_score"] == 0.7825


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------

def test_livestock_feed_report_registered() -> None:
    assert "livestock_feed" in REPORT_GENERATORS


def test_token_rewards_report_registered() -> None:
    assert "token_rewards" in REPORT_GENERATORS


def test_reward_calibration_report_registered() -> None:
    assert "reward_calibration" in REPORT_GENERATORS


def test_livestock_feed_report_public_safe() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            return {"name": "Kokonut Adelphi"}
        def fetchall(self):
            return []
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_livestock_feed(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "livestock_feed"
    assert "limitations" in report


def test_token_rewards_report_public_safe() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            if self.calls == 1:
                return {"name": "Kokonut Adelphi"}
            return None
        def fetchall(self):
            return []
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_token_rewards(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "token_rewards"
    assert "limitations" in report


def test_reward_calibration_report_public_safe() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params=None):
            self.calls += 1
        def fetchone(self):
            if self.calls == 1:
                return {"name": "Kokonut Adelphi"}
            return None
        def fetchall(self):
            return []
        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()

    report = generate_reward_calibration(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert report["report_type"] == "reward_calibration"
    assert "limitations" in report


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------

def test_agent_imports_new_analytics() -> None:
    import inspect
    from services.agents.ecological_modeling_agent import synthesize_ecological_modeling
    source = inspect.getsource(synthesize_ecological_modeling)
    assert "compute_feed_intake_summary" in source
    assert "compute_feed_conversion_ratio" in source
    assert "compute_reward_calibration" in source
    assert "compute_reward_calibration_model" in source


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_has_constraints()
    test_schema_has_predation_rate_columns()
    test_schema_has_decomposition_auto_compute()
    test_schema_has_token_reward_fields()
    test_schema_has_reward_calibration_fields()
    test_seed_has_metrics()
    test_seed_has_dashboards()
    test_seed_has_adelphi_data()
    test_feed_intake_summary_analytics()
    test_feed_conversion_ratio_analytics()
    test_reward_calibration_analytics()
    test_reward_calibration_model_analytics()
    test_livestock_feed_report_registered()
    test_token_rewards_report_registered()
    test_reward_calibration_report_registered()
    test_livestock_feed_report_public_safe()
    test_token_rewards_report_public_safe()
    test_reward_calibration_report_public_safe()
    test_agent_imports_new_analytics()
    print("All tests passed.")
