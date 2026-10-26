"""Feature gate for destructive data-governance retention enforcement."""

from __future__ import annotations

import os

DATA_RETENTION_ENFORCEMENT_ENV = "KOKONUT_FEATURE_DATA_RETENTION_ENFORCEMENT"


def data_retention_enforcement_enabled() -> bool:
    """Read the explicit destructive-retention switch without loading secrets."""
    return os.getenv(DATA_RETENTION_ENFORCEMENT_ENV, "false").strip().lower() == "true"


def require_data_retention_enforcement() -> None:
    """Fail closed until approved schedules and hold controls are ready."""
    if not data_retention_enforcement_enabled():
        raise RuntimeError(
            "Data retention enforcement is disabled. Set "
            f"{DATA_RETENTION_ENFORCEMENT_ENV}=true only after the "
            "jurisdiction-specific schedule is approved and legal-hold "
            "eligibility is enforced for the target records."
        )
