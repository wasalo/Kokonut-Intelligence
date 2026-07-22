# Evidence Maturity

Kokonut uses a 0–6 evidence maturity reference model for records that describe
claims, measurements, outcomes, scorecards, and supporting evidence. Maturity
is one governance dimension, not a universal publication switch.

Publication decisions also depend on lifecycle status, public flags, evidence
links, consent, registry eligibility, metric verification, claim type, external
verification, methodology, and (where applicable) attestation state.

## Canonical Reference Table

The reference table is `evidence_maturity_level`, defined in
`schemas/postgres/029_impact_accountability_foundation.sql`.

| Level | Key | Label | Public Claim Allowed | External Verification Required |
|------:|-----|-------|----------------------|--------------------------------|
| 0 | `narrative_only` | Narrative only | No | No |
| 1 | `self_reported` | Self-reported record | No | No |
| 2 | `structured_record` | Structured record | No | No |
| 3 | `reviewed_record` | Reviewed record | No | No |
| 4 | `evidence_linked` | Evidence-linked record | Yes | No |
| 5 | `attested_record` | Attested record | Yes | No |
| 6 | `externally_verified` | Externally verified record | Yes | Yes |

The database constrains `level` to 0–6 and stores `level_key`, `label`,
`description`, `public_claim_allowed`, `requires_external_verification`, and
creation metadata.

### Interpretation

- **Level 0:** no source record or structured evidence; narrative only.
- **Level 1:** a self-reported observation or feedback record.
- **Level 2:** structured record with required fields.
- **Level 3:** record reviewed by a human or responsible reviewer.
- **Level 4:** reviewed record linked to evidence such as a CID, hash, or URL.
- **Level 5:** evidence-linked record with an on-chain or off-chain attestation.
- **Level 6:** external or third-party verification with a methodology reference
  and verifier reference.

Level 5 attestation does not equal external verification. An attestation proves
that a statement was attested according to the relevant schema and resolver;
it does not independently prove the underlying measurement or methodology.

## Maturity Is Not Lifecycle

Do not overload these concepts:

| Concept | Meaning |
|---------|---------|
| Evidence maturity | Strength and provenance of supporting evidence |
| `status` | Governed lifecycle, usually draft/submitted/verified/published/rejected |
| `verified` | A table-specific verification flag, especially `metric_value` |
| `public_claim` | Whether a claim is intended for public publication |
| Public-safe flag | Whether a score/evidence row is eligible for public output |
| Consent | Whether a stakeholder signal may be used or published |
| Attestation | On-chain/off-chain attestation metadata and state |
| Registry eligibility | Whether a location has a verified/published farm registry record |
| External verification | Independent verification and methodology reference |

Raising maturity does not automatically publish a record. Publishing does not
automatically establish external verification. An attestation does not
automatically establish maturity 5 or 6 on every object.

## Object-Specific Publication Gates

There is no single platform-wide rule that every public view uses the same
maturity threshold.

| Object/output | Effective gate |
|---------------|----------------|
| Ordinary public `impact_claim` | `public_claim = TRUE`, `status = published`, maturity ≥4, registry-backed location |
| Public carbon `impact_claim` | Published, maturity 6, `claim_category = carbon`, `claim_type = third_party_verified_claim`, external verifier, methodology reference |
| Public MRV carbon claim | Applicable public carbon type, maturity 6, external verifier, methodology reference |
| Published `carbon_credit` | Maturity 6, external verifier, methodology reference; public inventory also requires published status and registry-backed location |
| Public EBF score | Maturity ≥4, evidence link/row, `public_score_allowed = TRUE`; carbon pillar requires level 6 and qualifying carbon claim |
| Public EBF scorecard | Published, scorecard maturity ≥4, public flag, seven public pillars, pillar maturity ≥4, evidence rows, registry-backed location |
| Stakeholder feedback | Explicit consent, public consent scope, published status, non-empty `public_summary`; no universal maturity ≥4 requirement |
| Stakeholder outcome | Lifecycle and source-specific gates; no universal Level 4 public-claim constraint |
| Public metric summary | Active metric definition, `metric_value.verified = TRUE`, active location, registry-backed location; no maturity field in the base metric tables |
| Attestation summary | Verified/published Celo attestation and registry-backed location; attestation records do not carry maturity |
| Report snapshot | Lifecycle-governed report output; no universal base-schema maturity gate |
| CIDS export | Verified/published source records with maturity labels where available; not a universal publication gate |
| RDF evidence chain | Evidence and location are sufficient for chain-validity helper; not a maturity or publication gate |

