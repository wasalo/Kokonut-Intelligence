"""EBF privacy and stakeholder feedback protection tests."""

from services.agents.feedback_agent import synthesize_feedback


def test_equity_feedback_synthesis_omits_private_raw_text() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchall(self):
            if self.calls == 1:
                return []
            return [{"stakeholder_group": "resident", "feedback_type": "equity", "sentiment": "mixed", "status": "verified", "consent_given": False, "is_public": False, "evidence_maturity": 2, "feedback_count": 1, "private_or_no_consent_count": 1, "harm_count": 0}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["private_or_no_consent_count"] == 1
    assert "Raw private feedback is not included" in summary["safety_note"]


if __name__ == "__main__":
    test_equity_feedback_synthesis_omits_private_raw_text()
