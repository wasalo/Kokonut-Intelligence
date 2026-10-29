import re

import pytest

from services.export.reports.wellbeing import generate_ebf_scorecard


@pytest.mark.parametrize("location_id", [None, ""])
def test_ebf_scorecard_rejects_missing_location_before_database_access(location_id):
    class NoDatabase:
        def cursor(self, **_kwargs):
            raise AssertionError("database must not open without a location scope")

    with pytest.raises(ValueError, match="ebf_scorecard requires an explicit location_id"):
        generate_ebf_scorecard(NoDatabase(), location_id)


def test_ebf_scorecard_uses_exact_public_projections_and_preserves_scope_and_payload():
    location_id = "a0000000-0000-0000-0000-000000000001"
    summary_columns = [
        "scorecard_id",
        "location_id",
        "location_name",
        "farm_id",
        "farm_name",
        "period_start",
        "period_end",
        "overall_score",
        "overall_confidence",
        "rubric_version",
        "evidence_maturity_level",
        "evidence_maturity_label",
        "pillar_count",
        "public_safe_pillar_count",
        "min_pillar_evidence_maturity",
        "max_pillar_evidence_maturity",
        "caveat",
    ]
    pillar_columns = [
        "pillar_key",
        "pillar_name",
        "normalized_score",
        "confidence_level",
        "trend_direction",
        "score_evidence_maturity_label",
        "evidence_summary",
        "uncertainty_notes",
    ]
    summary = {
        "scorecard_id": "00000000-0000-4000-8000-000000000001",
        "location_id": location_id,
        "location_name": "Kokonut Adelphi",
        "farm_id": "00000000-0000-4000-8000-000000000002",
        "farm_name": "Adelphi",
        "period_start": "2026-07-01",
        "period_end": "2026-09-30",
        "overall_score": 0.76,
        "overall_confidence": 0.82,
        "rubric_version": "ebf-v2",
        "evidence_maturity_level": 5,
        "evidence_maturity_label": "Verified",
        "pillar_count": 7,
        "public_safe_pillar_count": 7,
        "min_pillar_evidence_maturity": 4,
        "max_pillar_evidence_maturity": 6,
        "caveat": "Use for learning, not farm ranking.",
    }
    pillars = [
        {
            "pillar_key": "community_wellbeing",
            "pillar_name": "Community wellbeing",
            "normalized_score": 0.8,
            "confidence_level": 0.9,
            "trend_direction": "improving",
            "score_evidence_maturity_label": "Verified",
            "evidence_summary": "Reviewed community measures.",
            "uncertainty_notes": "Small sample.",
        }
    ]

    class Cursor:
        def __init__(self):
            self.query = ""
            self.calls = []

        def execute(self, query, params=None):
            self.query = " ".join(query.split())
            self.calls.append((self.query, params))

        def fetchone(self):
            return summary

        def fetchall(self):
            return pillars

        def close(self):
            pass

    class Conn:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    conn = Conn()
    report = generate_ebf_scorecard(
        conn, location_id, period_start="2026-07-01", period_end="2026-09-30"
    )

    summary_sql, summary_params = conn.cursor_value.calls[0]
    summary_projection = re.search(
        r"SELECT (.*?) FROM v_public_ebf_scorecard_summary", summary_sql
    )
    assert summary_projection is not None
    assert [column.strip() for column in summary_projection.group(1).split(",")] == summary_columns
    assert "WHERE location_id = %s" in summary_sql
    assert "period_start >= %s::date" in summary_sql
    assert "period_end <= %s::date" in summary_sql
    assert "ORDER BY period_end DESC, scorecard_id LIMIT 1" in summary_sql
    assert summary_params == (location_id, "2026-07-01", "2026-07-01", "2026-09-30", "2026-09-30")

    pillar_sql, pillar_params = conn.cursor_value.calls[1]
    pillar_projection = re.search(r"SELECT (.*?) FROM v_public_ebf_scorecard", pillar_sql)
    assert pillar_projection is not None
    assert [column.strip() for column in pillar_projection.group(1).split(",")] == pillar_columns
    assert "WHERE scorecard_id = %s ORDER BY pillar_key" in pillar_sql
    assert pillar_params == (summary["scorecard_id"],)
    assert report["location_id"] == location_id
    assert report["summary"] == summary
    assert report["pillars"] == pillars