## Impact And MRV Claims

### `impact_claim`

`impact_claim` stores evidence CIDs/hashes, maturity, attestation UID, public
claim intent, methodology, verifier, lifecycle, and review data.

Database and Directus behavior requires for ordinary public claims:

- `public_claim = TRUE`;
- `status = 'published'`;
- `evidence_maturity >= 4`;
- an eligible location/registry for public views.

Carbon claims additionally require:

- `evidence_maturity = 6`;
- `claim_category = 'carbon'`;
- `claim_type = 'third_party_verified_claim'`;
- `external_verifier`;
- `methodology_ref`.

The Directus impact-claim hook defaults maturity to 1, validates these public
conditions, and stamps reviewer fields on verification/publication/rejection.
The generic ordinary public claim path does not universally require an evidence
URL/CID/hash; maturity and object-specific evidence rules must be checked.

### `mrv_claim`

MRV claims include JSON claim data, source record IDs, evidence URLs/hashes,
attestation fields, lifecycle, `evidence_maturity`, `public_claim`, verifier,
and methodology. The database applies Level 6/verifier/methodology conditions
to specified public carbon-like claim types. It does not impose one universal
Level 4 public-MRV constraint equivalent to `impact_claim`.

## Carbon Evidence

### Carbon Credits

`carbon_credit` stores maturity, verifier, methodology, attestation linkage, and
lifecycle state. Publication requires:

- exactly maturity 6;
- non-empty external verifier;
- non-empty methodology reference.

The public carbon inventory additionally requires published status and a
verified or published farm registry record. Retirement is a separate governed
flow: the credit quantity is reserved first, then a separate reviewer confirms,
rejects, or cancels the retirement request.

### Carbon EBF Scores

Public carbon pillar scores require:

- score maturity exactly 6;
- evidence link;
- `public_score_allowed = TRUE`;
- a linked published carbon impact claim;
- `claim_type = 'third_party_verified_claim'`;
- external verifier;
- methodology reference.

Level 6 is therefore a necessary condition, not the complete publication gate.

## EBF Scorecards

EBF scorecard fields include:

- `ebf_scorecard.evidence_maturity_level`;
- `ebf_scorecard.public_claim_allowed`;
- `ebf_score.evidence_maturity_level`;
- `ebf_score.public_score_allowed`;
- `ebf_score_evidence.evidence_maturity_level`;
- `ebf_score_evidence.source_is_public_safe`.

The public scorecard views require:

1. published scorecard;
2. scorecard maturity ≥4;
3. `public_claim_allowed = TRUE`;
4. seven pillar rows;
5. public-enabled pillar scores;
6. pillar maturity ≥4;
7. evidence row/link for each public pillar;
8. verified or published farm registry.

Public carbon pillars use the stricter Level 6 carbon gate above. The database
view checks the score's maturity and evidence-row existence; it does not itself
require the linked evidence row's maturity field to be ≥4.

Reusable helpers in `services/scoring/gates.py` are advisory building blocks.
They do not reproduce every database view join, including lifecycle, registry,
seven-pillar completeness, and all carbon claim requirements.

## Stakeholder Evidence

`stakeholder_feedback.evidence_maturity` is available, but public feedback is
primarily governed by:

- explicit consent;
- public consent scope;
- `status = 'published'`;
- non-empty `public_summary`.

The public feedback view does not impose maturity ≥4. It exposes a maturity
label alongside its consent and publication gates.

`stakeholder_outcome.evidence_maturity` is also stored, but it has no universal
Level 4 public-claim constraint. CIDS export includes maturity labels for
outcomes and feedback where available; export inclusion is not equivalent to a
universal public maturity gate.

