"""MiCA asset classification — preliminary, code-level.

Supports KI-11 (MiCA Framework-Compliance). This is NOT legal advice and is
NOT a CASP authorization. It implements the *controlled operating model*
from the KI-11 assessment: every token-like instrument must be classified
before any EU offering, and the platform must never issue its own EMT/ART.

The enum + classify() give future issuance/settlement code a single gate:
route new instruments through classify() and refuse to proceed past the
`REQUIRES_LEGAL_REVIEW` / `PROHIBITED` tiers without human sign-off.

See docs/compliance/mica/ for the full disclosure-pack workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MicaConcern(Enum):
    """Preliminary MiCA perimeter concern for a platform instrument."""

    OUTSIDE = "outside_mica"          # MRV, analytics, attestations
    LOW = "low_risk"                  # non-transferable reputation
    ISSUANCE_REVIEW = "issuance_review"   # non-transferable DLT credit
    CASP_SCOPE = "casp_scope"         # tradable marketplace / credit
    HIGH = "high_risk"               # fungible redeemable basket
    PROHIBITED = "prohibited"         # ART/EMT issuance by platform


# Asset inventory discovered in code (services/credit_class, guilds)
ASSETS: dict[str, MicaConcern] = {
    "kokonut_credit_token": MicaConcern.ISSUANCE_REVIEW,   # non-transferable
    "guild_points": MicaConcern.LOW,                        # non-transferable
    "credit_basket": MicaConcern.HIGH,                      # fungible DLT basket
    "credit_marketplace": MicaConcern.CASP_SCOPE,           # sell/escrow/bridge
    "vKKN_governance": MicaConcern.ISSUANCE_REVIEW,         # needs classification
    "cusd_denom": MicaConcern.PROHIBITED,                   # do not issue as EMT
    "farm_mrv": MicaConcern.OUTSIDE,
    "attestation": MicaConcern.OUTSIDE,
}


@dataclass
class Classification:
    asset: str
    concern: MicaConcern
    eu_offerable: bool
    notes: str = ""
    required_controls: list[str] = field(default_factory=list)

    def blocks_without_human(self) -> bool:
        return self.concern in (
            MicaConcern.ISSUANCE_REVIEW,
            MicaConcern.CASP_SCOPE,
            MicaConcern.HIGH,
            MicaConcern.PROHIBITED,
        )


def classify(asset: str) -> Classification:
    """Return preliminary MiCA classification for a known platform instrument."""
    concern = ASSETS.get(asset, MicaConcern.ISSUANCE_REVIEW)
    controls: list[str] = []
    if concern == MicaConcern.OUTSIDE:
        eu_offerable = True
    elif concern == MicaConcern.LOW:
        eu_offerable = True
    elif concern == MicaConcern.ISSUANCE_REVIEW:
        eu_offerable = False
        controls = ["legal_classification", "disclosure_pack", "human_approval"]
    elif concern == MicaConcern.CASP_SCOPE:
        eu_offerable = False
        controls = ["authorised_casp", "kyc_aml", "travel_rule", "disclosure_pack"]
    elif concern == MicaConcern.HIGH:
        eu_offerable = False
        controls = ["legal_classification", "redemption_rules", "disclosure_pack",
                    "market_abuse_surveillance"]
    else:  # PROHIBITED
        eu_offerable = False
        controls = ["use_authorised_emt_provider", "never_issue_as_own"]
    return Classification(asset, concern, eu_offerable,
                          required_controls=controls)


def assert_perimeter(asset: str) -> None:
    """Raise if an asset cannot proceed to EU offering without human sign-off.

    Call this from issuance/settlement paths. It is a guardrail, not a
    compliance certification.
    """
    c = classify(asset)
    if c.blocks_without_human():
        raise PermissionError(
            f"MiCA perimeter: {asset} ({c.concern.value}) requires "
            f"human-approved controls: {', '.join(c.required_controls)}. "
            "Route through authorised EU CASP / legal review before EU offering."
        )
