"""Direct-call scope validation for operational reports."""

import re

import pytest

from services.export.reports import operations


class NoDatabase:
    def cursor(self, **_kwargs):
        raise AssertionError("database access must not occur for invalid location scope")


@pytest.mark.parametrize(
    ("generator", "report_type"),
    [
        (operations.generate_pest_management, "pest_management"),
        (operations.generate_training_impact, "training_impact"),
        (operations.generate_revenue_streams, "revenue_streams"),
        (operations.generate_model_validation, "model_validation"),
        (operations.generate_livestock_feed, "livestock_feed"),
        (operations.generate_token_rewards, "token_rewards"),
        (operations.generate_reward_calibration, "reward_calibration"),
        (operations.generate_organic_certification_readiness, "organic_certification_readiness"),
        (operations.generate_organic_transition_progress, "organic_transition_progress"),
        (operations.generate_organic_input_audit, "organic_input_audit"),
        (operations.generate_statement_of_work, "statement_of_work"),
    ],
)
@pytest.mark.parametrize(
    "location_id",
    [
        None,
        "",
        "all",
        "not-a-uuid",
        "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
    ],
)
def test_operational_report_rejects_invalid_location_before_database_access(
    generator, report_type, location_id
):
    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        generator(NoDatabase(), location_id)


def test_training_impact_uses_exact_public_projection_and_preserves_scope_payload():
    columns = [
        "id",
        "location_id",
        "location_name",
        "participant_name",
        "participant_role",
        "session_date",
        "session_topic",
        "session_type",
        "duration_hours",
        "pre_score",
        "post_score",
        "improvement_pct",
        "trainer",
        "notes",
        "status",
    ]
    location_id = "a0000000-0000-0000-0000-000000000001"
    sessions = [
        {
            "id": "00000000-0000-4000-8000-000000000001",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "participant_name": "Community member A",
            "participant_role": "farmer",
            "session_date": "2026-10-10",
            "session_topic": "Compost management",
            "session_type": "field_training",
            "duration_hours": 2.5,
            "pre_score": 2.0,
            "post_score": 4.0,
            "improvement_pct": 100.0,
            "trainer": "Farm educator",
            "notes": "Reviewed learning session.",
            "status": "published",
        },
        {
            "id": "00000000-0000-4000-8000-000000000002",
            "location_id": location_id,
            "location_name": "Kokonut Adelphi",
            "participant_name": "Community member A",
            "participant_role": "farmer",
            "session_date": "2026-09-10",
            "session_topic": "Water stewardship",
            "session_type": "workshop",
            "duration_hours": 1.5,
            "pre_score": 3.0,
            "post_score": 4.0,
            "improvement_pct": 50.0,
            "trainer": "Farm educator",
            "notes": "Follow-up session.",
            "status": "verified",
        },
    ]

    class Cursor:
        def __init__(self):
            self.calls = []
            self.current_query = ""

        def execute(self, query, params=None):
            self.current_query = " ".join(query.split())
            self.calls.append((self.current_query, params))

        def fetchone(self):
            return {"name": "Kokonut Adelphi"}

        def fetchall(self):
            return sessions if "v_public_training_impact" in self.current_query else []

        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.cursor_value = Cursor()

        def cursor(self, cursor_factory=None):
            return self.cursor_value

    connection = Connection()
    report = operations.generate_training_impact(connection, location_id)

    query, params = connection.cursor_value.calls[1]
    projection = re.search(r"SELECT (.*?) FROM v_public_training_impact", query)
    assert projection is not None
    assert [column.strip() for column in projection.group(1).split(",")] == columns
    assert "WHERE location_id = %s ORDER BY session_date DESC" in query
    assert params == (location_id,)
    assert report["report_type"] == "training_impact"
    assert report["location_id"] == location_id
    assert report["location_name"] == "Kokonut Adelphi"
    assert report["sessions"] == sessions
    assert report["total_sessions"] == 2
    assert report["unique_participants"] == 1
    assert report["total_training_hours"] == 4.0
    assert report["avg_improvement_pct"] == 75.0
