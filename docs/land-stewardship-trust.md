# Kokonut Land Stewardship Trust Methodology

**Issue:** KI-9 · **Iteration:** v1.1-hardening · **Status:** methodology (no schema change)
**Grounded in:** Kokonut Network Framework (kokonut.network/mcp) + Kokonut Intelligence schema (this repo)

> The Land Stewardship Trust is not a new contract or a new table. It is a
> **governed operating procedure** that turns the Kokonut Framework's values
> into enforceable, replicable data — using schema that already exists in
> Kokonut Intelligence. Any farm adopting KI can implement this methodology
> without code changes; they only supply the records.

## 1. Why this exists (Framework grounding)

From the Kokonut manifesto and vision (queried via the Kokonut MCP):

> *"Kokonut Network exists to make regenerative agriculture fundable,
> governable, verifiable, and community-owned — without surrendering control
> to banks, corporations, foundations, or founders."*

The **Kokonut Framework** is the "operating system" that makes each farm
*comparable, fundable, governable, and verifiable*. The Land Stewardship Trust
is the Framework's land-tenure and community-benefit discipline made concrete
in data. It operationalizes three Framework commitments:

| Framework commitment | Trust mechanism |
|---|---|
| **Community-owned** | `land_stewardship_commitment` with `commons_trust_pathway` model |
| **Verifiable** | governed lifecycle `draft→verified→published` + EAS attestation |
| **Replicable** | 8 forms of capital + 13-field Common Data Schema, no custom code |

The Framework's **5 Principles of Regeneration** are the due-diligence filter
for every Trust record (soil disturbance, living cover, biodiversity, responsible
animals, living roots). The **4 development phases** (I–IV) define when each
Trust instrument is created.

## 2. The Trust instruments (all already in KI schema)

KI implements the Trust through these tables (no new migrations needed):

| Instrument | Table | Key fields | Framework phase |
|---|---|---|---|
| Land tenure commitment | `land_stewardship_commitment` | `stewardship_model` ∈ {community_stewardship, cooperative_use, **commons_trust_pathway**, lease_to_stewardship, customary_commons}, `anti_speculation_terms`, `commons_transition_path` | I–II |
| Capital alignment | `capital_alignment_assessment` | `commons_reinvestment_commitment_pct`, `extractive_risk_level`, `community_control_terms` | I–II |
| Regenerative outcomes | `regenerative_outcome_summary` | `hectares_restored`, `soil_carbon_delta_t_ha`, `regenerative_score`, `tree_survival_rate_pct` | II–IV |
| Community governance | `community_governance_mechanism` | `decision_method` ∈ {consensus, consent, steward_review}, `community_veto_rights` | II–III |
| Adaptive review | `adaptive_stewardship_review` | `stewardship_scope`, `trigger_thresholds`, `corrective_actions`, `next_review_date` | IV (continuous) |
| Replication readiness | `replication_readiness_assessment` | `readiness_score` (0–10), `replication_status` | III |

Every table carries the governed lifecycle (`status` CHECK) and is exposed
publicly only via `v_public_*` views that require `status='published'`,
`evidence_maturity >= 3`, **and** a verified `farm_registry_record`. That
last condition is the Trust's enforcement: *no public stewardship claim leaves
the platform without a registered, verified farm behind it.*

## 3. Procedure — how an adopting farm establishes the Trust

1. **Onboard (Phase I).** Create `location` + `farm` (13-field Common Data
   Schema). Run `capital_alignment_assessment` for each funding source; require
   `commons_reinvestment_commitment_pct > 0` and `extractive_risk_level !=
   critical` before `published`.
2. **Commit (Phase I→II).** Insert `land_stewardship_commitment` with
   `stewardship_model='commons_trust_pathway'`; populate `anti_speculation_terms`
   (e.g. "no sale to non-community entity without DAO review") and
   `commons_transition_path`. Insert `community_governance_mechanism` with
   `decision_method` and `community_veto_rights`.
3. **Produce & measure (Phase II–IV).** Quarterly `regenerative_outcome_summary`
   rows; annual `adaptive_stewardship_review` with `trigger_thresholds` (e.g.
   `tree_survival_rate_pct < 70` → corrective action required).
4. **Verify & publish.** Human runs `--verify-value`; only then `status` moves
   to `published` and the `v_public_*` view exposes it. Attest the published
   record to Celo EAS via `services/attestation` (resolver-gated).
5. **Replicate (Phase III).** When `replication_readiness_assessment.readiness_score >= 7`
   and `replication_status='ready_for_replication'`, the farm model is
   eligible for a new location — the Trust travels with the pattern.

## 4. Enforcement & guardrails (code-grounded)

- **Lifecycle gate:** `status` CHECK enforces `draft/submitted/verified/published/rejected`.
  Compute creates `draft`; a human verifies. (Per AGENTS.md operational integrity.)
- **Public gate:** `v_public_*` views join on `farm_registry_record.status IN
  ('verified','published')` — unregistered farms cannot publish Trust claims.
- **Anti-speculation:** `land_stewardship_commitment.anti_speculation_terms` is
  free text but required in the methodology; `commons_transition_path` must be
  non-null for `commons_trust_pathway`.
- **Capital discipline:** `commons_reinvestment_commitment_pct BETWEEN 0 AND 100`
  CHECK; ≤0 fails review.

## 5. Replicability checklist (for any KI adopter)

- [ ] `location`/`farm` created with 13-field schema
- [ ] `capital_alignment_assessment` passed (reinvestment > 0, risk ≤ high)
- [ ] `land_stewardship_commitment` = `commons_trust_pathway` with anti-speculation + transition path
- [ ] `community_governance_mechanism` with veto rights defined
- [ ] Quarterly `regenerative_outcome_summary`; annual `adaptive_stewardship_review`
- [ ] All `published` with `evidence_maturity >= 3` and verified `farm_registry_record`
- [ ] Published records attested to EAS

## 6. Out of scope

- Legal trust instrument / title transfer (jurisdiction-specific, outside KI)
- On-chain land title (future EAS extension, not in this methodology)
- MiCA treatment of any token (see KI-11 `services/compliance/mica.py`)

## 7. References

- Framework: kokonut.network/mcp — Introduction, 5 Principles of Regeneration,
  Development Phases, Common Data Schema, MRV methodology
- KI schema: `schemas/postgres/037_commons_liberation_and_stewardship.sql`,
  `039_regenerative_outcomes_and_stewardship.sql`, `001_locations.sql`,
  `013_prd_completion.sql` (farm_registry_record)
- Attestation: `services/attestation/` (EAS publisher, resolver-gated)
- Governance: `services/governance/` (Baal read-first adapter)
