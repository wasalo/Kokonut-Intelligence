"""Mocked tests for the role-authority decision contract."""

import pytest

from services.analytics import governance_roles


class _Cursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, query, params):
        self.connection.query = query
        self.connection.params = params

    def fetchone(self):
        return self.connection.row


class _Connection:
    def __init__(self, row):
        self.row = row
        self.query = None
        self.params = None

    def cursor(self):
        return _Cursor(self)


@pytest.mark.parametrize(
    ("row", "required_level", "expected"),
    [
        (None, "observe", {
            "decision": "denied",
            "authority_granted": False,
            "authority_level": None,
            "required_level": "observe",
            "human_approval_required": False,
        }),
        (("recommend", True), "execute", {
            "decision": "denied",
            "authority_granted": False,
            "authority_level": "recommend",
            "required_level": "execute",
            "human_approval_required": False,
        }),
        (("execute", True), "execute", {
            "decision": "approval_required",
            "authority_granted": True,
            "authority_level": "execute",
            "required_level": "execute",
            "human_approval_required": True,
        }),
        (("decide", False), "recommend", {
            "decision": "authorized",
            "authority_granted": True,
            "authority_level": "decide",
            "required_level": "recommend",
            "human_approval_required": False,
        }),
    ],
)
def test_authority_evaluator_separates_role_authority_from_human_approval(
    row, required_level, expected
):
    conn = _Connection(row)

    result = governance_roles.evaluate_role_authority(
        conn,
        "11111111-1111-4111-8111-111111111111",
        "work_item",
        "stakeholder_triage",
        scope_type="location",
        scope_id="22222222-2222-4222-8222-222222222222",
        required_level=required_level,
    )

    assert result == expected
    assert conn.params == (
        "11111111-1111-4111-8111-111111111111",
        "work_item",
        "stakeholder_triage",
        "location",
        "22222222-2222-4222-8222-222222222222",
    )
    assert "r.status = 'active' AND c.status = 'active'" in conn.query
    assert "a.effective_from IS NOT NULL AND a.effective_from <= NOW()" in conn.query
    assert "a.effective_until IS NULL OR a.effective_until >= NOW()" in conn.query
    assert "r.effective_until IS NULL OR r.effective_until >= NOW()" in conn.query
    assert "BOOL_OR(d.requires_human_approval)" in conn.query


def test_legacy_boolean_helper_preserves_authority_only_contract():
    conn = _Connection(("execute", True))

    assert governance_roles.role_can_act(
        conn,
        "11111111-1111-4111-8111-111111111111",
        "work_item",
        "stakeholder_triage",
        scope_type="location",
        scope_id="22222222-2222-4222-8222-222222222222",
        required_level="execute",
    ) is True


def test_invalid_authority_level_fails_before_query():
    conn = _Connection(("execute", False))

    with pytest.raises(ValueError, match="required_level"):
        governance_roles.evaluate_role_authority(
            conn,
            "11111111-1111-4111-8111-111111111111",
            "work_item",
            "stakeholder_triage",
            required_level="publish",
        )

    assert conn.query is None
