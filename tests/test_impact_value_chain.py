"""Impact Value Chain tests: schema, seeds, analytics, views."""

from pathlib import Path

from services.analytics.impact_value_chain import (
    compute_development_phase_progress,
    compute_framework_step_progress,
    compute_task_completion_rate,
    compute_weekly_plan_adherence,
)

SCHEMA = Path("schemas/postgres/061_impact_value_chain.sql")
SEED = Path("schemas/seeds/061_impact_value_chain.sql")


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_schema_defines_tables() -> None:
    text = SCHEMA.read_text()
    for table in ["department", "job_role", "farm_task", "weekly_plan", "development_phase", "framework_step"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in text, f"Missing table: {table}"


def test_schema_defines_views() -> None:
    text = SCHEMA.read_text()
    for view in ["v_public_farm_tasks", "v_public_weekly_plans", "v_public_development_phases", "v_public_framework_steps"]:
        assert f"CREATE OR REPLACE VIEW {view}" in text, f"Missing view: {view}"


def test_schema_extends_staff() -> None:
    text = SCHEMA.read_text()
    assert "ALTER TABLE staff ADD COLUMN IF NOT EXISTS job_role_id" in text
    assert "ALTER TABLE staff ADD COLUMN IF NOT EXISTS department_id" in text
    assert "ALTER TABLE staff ADD COLUMN IF NOT EXISTS hire_date" in text
    assert "ALTER TABLE staff ADD COLUMN IF NOT EXISTS employment_status" in text


def test_schema_has_check_constraints() -> None:
    text = SCHEMA.read_text()
    assert "CHECK (category IN ('planting'" in text
    assert "CHECK (priority IN ('low'" in text
    assert "CHECK (status IN ('pending'" in text
    assert "CHECK (step_type IN ('preparation'" in text


def test_schema_has_governed_columns() -> None:
    text = SCHEMA.read_text()
    for col in ["source_system", "source_id", "source_raw", "created_at", "updated_at"]:
        assert col in text, f"Missing governed column: {col}"


# ---------------------------------------------------------------------------
# Seed tests
# ---------------------------------------------------------------------------

def test_seed_has_departments() -> None:
    text = SEED.read_text()
    assert "Operations" in text
    assert "Ecology" in text
    assert "Finance" in text
    assert "Community" in text
    assert "Governance" in text


def test_seed_has_job_roles() -> None:
    text = SEED.read_text()
    assert "Farm Lead" in text
    assert "Community Operations Lead" in text
    assert "Nursery Steward" in text
    assert "MRV Field Coordinator" in text
    assert "Finance Manager" in text
    assert "Training Coordinator" in text
    assert "DAO Governance Lead" in text


def test_seed_has_farm_tasks() -> None:
    text = SEED.read_text()
    assert "Prepare nursery beds" in text
    assert "Conduct monthly biodiversity survey" in text
    assert "Apply compost" in text
    assert "community training workshop" in text
    assert "financial report" in text


def test_seed_has_weekly_plans() -> None:
    text = SEED.read_text()
    assert "Week 27" in text
    assert "Week 28" in text
    assert "week_start" in text
    assert "budget_forecast_usd" in text


def test_seed_has_development_phases() -> None:
    text = SEED.read_text()
    assert "Land Preparation" in text
    assert "Establishment" in text
    assert "Production" in text
    assert "phase_order" in text


def test_seed_has_framework_steps() -> None:
    text = SEED.read_text()
    assert "Baseline Assessment" in text
    assert "Soil Preparation" in text
    assert "Planting & Establishment" in text
    assert "Monitoring & Data Collection" in text
    assert "Verification & Attestation" in text
    assert "Publication & Reporting" in text
    assert "prerequisites" in text


def test_seed_links_staff() -> None:
    text = SEED.read_text()
    assert "job_role_id" in text
    assert "department_id" in text
    assert "hire_date" in text
    assert "employment_status" in text


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


def test_task_completion_analytics() -> None:
    single = (5, 3, 1, 1, 0, 2, 1, 2, 2)
    result = compute_task_completion_rate(_MockConn(single=single), "test-location")
    assert result["total_tasks"] == 5
    assert result["completed_tasks"] == 3
    assert result["completion_pct"] == 60.0
    assert result["on_time_pct"] > 0


def test_weekly_plan_adherence_analytics() -> None:
    rows = [
        ("plan1", "Week 27", "2026-06-29", "2026-07-05", 350.0, 320.0, "completed"),
        ("plan2", "Week 28", "2026-07-06", "2026-07-12", 450.0, None, "active"),
    ]
    result = compute_weekly_plan_adherence(_MockConn(rows=rows), "test-location")
    assert result["total_plans"] == 2
    assert result["completed_plans"] == 1
    assert result["active_plans"] == 1


def test_development_phase_progress_analytics() -> None:
    rows = [
        ("phase1", "Land Prep", "Description", 1, "2025-01-01", "2025-06-30", "completed"),
        ("phase2", "Establishment", "Description", 2, "2025-07-01", "2026-06-30", "active"),
        ("phase3", "Production", "Description", 3, "2026-07-01", "2028-06-30", "pending"),
    ]
    result = compute_development_phase_progress(_MockConn(rows=rows), "test-location")
    assert result["total_phases"] == 3
    assert result["completed_phases"] == 1
    assert result["current_phase"] == "Establishment"


def test_framework_step_progress_analytics() -> None:
    rows = [
        ("step1", "Baseline", "Desc", 1, "preparation", 30, [], "completed"),
        ("step2", "Soil Prep", "Desc", 2, "implementation", 60, ["step1"], "completed"),
        ("step3", "Planting", "Desc", 3, "implementation", 90, ["step2"], "in_progress"),
        ("step4", "Monitoring", "Desc", 4, "monitoring", 365, ["step3"], "pending"),
    ]
    result = compute_framework_step_progress(_MockConn(rows=rows), "test-location")
    assert result["total_steps"] == 4
    assert result["completed_steps"] == 2
    assert result["in_progress_steps"] == 1
    assert result["completion_pct"] == 50.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_schema_defines_tables()
    test_schema_defines_views()
    test_schema_extends_staff()
    test_schema_has_check_constraints()
    test_schema_has_governed_columns()
    test_seed_has_departments()
    test_seed_has_job_roles()
    test_seed_has_farm_tasks()
    test_seed_has_weekly_plans()
    test_seed_has_development_phases()
    test_seed_has_framework_steps()
    test_seed_links_staff()
    test_task_completion_analytics()
    test_weekly_plan_adherence_analytics()
    test_development_phase_progress_analytics()
    test_framework_step_progress_analytics()
    print("All tests passed.")
