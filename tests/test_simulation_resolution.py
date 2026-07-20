"""Tests for the tactical-wargame simulation primitives.

Covers Monte Carlo ensemble aggregation, clash resolution, and clash sweep.
These are advisory-only analytical helpers; no governed state is touched.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from services.simulation.resolution import (
    DistributionSpec,
    clash_sweep,
    monte_carlo,
    resolve_clash,
)


def _fake_sim(conn, **params) -> dict:
    """Deterministic fake simulator: yield = base * rainfall - temp_penalty."""
    rainfall = float(params.get("rainfall_multiplier", 1.0))
    temp = float(params.get("temperature_offset_c", 0.0))
    return {"final_yield_kg_ha": 1000.0 * rainfall - 20.0 * abs(temp)}


def test_monte_carlo_aggregates_distribution():
    out = monte_carlo(
        _fake_sim,
        {"rainfall_multiplier": 1.0, "temperature_offset_c": 0.0},
        sampler={
            "rainfall_multiplier": {"dist": "normal", "mean": 1.0, "sd": 0.1},
            "temperature_offset_c": {"dist": "normal", "mean": 0.0, "sd": 1.0},
        },
        metric="final_yield_kg_ha",
        n=400,
        seed=42,
    )
    assert out["n"] == 400
    assert out["failures"] == []
    assert out["p5"] < out["p50"] < out["p95"]
    assert 850.0 < out["mean"] < 1050.0


def test_monte_carlo_seed_reproducible():
    base = {"rainfall_multiplier": 1.0, "temperature_offset_c": 0.0}
    sampler = {"rainfall_multiplier": {"dist": "normal", "mean": 1.0, "sd": 0.1}}
    a = monte_carlo(_fake_sim, base, sampler=sampler, metric="final_yield_kg_ha", n=200, seed=7)
    b = monte_carlo(_fake_sim, base, sampler=sampler, metric="final_yield_kg_ha", n=200, seed=7)
    assert a["mean"] == b["mean"]
    assert a["samples"] == b["samples"]


def test_monte_carlo_isolates_failing_draw():
    def _boom(conn, **params):
        raise RuntimeError("draw failed")

    out = monte_carlo(
        _boom,
        {},
        sampler={"x": {"dist": "uniform", "low": 0.0, "high": 1.0}},
        metric="y",
        n=50,
        seed=1,
    )
    assert out["failures"] and len(out["failures"]) == 50
    assert out["samples"] == []
    assert out["mean"] is None


def test_monte_carlo_per_draw_conn_factory():
    opens = {"count": 0}

    def _factory():
        opens["count"] += 1
        return MagicMock()

    out = monte_carlo(
        _fake_sim,
        {"rainfall_multiplier": 1.0},
        sampler={"rainfall_multiplier": {"dist": "normal", "mean": 1.0, "sd": 0.05}},
        metric="final_yield_kg_ha",
        conn_factory=_factory,
        n=30,
        seed=3,
        max_workers=4,
    )
    assert opens["count"] == 30
    assert out["failures"] == []


def test_resolve_clash_symmetric():
    r = resolve_clash(2.0, 2.0, model="ratio")
    assert abs(r["attacker_win_p"] - 0.5) < 1e-6
    assert abs(r["defender_hold_p"] - 0.5) < 1e-6
    assert r["mutual_p"] > 0.0


def test_resolve_clash_dominant_attacker():
    r = resolve_clash(8.0, 1.0, model="ratio")
    assert r["attacker_win_p"] > 0.9
    assert r["defender_hold_p"] < 0.1


def test_resolve_clash_mutual_loss_bounds():
    r = resolve_clash(1.0, 1.0, model="ratio")
    for v in r.values():
        if isinstance(v, float):
            assert 0.0 <= v <= 1.0


def test_resolve_clash_stochastic_reproducible():
    a = resolve_clash(2.0, 1.5, model="ratio", rng=np.random.default_rng(5), n=300)
    b = resolve_clash(2.0, 1.5, model="ratio", rng=np.random.default_rng(5), n=300)
    assert a["attacker_win_p"] == b["attacker_win_p"]


def test_clash_sweep_concurrent_and_isolated():
    scenarios = [
        {"label": "A", "attacker_strength": 5.0, "defender_strength": 1.0, "n": 50},
        {"label": "B", "attacker_strength": 1.0, "defender_strength": 9.0, "n": 50},
        {"label": "bad", "attacker_strength": "not-a-number"},
    ]
    results = clash_sweep(scenarios, max_workers=4, seed=11)
    by_label = {r["label"]: r for r in results}
    assert "A" in by_label and "B" in by_label
    assert by_label["A"]["attacker_win_p"] > by_label["B"]["attacker_win_p"]
    assert "error" in by_label["bad"]


def test_distribution_spec_sample_sd():
    spec = DistributionSpec(dist="normal", mean=10.0, sd=2.0)
    rng = np.random.default_rng(0)
    vals = [spec.sample(rng) for _ in range(500)]
    assert 8.0 < float(np.mean(vals)) < 12.0
