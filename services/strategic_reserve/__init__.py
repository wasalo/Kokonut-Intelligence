"""Strategic Reserve layer for the Kokonut ecosystem.

Unifies existing reserve-shaped primitives (carbon buffer pool, commons
reserve allocation, funding-round capital, strategy contingency) into a
first-class, monitorable reserve registry. Read-only analytics plus a
human-approved release-proposal path — never an automatic on-chain drawdown.
"""

from __future__ import annotations

from . import health

__all__ = ["health"]