## Metrics, Attestations, Reports, And RDF

### Metrics

The base `metric_definition` and `metric_value` tables do not carry evidence
maturity. Public metric summaries require an active definition, a verified
metric value, an active location, and a verified/published farm registry.
Metric computation creates draft/unverified rows; human verification is a
separate action.

### Attestations

`attestation_record` does not carry an evidence-maturity column. Attestation
summaries use lifecycle, chain, revocation, expiry, and registry conditions.
An attestation may support a maturity-5 interpretation for a specific claim, but
the claim's maturity field and object-specific gates remain authoritative.

### Report Snapshots

`report_snapshot` is lifecycle-governed and can embed maturity-bearing claims,
but the base table has no universal report-level maturity gate. Report
generation may identify evidence gaps such as public claims below Level 4,
carbon claims below Level 6, or missing CID/hash/attestation links.

### CIDS

`services/registry/cids_export.py` emits maturity fields such as
`kokonut:evidenceMaturity` and `kokonut:evidenceMaturityLabel` for supported
records. It queries verified/published source records but is primarily a
provenance/export layer, not a complete public-claim gate.

### RDF

`services/rdf/evidence_chain.py` can consider a chain valid when it has evidence
and location. That helper does not require maturity ≥4, Level 6 carbon gates,
published status, verifier, or methodology. RDF evidence-chain validity must not
be described as equivalent to publication approval.

## CRISP And Other Maturity-Bearing Records

CRISP assessments and dimension records carry FK-backed maturity fields, usually
defaulting to Level 1. CRISP uses maturity as assessment metadata and confidence
context; it does not automatically apply the `impact_claim` Level 4/6 gates to
CRISP outputs.

Other maturity-bearing domains include regenerative outcomes, capital and GNH
records, bio-factory records, soil/field evidence, regional readiness, strategy
evidence, solution lifecycle, and relationship entities. Their public views may
use different thresholds, including Level 3, or separate lifecycle/consent
rules. Always inspect the owning schema and public view.

## Agent Boundaries

Agents cannot directly verify or publish governed records. For EBF scorecards and
scores specifically, `services/agents/safety.py` prevents agents from raising
maturity above Level 3 and denies publication transitions.

This is not a universal statement that agents can never write any maturity field
on every collection. Collection-specific safety rules apply. Agent-generated
summaries and evidence-gap reports remain draft inputs for human review and do
not establish maturity.

## What Maturity Does Not Prove

Evidence maturity alone does not prove:

- that a record is published;
- that a metric is verified;
- that an attestation transaction succeeded;
- that an attester independently verified the underlying measurement;
- that a carbon claim has an external verifier or methodology;
- that a stakeholder signal was consented for public use;
- that a location is registry-eligible;
- that an RDF evidence chain is publication-safe;
- that a model output is accurate or predictive.

## Tests And Source References

Relevant tests include:

- `tests/test_ebf_gates.py`
- `tests/test_ebf_carbon_gates.py`
- `tests/test_ebf_public_views.py`
- `tests/test_ebf_p0.py`
- `tests/test_ebf_p1.py`
- `tests/test_ebf_p2.py`
- `tests/test_ebf_agent_safety.py`
- `tests/test_cids_export.py`
- `tests/test_carbon_credits.py`
- `tests/test_platform_done.py`
- `extensions/kokonut-hooks/src/workflow.test.ts`
- `extensions/kokonut-hooks/src/schemas.test.ts`

Canonical implementation references:

- `schemas/postgres/029_impact_accountability_foundation.sql`
- `schemas/postgres/030_stakeholder_feedback.sql`
- `schemas/postgres/031_impact_claims_and_cids.sql`
- `schemas/postgres/032_ebf_scorecard.sql`
- `schemas/postgres/078_carbon_credits.sql`
- `services/scoring/gates.py`
- `services/registry/cids_export.py`
- `services/rdf/evidence_chain.py`
- `services/agents/safety.py`
- `extensions/kokonut-hooks/src/impact-claim.ts`
- `extensions/kokonut-hooks/src/feedback.ts`
