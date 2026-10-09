"""Composite capital-accounting report builder (advisory)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .capacity import assess_capacity
from .capture import capture_risk
from .credit import credit_capacity, list_draft_credits
from .diversion import compute_diversion_index


def build_capital_accounting(
    conn,
    location_id: str,
    period_start: str = None,
    period_end: str = None,
) -> Dict[str, Any]:
    """Assemble the four capital-accounting lenses into one advisory dict."""
    sections: Dict[str, Any] = {}
    errors: list[str] = []

    try:
        sections["capacity"] = assess_capacity(conn, location_id)
    except Exception as exc:  # noqa: BLE001 - isolate per-section failure
        errors.append(f"capacity: {exc}")

    try:
        sections["diversion"] = compute_diversion_index(
            conn, location_id, period_start, period_end
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"diversion: {exc}")

    try:
        sections["capture_risk"] = capture_risk(conn, location_id)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"capture_risk: {exc}")

    try:
        sections["credit_ledger"] = {
            "draft_credits": list_draft_credits(conn, location_id),
            "capacity": credit_capacity(conn, location_id),
        }
    except Exception as exc:  # noqa: BLE001
        errors.append(f"credit_ledger: {exc}")

    return {
        "report_type": "capital_accounting",
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "advisory_only": True,
        "sections": sections,
        "errors": errors,
    }
