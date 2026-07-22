# Common Foundations Checklist

Use this checklist before publishing impact claims, report snapshots, or Green Paper evidence.

## 1. Useful Questions

- What decision will this evidence support?
- Who benefits from answering the question?
- Does the claim avoid implying more certainty than the evidence supports?

### Implementation context

Every governed record — claims, metrics, feedback, scorecards — should trace back to a question worth answering. The checklist enforces this by requiring source lineage fields (`source_system`, `source_id`, `source_raw`) on `mrv_claim`, `impact_claim`, `harvest_event`, `revenue_event`, and `expense_event`. Reports without lineage are flagged as `CLAIM_BELOW_PUBLICATION_THRESHOLD` by the report generator.

## 2. Stakeholder Involvement

- Which stakeholder groups are affected?
- Are stakeholder outcomes recorded separately where experience differs?
- Is stakeholder feedback consented before public use?

### Implementation context

Stakeholder outcomes live in `stakeholder_outcome` with fields for `stakeholder_group`, `importance`, `importance_perspective`, and `is_underserved`. Each outcome maps to an `impact_framework` dimension via `framework_key`, `dimension_key`, and `sdg_number`.

Stakeholder feedback is **private by default**. Public export requires:
- `consent_given = TRUE`
- `public_consent_scope` set to a public-safe value
- `status = 'published'`
- A non-empty `public_summary`

The feedback synthesis agent (`services/agents/feedback_agent.py`) uses public summaries and aggregates private/no-consent signals; it never exposes raw private feedback.

## 3. Feasible Data

- Are source records available in PostgreSQL/Directus?
- Are source lineage fields populated?
- Is evidence maturity appropriate for the intended use?

### Implementation context

Source records must be canonical PostgreSQL/Directus rows. Key source tables:

| Table | Role |
|---|---|
| `mrv_claim` | MRV claims with evidence maturity, external verifier, methodology ref |
| `impact_claim` | Impact claims with claim type/category, evidence CID/hash, attestation UID |
| `stakeholder_feedback` | Stakeholder feedback with consent fields and evidence maturity |
| `stakeholder_outcome` | Stakeholder outcomes with importance, framework mapping |
| `metric_value` | Verified metric values linked to metric definitions |
| `metric_definition` | Governed metric definitions with validation tests and report usage |

Evidence maturity must match the intended use. Internal reports accept levels 0–3. Public reports require level 4 or higher. Public carbon claims require level 6.

## 4. Sense-Making

- Has a human reviewer interpreted the result in context?
- Are limitations and negative findings documented?
- Are private/no-consent signals aggregated rather than exposed?

### Implementation context

The report generator (`services/export/report_generator.py`) attaches a `public_interest` section to every report snapshot with four fields:

| Field | Purpose |
|---|---|
| `public_interest_summary` | Contextual interpretation for non-technical readers |
| `uncertainty_notes` | Caveats about data quality, sample size, or methodology |
| `negative_findings` | JSONB array of limitations, gaps, and contradictory evidence |
| `affected_community_voice` | Direct quotes or summaries from affected stakeholders (when consented) |

`build_negative_findings()` in `report_generator.py` queries evidence gaps, public claims below maturity thresholds, and carbon claims below Level 6 to produce balanced, non-cherry-picked reports.

## 5. Reporting

- Does the public report include evidence maturity labels?
- Are carbon claims clearly separated from carbon credit issuance?
- Are public-interest fields populated on `report_snapshot`?

### Implementation context

Every public-facing report must include evidence maturity labels. The CIDS exporter (`services/registry/cids_export.py`) emits `kokonut:evidenceMaturity` and `kokonut:evidenceMaturityLabel` on every `cids:ImpactReport` entry.

Carbon claims are distinct from carbon credit issuance. Public carbon claims require:
- `evidence_maturity = 6`
- `claim_type = 'third_party_verified_claim'`
- Non-empty `external_verifier`
- Non-empty `methodology_ref`
- `status = 'published'`

This is enforced by the `chk_mrv_public_carbon_level6` database constraint on `mrv_claim`.

## 6. Learning

- Did review produce a proposed metric, workflow change, or operational action?
- Are rejected or needs-info findings retained for rework?
- Is the next reporting cycle able to improve data quality?

### Implementation context

Participatory metric proposals use a separate lifecycle: `proposed → discussed → approved → implemented → deprecated → rejected` (on `metric_proposal` table). Approval requires a minimum 30-day discussion period.

