"""Regression tests for governed AI impact evaluation."""

from services.abundance.ai_evaluation import evaluate_impact


class _Cursor:
    def __init__(self):
        self.query = ""
        self.execute_count = 0
        self.insert_params = None
        self.closed = False

    def execute(self, query, params=None):
        self.query = query
        self.execute_count += 1
        if "INSERT INTO ai_impact_evaluation" in query:
            self.insert_params = params

    def fetchall(self):
        if "FROM metric_value" in self.query:
            return [{"metric_name": "soil_health", "value": 1.0, "unit": "score"}]
        return []

    def fetchone(self):
        if "INSERT INTO ai_impact_evaluation" in self.query:
            return ("evaluation-123",)
        return None

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.cursor_instance = _Cursor()
        self.commits = 0

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.commits += 1


def test_evaluate_impact_scores_verified_metrics():
    conn = _Connection()

    result = evaluate_impact(conn, "location-123")

    assert result["evaluation_id"] == "evaluation-123"
    assert result["impact_score"] == 5.0
    assert result["confidence"] == 0.05
    assert result["metrics_used"] == 1
    assert conn.cursor_instance.insert_params[4] == 5.0
    assert conn.commits == 1
