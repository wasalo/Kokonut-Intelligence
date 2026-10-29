"""Fail-closed JSON preflight for governance domain constraints."""

import sys
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
