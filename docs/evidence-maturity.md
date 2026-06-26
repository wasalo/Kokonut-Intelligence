# Evidence Maturity

Kokonut uses a 0-6 evidence maturity model across impact claims, MRV claims, stakeholder feedback, and public reporting.

| Level | Key | Public Claim | Meaning |
|---:|---|---|---|
| 0 | `narrative_only` | No | Narrative without structured evidence. |
| 1 | `self_reported` | No | Self-reported observation or feedback. |
| 2 | `structured_record` | No | Structured record with required fields. |
| 3 | `reviewed_record` | No | Human-reviewed record. |
| 4 | `evidence_linked` | Yes | Reviewed record with CIDs, hashes, or evidence URLs. |
| 5 | `attested_record` | Yes | Evidence-linked record with attestation. |
| 6 | `externally_verified` | Yes | Externally verified record with methodology and verifier reference. |

## Public Carbon Claims

Public carbon claims require Level 6. Level 5 EAS attestation proves a claim was attested, but does not equal external verification.

## Review Use

- Levels 0-3 are internal or pre-publication evidence states.
- Level 4 is the minimum maturity for ordinary public impact claims.
- Level 5 records may include onchain/offchain attestations, but still need reviewer interpretation.
- Level 6 is required when a public carbon claim could be read as externally verified.

## Enforced Locations

Evidence maturity is enforced or surfaced in:

- `mrv_claim`
- `impact_claim`
- `stakeholder_feedback`
- `stakeholder_outcome`
- public-safe views
- report snapshots
- CIDS export
- Directus workflow hooks

## Agent Use

Agents may summarize evidence maturity and identify gaps. They cannot raise maturity, verify records, or publish claims. Any agent-produced summary is a draft input for human review.
