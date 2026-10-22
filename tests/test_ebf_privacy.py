"""EBF privacy and stakeholder feedback protection tests."""

from services.agents.feedback_agent import synthesize_feedback


def test_equity_feedback_synthesis_omits_private_raw_text() -> None:
    class Cursor:
        query = ""
        def execute(self, query, params):
            self.query = query
        def fetchall(self):
            return []
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            self.cursor_instance = Cursor()
            return self.cursor_instance
    conn = Conn()
    summary = synthesize_feedback(conn, "a0000000-0000-0000-0000-000000000001")
    assert summary["private_or_no_consent_count"] is None
    assert summary["harm_or_unintended_consequence_count"] is None
    assert "private/no-consent counts" in summary["safety_note"].lower()
    assert "FROM v_public_stakeholder_feedback_summary" in conn.cursor_instance.query
    assert "FROM stakeholder_feedback" not in conn.cursor_instance.query


def test_synthesis_omits_private_feedback_text() -> None:
    class Cursor:
        query = ""
        def execute(self, query, params):
            self.query = query
        def fetchall(self):
            return [{"stakeholder_group": "farmer", "feedback_type": "equity",
                     "sentiment": "positive", "public_summary": "A public-safe note",
                     "evidence_maturity": 3}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["private_or_no_consent_count"] is None
    assert summary["public_feedback_count"] == 1
    assert summary["aggregate_feedback"][0]["feedback_count"] == 1


def test_synthesis_includes_harm_count_when_present() -> None:
    class Cursor:
        calls = 0
        def execute(self, query, params):
            self.calls += 1
        def fetchall(self):
            if self.calls == 1:
                return []
            return [{"stakeholder_group": "resident", "feedback_type": "concern",
                     "sentiment": "negative", "public_summary": "A concern",
                     "evidence_maturity": 3}]
        def close(self):
            pass
    class Conn:
        def cursor(self, cursor_factory=None):
            return Cursor()
    summary = synthesize_feedback(Conn(), "a0000000-0000-0000-0000-000000000001")
    assert summary["harm_or_unintended_consequence_count"] is None
    assert "harm" not in summary["synthesis"].lower()


if __name__ == "__main__":
    test_equity_feedback_synthesis_omits_private_raw_text()
