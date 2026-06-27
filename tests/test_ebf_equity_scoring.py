"""EBF equity scoring tests."""

from services.scoring.equity import compute_equity_score_from_feedback


def test_equity_score_uses_aggregate_feedback_only() -> None:
    class Cursor:
        def execute(self, query, params):
            assert "raw" not in query.lower()
        def fetchone(self):
            return {
                "feedback_count": 4,
                "public_safe_feedback_count": 2,
                "positive_count": 3,
                "negative_count": 0,
                "stakeholder_group_count": 2,
            }
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    result = compute_equity_score_from_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert result["score"] > 0
    assert "raw private feedback is not exposed" in result["safety_note"]


if __name__ == "__main__":
    test_equity_score_uses_aggregate_feedback_only()
