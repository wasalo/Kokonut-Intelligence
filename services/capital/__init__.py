"""Capital accounting module (Keynes-inspired, constructive only).

Turns the 8 Forms of Capital from a static stock inventory into a dynamic
capital-accounting and deferred-credit system. All analytics are read-only and
advisory; governed writes (regenerative_credit_ledger and the assessment
tables) are restricted to status='draft' via services/agents/safety.py.

Concepts borrowed from Keynes, *How to Pay for the War*:
- Deferred Pay / compulsory savings -> regenerative_credit_ledger (a withheld
  claim on future regenerative output, redeemable later).
- Output capacity & national-income accounting -> capital_capacity_assessment.
- Consumption-vs-production diversion -> capital_diversion_observation.
- Managed containment (inflation analog) -> capital_capture_risk.
"""

from . import capacity, capture, credit, diversion

__all__ = ["capture", "capacity", "credit", "diversion"]
