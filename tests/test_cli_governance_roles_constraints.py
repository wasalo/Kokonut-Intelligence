"""Fail-closed JSON preflight for governance domain constraints."""

import sys
from datetime import datetime
from unittest.mock import Mock

import pytest

from services.analytics import cli_governance_roles


@pytest.mark.parametrize("constraints", ["not-json", "[]", '"recommend"', "null"])
def test_domain_add_rejects_invalid_or_non_object_constraints_before_connection(
    monkeypatch, capsys, constraints
):
    connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli_governance_roles, "_connection", connection)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kokonut-governance",
            "domain-add",
            "role-1",
            "farm_operations",
            "irrigation",
            "--constraints",
            constraints,
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli_governance_roles.main()

    assert error.value.code == 2
    assert "--constraints must be a valid JSON object" in capsys.readouterr().err
    connection.assert_not_called()


def test_domain_add_passes_decoded_constraints_to_service(monkeypatch):
    connection = Mock()
    add_domain = Mock(return_value={"created": True})
    output = Mock()
    constraints = {"max_amount": 3, "resources": ["soil", "water"]}
    monkeypatch.setattr(cli_governance_roles, "_connection", Mock(return_value=connection))
    monkeypatch.setattr(cli_governance_roles, "add_domain", add_domain)
    monkeypatch.setattr(cli_governance_roles, "_out", output)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kokonut-governance",
            "domain-add",
            "role-1",
            "farm_operations",
            "irrigation",
            "--constraints",
            '{"max_amount":3,"resources":["soil","water"]}',
        ],
    )

    cli_governance_roles.main()

    add_domain.assert_called_once_with(
        connection,
        "role-1",
        "farm_operations",
        "irrigation",
        scope_type="network",
        scope_id=None,
        authority_level="recommend",
        constraints=constraints,
        requires_human_approval=True,
    )
    output.assert_called_once_with({"created": True})


@pytest.mark.parametrize(
    "review_due_at",
    ["not-a-timestamp", "2026-10-30T12:00:00", "2026-02-30T12:00:00Z"],
)
def test_assignment_add_rejects_invalid_review_deadline_before_connection(
    monkeypatch, capsys, review_due_at
):
    connection = Mock(side_effect=AssertionError("database must not be opened"))
    monkeypatch.setattr(cli_governance_roles, "_connection", connection)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kokonut-governance",
            "assignment-add",
            "role-id",
            "party-id",
            "--review-due-at",
            review_due_at,
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli_governance_roles.main()

    assert error.value.code == 2
    assert "--review-due-at" in capsys.readouterr().err
    connection.assert_not_called()


@pytest.mark.parametrize(
    ("review_due_at", "expected"),
    [
        ("2026-10-30T12:00:00Z", datetime.fromisoformat("2026-10-30T12:00:00+00:00")),
        ("2026-10-30T12:00:00-04:00", datetime.fromisoformat("2026-10-30T12:00:00-04:00")),
    ],
)
def test_assignment_add_passes_aware_review_deadline_to_service(
    monkeypatch, review_due_at, expected
):
    connection = Mock()
    assign = Mock(return_value={"created": True})
    output = Mock()
    monkeypatch.setattr(
        cli_governance_roles, "_connection", Mock(return_value=connection)
    )
    monkeypatch.setattr(cli_governance_roles, "assign_role", assign)
    monkeypatch.setattr(cli_governance_roles, "_out", output)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "kokonut-governance",
            "assignment-add",
            "role-id",
            "party-id",
            "--review-due-at",
            review_due_at,
        ],
    )

    cli_governance_roles.main()

    assign.assert_called_once_with(
        connection,
        "role-id",
        "party-id",
        assignment_type="primary",
        assigned_by_party_id=None,
        mandate=None,
        review_due_at=expected,
    )
    output.assert_called_once_with({"created": True})