Rejected or needs-info findings are retained in governed tables with their full history. The `metric_version` table tracks formula changes for each metric definition, enabling audit trails across reporting cycles.

## 7. Evidence maturity model

The `evidence_maturity_level` table defines levels 0–6:

| Level | Key | Label | Public claims | Requires external verification |
|---|---|---|---|---|
| 0 | `narrative_only` | Narrative only | no | no |
| 1 | `self_reported` | Self-reported record | no | no |
| 2 | `structured_record` | Structured record | no | no |
| 3 | `reviewed_record` | Reviewed record | no | no |
| 4 | `evidence_linked` | Evidence-linked record | yes | no |
| 5 | `attested_record` | Attested record | yes | no |
| 6 | `externally_verified` | Externally verified record | yes | yes |

### Enforcement locations

Evidence maturity is enforced or surfaced in:

- `mrv_claim` — via `chk_mrv_public_carbon_level6` constraint
- `impact_claim` — public-safe view requires maturity ≥ 4
- `stakeholder_feedback` — public-safe view requires consent + maturity
- `stakeholder_outcome` — public-safe view requires maturity
- EBF scorecards — via `chk_ebf_scorecard_public_maturity` and `chk_ebf_score_public_maturity`
- report snapshots — public-interest fields populated by report generator
- CIDS export — `kokonut:evidenceMaturity` on every ImpactReport
- Directus workflow hooks — lifecycle enforcement

## 8. Public carbon claim constraints

The `chk_mrv_public_carbon_level6` constraint on `mrv_claim` enforces:

```sql
NOT (public_claim = TRUE AND claim_type IN ('carbon', 'carbon_credit', ...))
OR (
    evidence_maturity = 6
    AND NULLIF(TRIM(COALESCE(external_verifier, '')), '') IS NOT NULL
    AND NULLIF(TRIM(COALESCE(methodology_ref, '')), '') IS NOT NULL
)
```

This means: if a claim is public AND carbon-related, it MUST have maturity Level 6, a non-empty external verifier, and a non-empty methodology reference. EAS attestation alone is Level 5 and is not sufficient for public carbon claims.

The same gate is enforced in Python by `public_carbon_score_allowed()` and `linked_carbon_claim_allowed()` in `services/scoring/gates.py`.

## 9. Agent safety constraints

Schema 029 adds two database-level constraints that prevent agents from publishing their own outputs:

### `chk_ai_summary_agent_draft_only`

```sql
created_by IS NULL OR status IN ('draft', 'submitted', 'rejected')
```

Agent-created `ai_summary` rows cannot reach `verified` or `published` status.

### `chk_agent_task_draft_submit_only`

```sql
review_status IN ('draft', 'submitted', 'rejected')
```

Agent `task_type` rows cannot reach `verified` or `published` review status.

These constraints complement the Python-level enforcement in `services/agents/safety.py` (`GOVERNED_COLLECTIONS`, `HIGH_RISK_ACTIONS`) and the Directus hook rules in `extensions/kokonut-hooks/src/agent-safety.ts`.

## 10. Dashboards

### Evidence Gap Dashboard

`dashboards/metabase/sql/20_evidence_gap_dashboard.sql` — queries `v_public_impact_claim_summary` to surface claims needing stronger evidence, ordered by maturity level.

### Stakeholder Feedback Dashboard

`dashboards/metabase/sql/21_stakeholder_feedback_dashboard.sql` — public-safe stakeholder feedback review with consent and maturity filtering.

Use both dashboards before publishing Green Paper materials. Claims with missing evidence links, public claims below maturity thresholds, or carbon claims below Level 6 should be treated as review items rather than public proof.

## 11. Related documentation

| Document | Purpose |
|---|---|
| `docs/evidence-maturity.md` | Full 0–6 maturity model with review guidance |
| `docs/reporting-principles.md` | Public-interest defaults and report snapshot fields |
| `docs/public-report-disclaimer.md` | Standard, carbon, and privacy disclaimers |
| `docs/cids-mapping.md` | CIDS export compatibility layer |
| `docs/agent-safety.md` | Agent enforcement architecture and task catalogue |
| `docs/agent-access.md` | Role permissions and enforcement layers |
| `docs/green-paper.md` | Section 15: Common Foundations Checklist (canonical source) |
