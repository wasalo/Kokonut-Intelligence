"""Tests for the Strategic Reserve layer (health, biodiversity, report)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.export import report_generator as rg
from services.strategic_reserve import health as srh


def test_registered():
    assert "strategic_reserve" in rg.REPORT_GENERATORS
    assert rg.REPORT_GENERATORS["strategic_reserve"] is rg.generate_strategic_reserve


def test_compute_adequacy():
    reserve = {"held_quantity": 50.0, "capacity_target": 100.0, "unit": "usd", "status": "active"}
    a = srh.compute_adequacy(reserve)
    assert a["adequacy_pct"] == 50.0
    assert a["drawdown_headroom"] == 50.0


def test_compute_adequacy_zero_target():
    reserve = {"held_quantity": 0.0, "capacity_target": 0.0, "unit": "usd"}
    a = srh.compute_adequacy(reserve)
    assert a["adequacy_pct"] is None


def test_breaches_operators():
    assert srh._breaches("lt", 4, 5) is True
    assert srh._breaches("gte", 5, 5) is True
    assert srh._breaches("gt", 3, 5) is False
    assert srh._breaches("eq", 5, 5) is True
    assert srh._breaches("lt", None, 5) is None
    assert srh._breaches(None, 1, 1) is None


def test_evaluate_trigger_no_key():
    reserve = {"trigger_metric_key": None}
    t = srh.evaluate_trigger(MagicMock(), reserve)
    assert t["trigger_defined"] is False


def test_evaluate_trigger_breach():
    reserve = {
        "trigger_metric_key": "carbon_reversal_risk",
        "trigger_operator": "gt",
        "trigger_threshold": 5.0,
        "scope_id": None,
    }
    conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchone.return_value = {"value": 9.0, "computed_at": "2026-01-01"}
    fake_cur.__enter__ = lambda self: self
    fake_cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = fake_cur
    t = srh.evaluate_trigger(conn, reserve)
    assert t["trigger_defined"] is True
    assert t["observed_value"] == 9.0
    assert t["breach"] is True
    assert t["release_proposed"] is True


def test_reserve_health_aggregates():
    reserves = [
        {"reserve_code": "R1", "reserve_type": "carbon_buffer", "entity_scope": "farm",
         "name": "Carbon", "adequacy": {"adequacy_pct": 200.0}},
        {"reserve_code": "R2", "reserve_type": "seed_vault", "entity_scope": "farm",
         "name": "Seed", "adequacy": {"adequacy_pct": 10.0}},
    ]
    conn = MagicMock()
    with patch.object(srh, "reserve_health", return_value={
        "reserve_count": 2, "reserves": reserves, "generated_at": "x",
    }):
        out = rg.generate_strategic_reserve(conn, location_id="all")
    assert out["report_type"] == "strategic_reserve"
    assert out["reserve_count"] == 2
    # R1 adequately funded (200% >= 100); R2 not (10%).
    assert out["fundability_signal"]["adequately_funded_reserves"] == 1
    assert out["fundability_signal"]["fundability_pct"] == 50.0


def test_report_seed_vault_isolated_on_error():
    reserves = [
        {"reserve_code": "R1", "reserve_type": "carbon_buffer", "entity_scope": "farm",
         "name": "Carbon", "adequacy": {"adequacy_pct": 100.0}},
    ]
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [{"id": "a0000000-0000-0000-0000-000000000001", "name": "Loc1"}]
    cur.__enter__ = lambda self: self
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    with patch.object(srh, "reserve_health", return_value={
        "reserve_count": 1, "reserves": reserves, "generated_at": "x",
    }), \
         patch.object(srh, "seed_vault_health", side_effect=RuntimeError("boom")):
        out = rg.generate_strategic_reserve(conn, location_id="a0000000-0000-0000-0000-000000000001")
    # Per-location seed-vault error is isolated, not crashing the report.
    seed = out["locations"][0]["seed_vault"]
    assert "error" in seed
