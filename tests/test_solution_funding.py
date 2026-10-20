"""Legacy solution-funding writers fail closed before database access."""

import uuid
from unittest.mock import MagicMock

import pytest

from services.innovation import solution_funding


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (lambda conn: solution_funding.create_case(conn, "solution", "stage", "grant", 1, "rationale"), "case creation"),
        (lambda conn: solution_funding.submit_case(conn, "case", "party"), "case submission"),
        (lambda conn: solution_funding.approve_case(conn, "case", "party"), "case approval"),
        (lambda conn: solution_funding.add_tranche(conn, "case", 1, 1), "tranche creation"),
        (lambda conn: solution_funding.approve_tranche(conn, "tranche", "party"), "tranche approval"),
        (lambda conn: solution_funding.release_tranche(conn, "tranche", 1, "party", []), "tranche release"),
    ],
)
def test_legacy_funding_writers_fail_before_database_access(operation, message):
    conn = MagicMock()

    with pytest.raises(RuntimeError, match=message):
        operation(conn)

    conn.cursor.assert_not_called()
    conn.commit.assert_not_called()
    conn.rollback.assert_not_called()


def test_clean_helper_converts_uuids():
    mock_uuid = uuid.uuid4()
    row = {"id": mock_uuid, "amount": 1000}

    cleaned = solution_funding._clean(row)

    assert cleaned["id"] == str(mock_uuid)
