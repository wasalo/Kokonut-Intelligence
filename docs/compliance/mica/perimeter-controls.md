# EU Perimeter Controls — Checklist (KI-11)

Applied when a classified asset is offered to EU users. Companion to
`services/compliance/mica.py` `assert_perimeter()`.

## Required before EU offering

- [ ] Legal classification completed per asset (counsel sign-off)
- [ ] Disclosure pack filled (`disclosure-pack.md`)
- [ ] Authorised EU CASP engaged for custody/exchange/execution/transfer
- [ ] `assert_perimeter()` passes in code (no PROHIBITED/HIGH without controls)
- [ ] Geofencing where required (do not serve restricted jurisdictions)

## KYC / AML / Sanctions

- [ ] Identity verification (KYC) for EU-facing accounts
- [ ] Sanctions screening on addresses + counterparties
- [ ] Transaction monitoring for suspicious activity
- [ ] Travel Rule (originator/beneficiary) on transfers ≥ threshold
- [ ] Suspicious-activity reporting workflow

## Investor protection

- [ ] Suitability / risk warning shown pre-transaction
- [ ] Investor communications logged (immutable)
- [ ] Complaints handling process published
- [ ] Conflicts-of-interest policy in place

## Operational resilience (DORA-aligned, where regulated)

- [ ] ICT risk register (see `risk-register.md`)
- [ ] Incident response (see `workflow-emergency-incident.md`)
- [ ] Outsourcing controls for CASP / stablecoin provider

## Prohibitions (hard)

- [ ] Platform does NOT issue its own ART or EMT — uses authorised provider
- [ ] `cusd` never represented as platform-issued e-money
- [ ] `$vKKN` "1:1 coconut tree" claim not used in EU marketing without review
