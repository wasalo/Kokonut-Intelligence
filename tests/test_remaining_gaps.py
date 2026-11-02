"""Remaining gaps tests: leaf litter, livestock, decomposition, predation, token rewards, reward calibration."""

import re
from datetime import date
from pathlib import Path
from unittest.mock import patch

from services.analytics.livestock_feed import (
    compute_feed_conversion_ratio,
    compute_feed_intake_summary,
)
from services.analytics.reward_calibration import (
    compute_reward_calibration,
    compute_reward_calibration_model,
)
from services.export.report_generator import (
    REPORT_GENERATORS,
    generate_livestock_feed,
    generate_reward_calibration,
    generate_token_rewards,
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


def test_livestock_feed_projection_preserves_full_payload_and_totals() -> None:
    location_id = "a0000000-0000-0000-0000-000000000001"
    source_rows = [
        {
            "id": "b0000000-0000-0000-0000-000000000001",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "livestock_group_id": "c0000000-0000-0000-0000-000000000001",
            "group_name": "Dairy goats",
            "livestock_species": "goat",
            "livestock_breed": "local crossbreed",
            "animal_count": 12,
            "record_date": date(2026, 3, 31),
            "feed_type": "forage",
            "feed_name": "cut grass",
            "quantity_kg": 24.0,
            "per_animal_kg": 2.0,
            "method": "weighed",
            "temperature_c": 25.5,
            "notes": "Morning feed record.",
            "status": "verified",
        },
        {
            "id": "b0000000-0000-0000-0000-000000000002",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "livestock_group_id": "c0000000-0000-0000-0000-000000000001",
            "group_name": "Dairy goats",
            "livestock_species": "goat",
            "livestock_breed": "local crossbreed",
            "animal_count": 12,
            "record_date": date(2026, 3, 30),
            "feed_type": "supplement",
            "feed_name": "mineral mix",
            "quantity_kg": 2.5,
            "per_animal_kg": 0.2083,
            "method": "measured",
            "temperature_c": 24.0,
            "notes": "Mineral supplement record.",
            "status": "published",
        },
    ]
    group_rows = [{
        "group_name": "Dairy goats",
        "species": "goat",
        "breed": "local crossbreed",
        "animal_count": 12,
        "feed_type": "mixed forage",
        "status": "active",
    }]
    columns = (
        "id, location_id, location_name, livestock_group_id, group_name, livestock_species, "
        "livestock_breed, animal_count, record_date, feed_type, feed_name, quantity_kg, "
        "per_animal_kg, method, temperature_c, notes, status"
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
            return source_rows if self.fetchall_calls == 1 else group_rows

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_livestock_feed(conn, location_id)
    query, params = conn.cursor_value.executed[1]

    assert re.sub(r"\s+", " ", query).strip() == (
        f"SELECT {columns} FROM v_public_livestock_feed_intake "
        "WHERE location_id = %s ORDER BY record_date DESC"
    )
    assert params == (location_id,)
    assert report["report_type"] == "livestock_feed"
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["feed_records"] == [
        {**row, "record_date": row["record_date"].isoformat()}
        for row in source_rows
    ]
    assert report["livestock_groups"] == group_rows
    assert report["total_groups"] == 1
    assert report["total_animals"] == 12
    assert report["total_feed_kg"] == 26.5


def test_token_rewards_report_public_safe() -> None:
    distribution_columns = [
        "id",
        "location_id",
        "location_name",
        "recipient_name",
        "reward_type",
        "token_type",
        "token_amount",
        "usd_value",
        "distribution_date",
        "epoch",
        "linked_metric_key",
        "linked_metric_value",
        "is_onchain",
        "distribution_method",
        "notes",
        "status",
    ]
    calibration_columns = [
        "id",
        "location_id",
        "location_name",
        "model_name",
        "model_type",
        "run_date",
        "input_metrics",
        "output_weights",
        "calibration_score",
        "total_tokens_distributed",
        "token_per_unit_output",
        "epoch",
        "confidence_level",
        "notes",
        "status",
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    distributions = [
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "recipient_name": "Community fund",
            "reward_type": "impact",
            "token_type": "KOKO",
            "token_amount": 12.5,
            "usd_value": 25.0,
            "distribution_date": date(2026, 10, 1),
            "epoch": 4,
            "linked_metric_key": "soil_health",
            "linked_metric_value": 0.8,
            "is_onchain": True,
            "distribution_method": "attestation",
            "notes": "Reviewed reward.",
            "status": "verified",
        },
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "recipient_name": "Training guild",
            "reward_type": "participation",
            "token_type": "KOKO",
            "token_amount": 7.5,
            "usd_value": 15.0,
            "distribution_date": date(2026, 9, 1),
            "epoch": 3,
            "linked_metric_key": "training_hours",
            "linked_metric_value": 6.0,
            "is_onchain": False,
            "distribution_method": "offchain_credit",
            "notes": "Reviewed participation reward.",
            "status": "published",
        },
    ]
    calibration = {
        "id": "00000000-0000-4000-8000-000000000003",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "model_name": "Impact model",
        "model_type": "linear",
        "run_date": date(2026, 10, 2),
        "input_metrics": {"soil_health": 0.8},
        "output_weights": {"soil_health": 1.25},
        "calibration_score": 0.92,
        "total_tokens_distributed": 20.0,
        "token_per_unit_output": 1.0,
        "epoch": 4,
        "confidence_level": 0.9,
        "notes": "Current reviewed calibration.",
        "status": "verified",
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            if len(self.calls) == 1:
                return {"name": "Kokonut Adelphi"}
            return calibration

        def fetchall(self):
            return distributions

        def close(self):
            pass

    class Conn:
        def cursor(self, cursor_factory=None):
            self.cursor_value = Cursor()
            return self.cursor_value

    conn = Conn()
    report = generate_token_rewards(conn, location_id)

    distribution_sql, distribution_params = conn.cursor_value.calls[1]
    distribution_projection = re.search(
        r"SELECT (.*?) FROM v_public_token_reward_distribution", distribution_sql
    )
    assert distribution_projection is not None
    assert [column.strip() for column in distribution_projection.group(1).split(",")] == distribution_columns
    assert "WHERE location_id = %s ORDER BY distribution_date DESC" in distribution_sql
    assert distribution_params == (location_id,)

    calibration_sql, calibration_params = conn.cursor_value.calls[2]
    calibration_projection = re.search(
        r"SELECT (.*?) FROM v_public_reward_calibration", calibration_sql
    )
    assert calibration_projection is not None
    assert [column.strip() for column in calibration_projection.group(1).split(",")] == calibration_columns
    assert "WHERE location_id = %s ORDER BY run_date DESC LIMIT 1" in calibration_sql
    assert calibration_params == (location_id,)

    assert report["report_type"] == "token_rewards"
    assert report["location_id"] == location_id
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["distributions"] == [
        {**distributions[0], "distribution_date": "2026-10-01"},
        {**distributions[1], "distribution_date": "2026-09-01"},
    ]
    assert report["latest_calibration"] == calibration
    assert report["total_distributions"] == 2
    assert report["total_tokens"] == 20.0
    assert report["total_usd"] == 40.0
    assert report["onchain_count"] == 1
    assert report["offchain_count"] == 1
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


def test_reward_calibration_uses_exact_public_projection_and_preserves_scope_payload() -> None:
    columns = [
        "id",
        "location_id",
        "location_name",
        "model_name",
        "model_type",
        "run_date",
        "input_metrics",
        "output_weights",
        "calibration_score",
        "total_tokens_distributed",
        "token_per_unit_output",
        "epoch",
        "confidence_level",
        "notes",
        "status",
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    model = {
        "id": "00000000-0000-4000-8000-000000000001",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "model_name": "Impact model",
        "model_type": "linear",
        "run_date": date(2026, 10, 2),
        "input_metrics": {"soil_health": 0.8},
        "output_weights": {"soil_health": 1.25},
        "calibration_score": 0.92,
        "total_tokens_distributed": 20.0,
        "token_per_unit_output": 1.0,
        "epoch": 4,
        "confidence_level": 0.9,
        "notes": "Current reviewed calibration.",
        "status": "verified",
    }
    metric_link = {
        "reward_type": "impact",
        "linked_metric_key": "soil_health",
        "avg_metric": 0.8,
        "avg_tokens": 20.0,
        "count": 3,
    }

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"} if "FROM location" in self.current_query else None

        def fetchall(self):
            if "v_public_reward_calibration" in self.current_query:
                return [model]
            return [metric_link]

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    with patch(
        "services.analytics.reward_calibration.detect_overjustification_risk",
        return_value={"risk_level": "low", "sample_count": 3},
    ):
        report = generate_reward_calibration(conn, location_id)

    query, params = conn.cursor_value.calls[1]
    projection = re.search(r"SELECT (.*?) FROM v_public_reward_calibration", query)
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert "WHERE location_id = %s ORDER BY run_date DESC" in query
    assert params == (location_id,)
    assert conn.cursor_value.calls[2][1] == (location_id,)
    assert report["report_type"] == "reward_calibration"
    assert report["location_id"] == location_id
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["calibration_models"] == [{**model, "run_date": "2026-10-02"}]
    assert report["metric_links"] == [metric_link]
    assert report["latest_calibration_score"] == 0.92
    assert report["latest_model_name"] == "Impact model"
    assert report["overjustification_risk"] == {"risk_level": "low", "sample_count": 3}


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
    test_reward_calibration_uses_exact_public_projection_and_preserves_scope_payload()
    test_agent_imports_new_analytics()
    print("All tests passed.")
