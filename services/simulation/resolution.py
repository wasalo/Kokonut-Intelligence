"""Tactical-wargame inspired simulation primitives.

These are ADVISORY-ONLY analytical tools. They do not write governed state
and never publish or act. The "opposing force" modelled here is restricted to
shocks, threats, pests, market pressure, and competitor data -- never the
fragmentation or adversarial manipulation of stakeholders or communities
(see AGENTS.md: anti-capture governance, stakeholder unity).

Two ideas are borrowed from tactical wargames (Wikipedia):
1. Combat resolution with uncertainty -- outcomes are resolved probabilistically
   (dice / Combat Results Table), not as single deterministic points.
2. Two-sided clash resolution -- attacker vs. defender strengths produce a
   probability distribution over outcomes, including mutual loss.

The Monte Carlo runner wraps any deterministic simulator as a black box,
perturbs sampled inputs, and aggregates a caller-chosen scalar metric into a
distribution. Draws run under a bounded thread pool so one failing draw does
not abort the batch (each draw opens its own DB connection).
"""

from __future__ import annotations

import concurrent.futures
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from services.common.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_WORKERS = 8
DEFAULT_DRAWS = 500


@dataclass
class DistributionSpec:
    """Specification of a probability distribution used to perturb an input."""

    dist: str
    mean: float = 0.0
    sd: float = 1.0
    low: float = 0.0
    high: float = 1.0
    mode: float = 0.0

    def sample(self, rng: np.random.Generator) -> float:
        if self.dist == "normal":
            return float(rng.normal(self.mean, self.sd))
        if self.dist == "lognormal":
            return float(rng.lognormal(mean=self.mean, sigma=self.sd))
        if self.dist == "uniform":
            return float(rng.uniform(self.low, self.high))
        if self.dist == "triangular":
            return float(rng.triangular(self.low, self.mode, self.high))
        raise ValueError(f"Unknown distribution: {self.dist!r}")


def _coerce_sampler(sampler: Dict[str, Any]) -> Dict[str, DistributionSpec]:
    specs: Dict[str, DistributionSpec] = {}
    for name, spec in sampler.items():
        if isinstance(spec, DistributionSpec):
            specs[name] = spec
        else:
            specs[name] = DistributionSpec(**spec)
    return specs


def _get_metric(result: Dict[str, Any], metric: str) -> float:
    """Extract a scalar metric from a nested result dict using dot-path."""
    node: Any = result
    for part in metric.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise KeyError(f"Metric {metric!r} not found in simulation result")
    return float(node)


