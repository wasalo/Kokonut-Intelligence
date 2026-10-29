"""Migration-271 projection contracts for strategy advantage readers."""

from __future__ import annotations

from contextlib import AbstractContextManager
from uuid import UUID, uuid4

from services.analytics import advantage_assessment, competitive_report, strategy_coherence

PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ADVANTAGE_COLUMNS = (
    "advantage_id, strategy_plan_id, name, defensibility_score, status, "
    "link_count, capability_link_count, choice_link_count, investment_link_count, fit_status"
)
ADVANTAGE_SELECT = (
    f"SELECT {ADVANTAGE_COLUMNS} FROM v_strategy_advantage_fit "
    "WHERE strategy_plan_id = %s::uuid"
)
ADVANTAGE_ORDERED_SELECT = ADVANTAGE_SELECT + " ORDER BY defensibility_score DESC NULLS LAST"


def _advantage(name: str, score: int | None, *, fit_status: str = "fit") -> dict:
    return {
        "advantage_id": uuid4(),
        "strategy_plan_id": UUID(PLAN_ID),
        "name": name,
        "defensibility_score": score,
        "status": "active",
        "link_count": 2,
        "capability_link_count": 1,
        "choice_link_count": 0,
        "investment_link_count": 1,
        "fit_status": fit_status,
    }


class _Cursor(AbstractContextManager):
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.query = ""
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=None):
        self.query = " ".join(query.split())
        self.parameters = parameters
        self.connection.operations.append((self.query, parameters))
        if "FROM v_strategy_advantage_fit" in self.query:
            self.rows = list(self.connection.advantages)
        elif self.query.startswith("SELECT * FROM strategy_plan"):
            self.rows = [
                {
                    "id": UUID(PLAN_ID),
                    "diagnosis_summary": "A supported diagnosis",
                    "guiding_policy": "A coherent policy",
                    "status": "draft",
                }
            ]
        elif "FROM strategy_foresight_frame" in self.query:
            self.rows = [{"id": uuid4(), "status": "approved"}]
        elif "COUNT(*) AS count" in self.query:
            self.rows = [{"count": 1}]
        elif "INSERT INTO strategy_coherence_finding" in self.query:
            p = parameters
            entity_id = p[3] if isinstance(p[3], UUID) else UUID(p[3])
            self.rows = [{
                "id": uuid4(),
                "strategy_plan_id": UUID(p[0]),
                "rule_key": p[1],
                "entity_type": p[2],
                "entity_id": entity_id,
                "severity": p[4],
                "explanation": p[5],
                "evidence": {},
                "remediation": p[7],
            }]
        elif "FROM v_strategy_competitive_health" in self.query:
            self.rows = [{
                "strategy_plan_id": UUID(PLAN_ID),
                "scope_type": "location",
                "scope_id": None,
                "landscape_count": 0,
                "verified_landscape_count": 0,
                "average_force_pressure_score": None,
                "unreviewed_material_signal_count": 0,
                "approved_position_count": 0,
                "verified_advantage_count": 0,
                "unlinked_advantage_count": 0,
                "partial_advantage_count": 0,
                "open_competitive_review_count": 0,
            }]
        else:
            self.rows = []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class _Connection:
    def __init__(self, advantages):
        self.advantages = list(advantages)
        self.operations = []
        self.commits = 0

    def cursor(self, cursor_factory=None):
        return _Cursor(self)

    def commit(self):
        self.commits += 1


def _assert_projection(connection, *, ordered: bool):
    expected = ADVANTAGE_ORDERED_SELECT if ordered else ADVANTAGE_SELECT
    matching = [
        (query, params)
        for query, params in connection.operations
        if "FROM v_strategy_advantage_fit" in query
    ]
    assert len(matching) == 1
    query, params = matching[0]
    assert query == expected
    assert params == (PLAN_ID,)


def test_strategy_coherence_uses_exact_advantage_projection_and_preserves_findings():
    connection = _Connection([_advantage("Unlinked claim", 75, fit_status="unlinked")])

    findings = strategy_coherence.run_checks(connection, PLAN_ID)

    _assert_projection(connection, ordered=False)
    assert [finding["rule_key"] for finding in findings] == ["advantage_requires_operating_fit"]
    assert findings[0]["entity_id"] == str(connection.advantages[0]["advantage_id"])
    assert connection.commits == 1


def test_competitive_report_uses_ordered_projection_and_preserves_payload():
    advantages = [
        _advantage("Strong fit", 90),
        _advantage("Moderate fit", 50),
        _advantage("Unscored fit", None),
    ]
    connection = _Connection(advantages)

    result = competitive_report.report(connection, PLAN_ID)

    _assert_projection(connection, ordered=True)
    assert [row["name"] for row in result["advantages"]] == [
        "Strong fit",
        "Moderate fit",
        "Unscored fit",
    ]
    assert result["advantages"] == [
        {**row, "advantage_id": str(row["advantage_id"]), "strategy_plan_id": PLAN_ID}
        for row in advantages
    ]
    assert result["strategy_plan_id"] == PLAN_ID
    assert result["health"]["strategy_plan_id"] == PLAN_ID


def test_fit_dashboard_uses_ordered_projection_and_preserves_rows():
    advantages = [_advantage("First", 80), _advantage("Second", 40)]
    connection = _Connection(advantages)

    rows = advantage_assessment.fit_dashboard(connection, PLAN_ID)

    _assert_projection(connection, ordered=True)
    assert [row["name"] for row in rows] == ["First", "Second"]
    assert rows == [
        {**row, "advantage_id": str(row["advantage_id"]), "strategy_plan_id": PLAN_ID}
        for row in advantages
    ]
