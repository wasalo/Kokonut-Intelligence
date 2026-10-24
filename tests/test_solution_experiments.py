"""Fail-closed coverage for legacy solution experiment writers."""

from unittest.mock import MagicMock

import pytest

from services.innovation import solution_experiments

LEGACY_WRITES = [
    pytest.param(
        lambda conn: solution_experiments.create_experiment(
            conn, "solution", "hypothesis", "baseline", "treatment", "unit",
            "rollback",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="create-protocol",
    ),
    pytest.param(
        lambda conn: solution_experiments.submit_protocol(conn, "experiment"),
        "location-scoped Solution Lifecycle Gateway",
        id="submit-protocol",
    ),
    pytest.param(
        lambda conn: solution_experiments.approve_protocol(
            conn, "experiment", "reviewer",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="approve-protocol",
    ),
    pytest.param(
        lambda conn: solution_experiments.start_experiment(
            conn, "experiment", "operator",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="start-experiment",
    ),
    pytest.param(
        lambda conn: solution_experiments.record_observation(
            conn, "experiment", "rainfall", 12.5, "baseline",
            recorded_by_party_id="participant",
        ),
        "consent-aware",
        id="record-observation",
    ),
    pytest.param(
        lambda conn: solution_experiments.analyze_sequentially(
            conn, "experiment", "rainfall",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="analyze-sequentially",
    ),
    pytest.param(
        lambda conn: solution_experiments.complete_experiment(
            conn, "experiment",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="complete-experiment",
    ),
    pytest.param(
        lambda conn: solution_experiments.review_result(
            conn, "experiment", "validated", "reviewer",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="review-result",
    ),
    pytest.param(
        lambda conn: solution_experiments.create_replication(
            conn, "solution", "experiment", "location", "target", "context",
        ),
        "location-scoped Solution Lifecycle Gateway",
        id="create-replication",
    ),
]


@pytest.mark.parametrize(("invoke", "message"), LEGACY_WRITES)
def test_legacy_experiment_writes_fail_before_database_access(invoke, message):
    conn = MagicMock()

    with pytest.raises(RuntimeError, match=message):
        invoke(conn)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()