def monte_carlo(
    sim_callable: Callable[..., Dict[str, Any]],
    base_params: Dict[str, Any],
    *,
    sampler: Dict[str, Any],
    metric: str,
    conn: Any = None,
    conn_factory: Optional[Callable[[], Any]] = None,
    n: int = DEFAULT_DRAWS,
    seed: Optional[int] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Dict[str, Any]:
    """Run a Monte Carlo ensemble over a deterministic simulator.

    Args:
        sim_callable: Black-box simulator, called as ``sim_callable(conn, **params)``
            and expected to return a dict. Its side effects (e.g. persisting a run
            row) are left intact -- this helper only aggregates a scalar metric.
        base_params: Parameter dict passed to every draw (merged with perturbations).
        sampler: Mapping of param name -> distribution spec used to perturb that
            param per draw. Specs: {"dist": "normal"|"lognormal"|"uniform"|"triangular",
            plus the relevant moments}.
        metric: Dot-path scalar to extract from each result (e.g. "final_yield_kg_ha"
            or "summary.yield_kg_ha").
        conn: Optional shared connection for the synchronous caller path. Ignored
            when a per-draw conn_factory is supplied; each worker gets its own conn.
        conn_factory: Callable returning a fresh DB connection for a draw. Required
            for concurrent draws (psycopg2 connections are not thread-safe).
        n: Number of draws.
        seed: RNG seed for reproducibility.
        max_workers: Bound on concurrent draws.

    Returns:
        {"mean", "p5", "p50", "p95", "std", "n", "failures", "samples"}
        where ``failures`` lists per-draw errors (never fatal) and ``samples`` holds
        the aggregated metric values.
    """
    specs = _coerce_sampler(sampler)
    samples: List[float] = []
    failures: List[Dict[str, Any]] = []
    lock = threading.Lock()

    def _draw(draw_index: int) -> None:
        draw_rng = np.random.default_rng(None if seed is None else seed + draw_index)
        params = dict(base_params)
        for name, spec in specs.items():
            params[name] = spec.sample(draw_rng)
        draw_conn = conn_factory() if conn_factory is not None else conn
        try:
            result = sim_callable(draw_conn, **params)
            if isinstance(result, dict) and "error" in result:
                with lock:
                    failures.append({"draw": draw_index, "error": result["error"]})
                return
            value = _get_metric(result, metric)
            with lock:
                samples.append(value)
        except Exception as exc:  # isolated per-draw failure
            with lock:
                failures.append({"draw": draw_index, "error": str(exc)})
        finally:
            if conn_factory is not None and draw_conn is not None:
                try:
                    draw_conn.close()
                except Exception:
                    pass

    if conn_factory is not None and max_workers > 1 and n > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(_draw, range(n)))
    else:
        for i in range(n):
            _draw(i)

    if not samples:
        return {
            "mean": None,
            "p5": None,
            "p50": None,
            "p95": None,
            "std": None,
            "n": n,
            "failures": failures,
            "samples": [],
        }

    arr = np.asarray(samples, dtype=float)
    return {
        "mean": float(np.mean(arr)),
        "p5": float(np.percentile(arr, 5)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "std": float(np.std(arr)),
        "n": n,
        "failures": failures,
        "samples": samples,
    }


def resolve_clash(
    attacker_strength: float,
    defender_strength: float,
    *,
    model: str = "ratio",
    rng: Optional[np.random.Generator] = None,
    n: int = 1,
    attacker_sd: float = 0.0,
    defender_sd: float = 0.0,
) -> Dict[str, float]:
    """Resolve a two-sided clash and return outcome probabilities.

    Modeled on a Combat Results Table: relative strength drives the probability
    that the attacker prevails, the defender holds, or both are degraded
    (mutual loss). This is generic and non-military -- attacker/defender strengths
    can be any domain (shock severity vs. reserve adequacy, pest pressure vs.
    intervention efficacy, competitor strength vs. location resilience).

    Args:
        attacker_strength: Positive scalar for the attacking side.
        defender_strength: Positive scalar for the defending side.
        model: "ratio" (logistic mapping of attacker/defender) is the only
            supported model.
        rng: Optional RNG for stochastic draws (strengths perturbed by sd).
        n: Number of stochastic draws to average over (1 = deterministic).
        attacker_sd / defender_sd: Stdev of per-draw strength perturbation.

    Returns:
        {"attacker_win_p", "defender_hold_p", "mutual_p",
         "expected_attacker_loss", "expected_defender_loss"}
    """
    if model != "ratio":
        raise ValueError(f"Unknown clash model: {model!r}")

    def _single() -> Dict[str, float]:
        a = attacker_strength
        d = defender_strength
        if rng is not None:
            if attacker_sd > 0:
                a = max(0.0, rng.normal(attacker_strength, attacker_sd))
            if defender_sd > 0:
                d = max(0.0, rng.normal(defender_strength, defender_sd))
        eps = 1e-9
        ratio = a / (d + eps)
        # Sharpened logistic mapping of log-ratio (k=2): ratio 1 -> 0.5,
        # ratio 8 -> ~0.98 (clearly dominant attacker), ratio 0.125 -> ~0.02.
        attacker_win_p = 1.0 / (1.0 + np.exp(-2.0 * np.log(ratio)))
        defender_hold_p = 1.0 - attacker_win_p
        # Mutual-loss probability rises as the clash is closely contested.
        mutual_p = 4.0 * attacker_win_p * defender_hold_p
        expected_attacker_loss = defender_hold_p * (1.0 - 0.5 * mutual_p)
        expected_defender_loss = attacker_win_p * (1.0 - 0.5 * mutual_p)
        return {
            "attacker_win_p": float(attacker_win_p),
            "defender_hold_p": float(defender_hold_p),
            "mutual_p": float(mutual_p),
            "expected_attacker_loss": float(expected_attacker_loss),
            "expected_defender_loss": float(expected_defender_loss),
        }

    if n <= 1 or rng is None:
        return _single()

    acc: Dict[str, float] = {
        "attacker_win_p": 0.0,
        "defender_hold_p": 0.0,
        "mutual_p": 0.0,
        "expected_attacker_loss": 0.0,
        "expected_defender_loss": 0.0,
    }
    for _ in range(n):
        r = _single()
        for k in acc:
            acc[k] += r[k]
    return {k: v / n for k, v in acc.items()}


def clash_sweep(
    scenarios: Sequence[Dict[str, Any]],
    *,
    max_workers: int = DEFAULT_MAX_WORKERS,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Resolve many clashes concurrently.

    Each scenario is a dict that must contain ``attacker_strength`` and
    ``defender_strength`` (plus optional ``model``, ``attacker_sd``,
    ``defender_sd``, ``label``). Returns a list of per-scenario results enriched
    with the original label. Draws run under a bounded pool; a failing scenario is
    recorded under ``error`` and never aborts the sweep.
    """
    results: List[Optional[Dict[str, Any]]] = [None] * len(scenarios)
    lock = threading.RLock()

    def _resolve(idx: int, scenario: Dict[str, Any]) -> None:
        try:
            rng = np.random.default_rng(None if seed is None else seed + idx)
            outcome = resolve_clash(
                float(scenario["attacker_strength"]),
                float(scenario["defender_strength"]),
                model=scenario.get("model", "ratio"),
                rng=rng,
                n=int(scenario.get("n", 1)),
                attacker_sd=float(scenario.get("attacker_sd", 0.0)),
                defender_sd=float(scenario.get("defender_sd", 0.0)),
            )
            outcome["label"] = scenario.get("label", str(idx))
            with lock:
                results[idx] = outcome
        except Exception as exc:
            with lock:
                results[idx] = {"label": scenario.get("label", str(idx)), "error": str(exc)}

    if max_workers > 1 and len(scenarios) > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(lambda i: _resolve(i, scenarios[i]), range(len(scenarios))))
    else:
        for i, sc in enumerate(scenarios):
            _resolve(i, sc)

    return [r for r in results if r is not None]
