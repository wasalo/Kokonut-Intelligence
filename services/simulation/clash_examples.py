"""Advisory clash examples built on the tactical-wargame clash primitive.

These helpers translate platform data into two-sided clash resolutions. The
"attacker" is always a shock / threat / pressure signal; the "defender" is always
a buffer / reserve / intervention. Stakeholders and communities are NEVER modelled
as opposing forces (see AGENTS.md: anti-capture governance).

All functions are READ-ONLY: they query, resolve, and return probabilities. They
do not write governed state.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.common.logging import get_logger

from .resolution import resolve_clash

logger = get_logger(__name__)

_SEVERITY_SCALE = {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}


def _severity_to_strength(severity: str, probability: float) -> float:
    base = _SEVERITY_SCALE.get(str(severity).lower(), 1.0)
    return base * max(0.0, float(probability))


def stress_reserve(
    conn: Any,
    location_id: str,
    *,
    reserve_code: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve shock-threat pressure against strategic-reserve adequacy.

    ADVISORY-ONLY. Builds attacker strength from active high/critical threat flags
    at the location (severity x probability) and defender strength from the chosen
    reserve's adequacy percentage. Returns the clash outcome probabilities.

    Args:
        conn: DB connection (read-only use).
        location_id: Location to assess.
        reserve_code: Reserve to test (defaults to the first reserve found).
        seed: RNG seed for reproducibility of the stochastic clash.

    Returns:
        {"reserve_code", "attacker_strength", "defender_strength", "clash"}
    """
    from services.strategic_reserve import health as reserve_health

    # Defender: reserve adequacy (0-100+ scale).
    health = reserve_health.reserve_health(conn)
    reserves = health.get("reserves", [])
    if reserve_code:
        target = next((r for r in reserves if r.get("reserve_code") == reserve_code), None)
    else:
        target = next((r for r in reserves), None)
    defender_strength = float(target.get("adequacy", {}).get("adequacy_pct") or 0) if target else 0.0
    chosen_code = target.get("reserve_code") if target else reserve_code

    # Attacker: aggregate active high/critical threat flags at the location.
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tf.severity_potential, tf.probability, t.probability AS threat_prob
        FROM threat_flag tf
        JOIN threat t ON t.id = tf.threat_id
        WHERE t.location_id = %s
          AND tf.status = 'active'
          AND tf.severity_potential IN ('high', 'critical')
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    cur.close()

    attacker_strength = 0.0
    for severity, flag_prob, threat_prob in rows:
        p = float(flag_prob or 0) * float(threat_prob or 0)
        attacker_strength += _severity_to_strength(severity, p)

    import numpy as np

    rng = np.random.default_rng(seed)
    clash = resolve_clash(
        attacker_strength,
        defender_strength,
        model="ratio",
        rng=rng,
        n=200,
        attacker_sd=max(0.1, attacker_strength * 0.15),
        defender_sd=max(0.5, defender_strength * 0.1),
    )

    return {
        "reserve_code": chosen_code,
        "attacker_strength": round(attacker_strength, 3),
        "defender_strength": round(defender_strength, 3),
        "clash": clash,
    }


def pest_vs_intervention(
    conn: Any,
    location_id: str,
    *,
    pest: str,
    pressure: float,
    intervention_efficacy: float,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Resolve pest pressure against an intervention's efficacy.

    ADVISORY-ONLY. A generic two-sided clash: attacker = pest pressure (count-scaled),
    defender = intervention efficacy (0-1). Returns clash probabilities.

    Args:
        conn: DB connection (kept for call-site symmetry; not queried here).
        location_id: Location context (for reporting only).
        pest: Pest identifier (for reporting).
        pressure: Observed pest pressure scalar (>= 0).
        intervention_efficacy: Efficacy of the planned intervention (0-1).
        seed: RNG seed for reproducibility.

    Returns:
        {"location_id", "pest", "attacker_strength", "defender_strength", "clash"}
    """
    import numpy as np

    attacker_strength = max(0.0, float(pressure))
    defender_strength = max(0.0, float(intervention_efficacy)) * 4.0  # scale to 0-4
    rng = np.random.default_rng(seed)
    clash = resolve_clash(
        attacker_strength,
        defender_strength,
        model="ratio",
        rng=rng,
        n=200,
        attacker_sd=max(0.05, attacker_strength * 0.15),
        defender_sd=max(0.05, defender_strength * 0.1),
    )
    return {
        "location_id": location_id,
        "pest": pest,
        "attacker_strength": round(attacker_strength, 3),
        "defender_strength": round(defender_strength, 3),
        "clash": clash,
    }
