# MiCA Compliance Pack (KI-11)

**Classification:** Internal · **Prerequisite from:** KI-10 (`control-mapping.md`)
**Scope:** Preliminary MiCA perimeter controls for Kokonut Intelligence.
**Not:** legal advice, CASP authorization, or a license to issue crypto-assets.

## Principle (from KI-11 assessment)

> Keep farms and MRV outside the regulated perimeter. Use an *authorised EU
> CASP* for custody/exchange/execution. Classify every token before EU
> offering. Never issue ARTs/EMTs — use an authorised provider.

## What this pack delivers (v1.1 scope)

1. **`services/compliance/mica.py`** — code-level asset classification enum +
   `classify()` / `assert_perimeter()` guardrail. Every token-like instrument
   in the codebase is inventoried and tiered.
2. **Asset inventory** (discovered in code):

| Instrument | Code location | Preliminary concern |
|---|---|---|
| KokonutCreditToken | `contracts/src/KokonutCreditToken.sol` | Issuance review (non-transferable) |
| Guild Points | `contracts/script/DeployKokonutGuildPoints.s.sol` | Low (non-transferable) |
| Credit basket | `services/credit_class/basket.py` | High (fungible DLT) |
| Credit marketplace | `services/credit_class/marketplace.py` | CASP scope (sell/escrow) |
| `$vKKN` governance | guilds / KGP | Issuance review |
| `cusd` denom | `services/credit_class/params.py` | Prohibited as own EMT |
| Farm MRV / attestations | — | Outside MiCA |

3. **Disclosure-pack template** (`disclosure-pack.md`) — per-asset issuer,
   rights, risks, tech, governance, supply, redemption, environmental claims,
   conflicts, complaints. Fill per eligible asset before any EU offering.

4. **EU perimeter controls checklist** (`perimeter-controls.md`) — geofencing,
   KYC/AML, sanctions, Travel Rule, suitability warnings, incident response,
   immutable records.

## Out of scope (explicit follow-ups, not blockable in v1.1)

- Actual CASP authorization / EU passporting (requires licensed partner)
- Full KYC/AML, sanctions, transaction-monitoring, Travel Rule workflows
- DORA-grade ICT risk for regulated activity
- Legal classification sign-off (human + counsel)

## Guardrail usage

```python
from services.compliance.mica import assert_perimeter
assert_perimeter("credit_basket")   # raises PermissionError -> blocks EU path
```

CI test: `tests/test_mica_classification.py` asserts `cusd` is PROHIBITED and
`farm_mrv` is outside perimeter.
