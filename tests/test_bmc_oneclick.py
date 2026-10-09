"""Tests for the BMC one-click (create-from-data) capability."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import services.analytics.business_model_canvas as bmc


def _fake_suggest(conn, location_id):
    return {
        "blocks": {
            "key_partners": [{"name": "Coop", "type": "cooperative"}],
            "key_activities": [{"name": "Farming"}],
            "key_resources": [],
            "value_propositions": [],
            "customer_relationships": [],
            "channels": [],
            "customer_segments": [],
            "revenue_streams": [],
            "cost_structure": {},
        },
        "generated_from": ["cooperative"],
    }


def test_create_from_data_populates_blocks():
    created = {"id": "c0000000-0000-0000-0000-00000000000c", "status": "draft", "version": 1}
    conn = MagicMock()
    with patch.object(bmc, "suggest", side_effect=_fake_suggest), \
         patch.object(bmc, "create", return_value=created) as mock_create:
        out = bmc.create_from_data(conn, location_id="a0000000-0000-0000-0000-000000000001")

    assert out["canvas"] == created
    assert out["generated_from"] == ["cooperative"]
    assert "key_partners" in out["populated_blocks"]
    # create() must receive the suggested blocks.
    _, kwargs = mock_create.call_args
    assert kwargs["blocks"]["key_partners"]


def test_create_from_data_requires_entity():
    conn = MagicMock()
    try:
        bmc.create_from_data(conn)
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("expected ValueError")
