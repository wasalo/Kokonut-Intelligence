"""Tests for data quality scoring and rule management.

Covers data_quality_rule CRUD, entity quality summaries, quality trends,
scoring logic, and input validation. Integration DB tests skip when the
data_quality_rule table is not available.
"""

import uuid

import pytest

from services.analytics.data_quality import (
    list_rules, create_rule, deactivate_rule,
    score_entity, entity_quality_summary, quality_trend,
)


def _db_available():
    """Check if the database is reachable and has the data_quality_rule table."""
    try:
        from services.analytics.data_quality import _conn
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'data_quality_rule'"
                )
                return cur.fetchone() is not None
    except Exception:
        return False


_db_skip = pytest.mark.skipif(not _db_available(), reason="data_quality_rule table not available")


# --- Rule CRUD Tests ---------------------------------------------------------

@_db_skip
class TestRuleCRUD:
    def test_list_rules_returns_seeded_data(self):
        rules = list_rules()
        assert len(rules) >= 13

    def test_list_rules_filter_by_entity_type(self):
        rules = list_rules(entity_type="farm_activity")
        assert len(rules) >= 1
        assert all(r["entity_type"] == "farm_activity" for r in rules)

    def test_list_rules_filter_by_dimension(self):
        rules = list_rules(dimension="completeness")
        assert len(rules) >= 1
        assert all(r["dimension"] == "completeness" for r in rules)

    def test_create_and_deactivate_rule(self):
        created = create_rule(
            entity_type="farm_activity",
            dimension="accuracy",
            rule_type="range",
            rule_config={"field": "yield_amount", "min": 0, "max": 10000},
            severity="warning",
        )
        assert created["entity_type"] == "farm_activity"
        assert created["dimension"] == "accuracy"
        rule_id = created["id"]

        found = list_rules()
        assert any(r["id"] == rule_id for r in found)

        assert deactivate_rule(rule_id)
        after = list_rules(active=True)
        assert not any(r["id"] == rule_id for r in after)

    def test_entity_quality_summary(self):
        summary = entity_quality_summary("farm_activity")
        assert isinstance(summary, dict)
        assert summary["entity_type"] == "farm_activity"
        assert "total_entities" in summary
        assert "avg_completeness" in summary
        assert "avg_accuracy" in summary
        assert "avg_timeliness" in summary
        assert "avg_consistency" in summary
        assert "avg_overall" in summary
        assert "distribution" in summary
        assert "excellent" in summary["distribution"]
        assert "good" in summary["distribution"]
        assert "fair" in summary["distribution"]
        assert "poor" in summary["distribution"]

    def test_quality_trend(self):
        trend = quality_trend("farm_activity", days=30)
        assert isinstance(trend, list)


# --- Pure Logic Tests --------------------------------------------------------

class TestScoreComputation:
    def test_overall_score_is_average_of_four_dimensions(self):
        rule_results = [
            {"dimension": "completeness", "passed": True},
            {"dimension": "completeness", "passed": False},
            {"dimension": "accuracy", "passed": True},
            {"dimension": "accuracy", "passed": True},
            {"dimension": "timeliness", "passed": True},
            {"dimension": "timeliness", "passed": True},
            {"dimension": "consistency", "passed": True},
            {"dimension": "consistency", "passed": False},
        ]
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=rule_results,
        )
        assert result["completeness_pct"] == 50.0
        assert result["accuracy_pct"] == 100.0
        assert result["timeliness_pct"] == 100.0
        assert result["consistency_pct"] == 50.0
        expected_overall = round((50.0 + 100.0 + 100.0 + 50.0) / 4, 2)
        assert result["overall_score"] == expected_overall

    def test_empty_results_default_to_100(self):
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=[],
        )
        assert result["overall_score"] == 100.0


class TestScoringDimensions:
    def test_each_dimension_contributes_to_score(self):
        """A result with only one dimension failing should drag that dimension's pct to 0."""
        rule_results = [
            {"dimension": "completeness", "passed": False},
            {"dimension": "accuracy", "passed": True},
            {"dimension": "timeliness", "passed": True},
            {"dimension": "consistency", "passed": True},
        ]
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=rule_results,
        )
        assert result["completeness_pct"] == 0.0
        assert result["accuracy_pct"] == 100.0
        expected = round((0 + 100 + 100 + 100) / 4, 2)
        assert result["overall_score"] == expected

    def test_unknown_dimension_gracefully_skipped(self):
        """An unknown dimension in rule_results should not crash scoring."""
        rule_results = [
            {"dimension": "bogus", "passed": True},
            {"dimension": "completeness", "passed": True},
        ]
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=rule_results,
        )
        assert result["overall_score"] == 100.0


class TestValidation:
    def test_score_entity_with_missing_dimension_key(self):
        """rule_result with no 'dimension' key defaults to completeness."""
        rule_results = [{"passed": True}]
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=rule_results,
        )
        assert result["completeness_pct"] == 100.0

    def test_score_entity_with_missing_passed_key(self):
        """rule_result with no 'passed' key is treated as failure."""
        rule_results = [{"dimension": "accuracy"}]
        result = score_entity(
            entity_type="farm_activity",
            entity_id=str(uuid.uuid4()),
            rule_results=rule_results,
        )
        assert result["accuracy_pct"] == 0.0
