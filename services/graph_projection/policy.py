"""Publication policy for projected records."""

from __future__ import annotations

from datetime import date, datetime, timezone

PUBLIC_LIFECYCLES = frozenset({"verified", "published"})


def registry_is_public(row: dict) -> bool:
    return row.get("status") in PUBLIC_LIFECYCLES


def metric_value_is_public(row: dict, eligible_locations: set[str]) -> bool:
    location_id = row.get("location_id")
    return bool(row.get("verified")) and bool(row.get("is_public_candidate")) and location_id is not None and str(location_id) in eligible_locations


def impact_claim_is_public(row: dict, eligible_locations: set[str]) -> bool:
    location_id = row.get("location_id")
    if location_id is None or str(location_id) not in eligible_locations:
        return False
    if row.get("status") != "published" or not row.get("public_claim"):
        return False
    expires_at = row.get("expires_at")
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        return False
    maturity = int(row.get("evidence_maturity") or 0)
    if maturity < 4:
        return False
    if row.get("claim_category") == "carbon":
        return (
            maturity == 6
            and row.get("claim_type") == "third_party_verified_claim"
            and bool(str(row.get("external_verifier") or "").strip())
            and bool(str(row.get("methodology_ref") or "").strip())
        )
    return True


def attestation_is_public(row: dict, eligible_locations: set[str]) -> bool:
    expiration_date = row.get("expiration_date")
    expires_at = row.get("expires_at")
    return (
        row.get("status") == "published"
        and row.get("chain") == "celo"
        and row.get("revocation_date") is None
        and (expiration_date is None or expiration_date >= date.today())
        and (expires_at is None or expires_at > datetime.now(timezone.utc))
        and row.get("location_id") is not None
        and str(row["location_id"]) in eligible_locations
    )
