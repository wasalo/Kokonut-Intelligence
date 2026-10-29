"""Mock-only contract for the capability dashboard view projection."""

import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from services.analytics import capability_map


def test_dashboard_uses_exact_migration_207_projection_and_guild_filter():
    columns = (
        "capability_id, capability_name, capability_type, guild_key, maturity_level, "
        "owner_role, status, parent_id, parent_name, process_count, service_count, "
        "child_count, latest_maturity_score, created_at, updated_at"
    )
    capability_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    created_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    updated_at = datetime(2026, 10, 29, tzinfo=timezone.utc)
    row = {
        "capability_id": capability_id,
        "capability_name": "Regenerative operations",
        "capability_type": "operational",
        "guild_key": "farm-operations",
        "maturity_level": 3,
        "owner_role": "farm-manager",
        "status": "active",
        "parent_id": parent_id,
        "parent_name": "Operations",
        "process_count": 4,
        "service_count": 2,
        "child_count": 1,
        "latest_maturity_score": 3.5,
        "created_at": created_at,
        "updated_at": updated_at,
    }

    for guild_key, where, params in (
        (None, "", []),
        ("farm-operations", " WHERE guild_key = %s", ["farm-operations"]),
    ):
        cursor = MagicMock()
        cursor.fetchall.return_value = [row]
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor

        with patch.object(capability_map, "_conn", return_value=nullcontext(conn)):
            result = capability_map.get_capability_dashboard(guild_key=guild_key)

        sql, bound = cursor.execute.call_args.args
        assert sql == (
            f"SELECT {columns} FROM v_capability_dashboard{where} "
            "ORDER BY guild_key, capability_type, capability_name"
        )
        assert bound == params
        assert result == [
            {
                **row,
                "capability_id": str(capability_id),
                "parent_id": str(parent_id),
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
            }
        ]
