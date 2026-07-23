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


def test_synthesis_omits_private_feedback_text() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchall(self):
            if self.calls == 1:
                return []
            return [{"stakeholder_group": "farmer", "feedback_type": "equity",
                     "sentiment": "positive", "status": "verified",
                     "consent_given": False, "is_public": False,
                     "evidence_maturity": 2, "feedback_count": 3,
                     "private_or_no_consent_count": 3, "harm_count": 0}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["private_or_no_consent_count"] == 3
    assert summary["public_feedback_count"] == 0
    assert "Raw private" in summary["safety_note"]


def test_synthesis_includes_harm_count_when_present() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchall(self):
            if self.calls == 1:
                return []
            return [{"stakeholder_group": "resident", "feedback_type": "concern",
                     "sentiment": "negative", "status": "verified",
                     "consent_given": True, "is_public": True,
                     "evidence_maturity": 3, "feedback_count": 2,
                     "private_or_no_consent_count": 0, "harm_count": 1}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["harm_or_unintended_consequence_count"] == 1
    assert "harms" in summary["synthesis"].lower() or "reviewer attention" in summary["synthesis"].lower()


if __name__ == "__main__":
    test_equity_feedback_synthesis_omits_private_raw_text()
