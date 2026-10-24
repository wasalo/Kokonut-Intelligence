"""Tests for private coaching and resource decisions."""

from unittest.mock import MagicMock

import pytest

from services.management import operating_support

PARTY_ID = "b0000000-0000-0000-0000-000000002505"


@pytest.mark.parametrize(
    ("function", "args", "kwargs"),
    [
        (
            operating_support.record_coaching_session,
            ("adelphi", "scope-id", PARTY_ID, "private coaching focus"),
            {
                "wellbeing_check": "private health detail",
                "notes": "private coaching notes",
            },
        ),
        (
            operating_support.request_resource,
            ("internal", "scope-id", PARTY_ID, "water", "Private water request"),
            {},
        ),
        (
            operating_support.decide_resource,
            ("request-id", PARTY_ID, "approved"),
            {"reason": "reviewed"},
        ),
    ],
)
def test_unscoped_mutations_fail_before_database_access(function, args, kwargs):
    connection = MagicMock()

    with pytest.raises(RuntimeError, match="operating-pilot Gateway"):
        function(connection, *args, **kwargs)

    connection.cursor.assert_not_called()
    connection.commit.assert_not_called()
