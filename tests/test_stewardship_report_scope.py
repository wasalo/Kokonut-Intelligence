"""Direct-call location scope validation for stewardship reports."""

from unittest.mock import Mock
from uuid import uuid4

import pytest

from services.export.reports.commons.stewardship import (
    generate_community_governance,
    generate_replication_readiness,
)

REPORTS = [
    (generate_community_governance, "community_governance"),
    (generate_replication_readiness, "replication_readiness"),
]
INVALID_SCOPES = [
    None,
    "",
    "all",
    "not-a-uuid",
    "11111111-1111-4111-8111-111111111111,22222222-2222-4222-8222-222222222222",
]


@pytest.mark.parametrize("generator, report_type", REPORTS)
@pytest.mark.parametrize("location_id", INVALID_SCOPES)
def test_invalid_location_scope_fails_before_cursor(
    generator, report_type, location_id
):
    conn = Mock()

    with pytest.raises(ValueError, match=f"{report_type} requires an explicit location_id"):
        generator(conn, location_id)

    conn.cursor.assert_not_called()


@pytest.mark.parametrize("generator, report_type", REPORTS)
def test_valid_location_uuid_reaches_existing_report_query(generator, report_type):
    location_id = str(uuid4())
    conn = Mock()
    cursor = Mock()
    cursor.fetchall.return_value = []
    conn.cursor.return_value = cursor

    report = generator(conn, location_id)

    assert report["report_type"] == report_type
    assert report["location_id"] == location_id
    conn.cursor.assert_called_once()
    cursor.execute.assert_called_once()
    cursor.close.assert_called_once()
