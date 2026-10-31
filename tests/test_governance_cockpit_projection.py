"""Mock-only public governance cockpit privacy contract."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from services.analytics.governance_cockpit import public_cockpit


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (
            {
                "active_circle_count": 2,
                "active_role_count": 5,
                "resolved_tension_count": 3,
                "implemented_proposal_count": 4,
                "privacy_limitation": "Public aggregate only",
                "generated_at": datetime(2026, 10, 29, tzinfo=timezone.utc),
            },
            {
                "active_circle_count": 2,
                "active_role_count": 5,
                "resolved_tension_count": 3,
                "implemented_proposal_count": 4,
                "privacy_limitation": "Public aggregate only",
                "generated_at": datetime(2026, 10, 29, tzinfo=timezone.utc),
            },
        ),
        (None, {}),
    ],
)
def test_public_cockpit_uses_exact_migration_249_projection_and_preserves_payload(row, expected):
    cursor = MagicMock()
    cursor.fetchone.return_value = row
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor

    result = public_cockpit(conn)

    assert cursor.execute.call_args.args == (
        "SELECT active_circle_count, active_role_count, resolved_tension_count, "
        "implemented_proposal_count, privacy_limitation, generated_at "
        "FROM v_governance_cockpit_public",
    )
    assert result == expected
    if result:
        assert set(result) == {
            "active_circle_count",
            "active_role_count",
            "resolved_tension_count",
            "implemented_proposal_count",
            "privacy_limitation",
            "generated_at",
        }
        assert not {"identity", "tension_details", "proposal_title"} & set(result)
