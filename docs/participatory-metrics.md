# Participatory Metrics

Participatory metrics let farm operators, workers, advisors, and DAO reviewers propose measurements that are useful locally before they become governed platform metrics. The proposal is a governance record; it does not itself compute values, create a calculator, or publish a metric.

## Proposal Record

`metric_proposal` stores the proposal and its review context:

| Field | Purpose |
|---|---|
| `location_id` | Location scope; may be null for a platform-wide proposal |
| `proposed_by` | Proposer name or identifier |
| `proposed_by_role` | Proposer context, such as `farm_operator` |
| `proposal_date` | Date from which the discussion period is measured |
| `metric_name` | Proposed display name |
| `metric_description` | What the metric measures |
| `unit_of_measure` | Expected unit, when applicable |
| `category` | Domain or impact category |
| `rationale` | Why the metric is needed |
| `data_source` | Intended source records or systems |
| `collection_method` | How observations will be collected or confirmed |
| `frequency` | Intended collection or reporting cadence |
| `stakeholder_groups` | Groups expected to use or be affected by the metric |
| `discussion_notes` | Structured discussion record |
| `reviewed_by` | Staff reviewer recorded by the review workflow |
| `review_date` | Date of the review action |
| `implementation_date` | Date the metric was implemented |
| `metric_definition_id` | Link to the governed definition after implementation |
| `metadata` | Additional provenance or governance context |

## Proposal Lifecycle

`metric_proposal.status` uses a proposal workflow, not the standard governed record lifecycle:

```text
proposed -> discussed -> approved -> implemented -> deprecated
proposed -> approved
proposed -> rejected -> proposed
discussed -> rejected
approved -> deprecated
```

The exact allowed transitions are:

| Current status | Allowed next statuses |
|---|---|
| `proposed` | `discussed`, `approved`, `rejected` |
| `discussed` | `approved`, `rejected` |
| `approved` | `implemented`, `deprecated` |
| `implemented` | `deprecated` |
| `rejected` | `proposed` |
| `deprecated` | None; terminal |

The Directus hook rejects transitions outside this table. A rejected proposal may return to `proposed` for rework; a deprecated proposal cannot be reopened.

## Discussion And Approval

- Proposals may be created with `proposed` status and then discussed through `discussion_notes`.
- Approval requires at least 30 complete days since `proposal_date`; the hook calculates elapsed whole days when the status changes to `approved`.
- Review statuses are `approved`, `implemented`, `deprecated`, and `rejected`.
- A review status stamps `review_date` when one is not supplied.
- When Directus accountability contains a user, the hook stamps `reviewed_by` unless a value was already supplied.
- The 30-day rule applies to approval, including a direct `proposed -> approved` transition. It does not make `discussed` mandatory.

## Implementation

When a proposal reaches `implemented`:

- `metric_definition_id` is required.
- The link must point to the governed `metric_definition` that defines the metric key, formula, unit, and governance metadata.
- The proposal does not automatically register a Python calculator, compute a `metric_value`, or verify a result.
- After implementation, use the normal metric-definition, computation, and human-verification workflow documented in [Metric Verification](metric-verification.md).
- `implementation_date` should record when the linked definition became operational.

## Directus Workflow

The Directus hook in `extensions/kokonut-hooks/src/metric-proposal.ts` validates updates before they are written. The action hook in `extensions/kokonut-hooks/src/index.ts` records each status change in `workflow_history`, including the actor and discussion notes when available.

Directus permissions separate proposal participation from review:

- Proposal creators can create the proposal fields and read proposals scoped to their location.
- Reviewers can update `status`, review metadata, implementation metadata, `metric_definition_id`, discussion notes, and metadata.
- Clients cannot use the proposal update path to bypass the transition rules or the 30-day approval gate.
- Agents may create or update `metric_proposal` only within the agent-safe review statuses (`draft`, `submitted`, or `rejected`) when an agent write path is explicitly used; they cannot verify or publish the proposal. Human reviewers still control approval, implementation, and deprecation through Directus.

## Required Review Questions

- Who proposed the metric and why?
- Which stakeholder groups will use the metric or be affected by it?
- What source data and collection method are feasible?
- What unit and frequency are appropriate?
- What decision will the metric support?
- How will the metric distinguish observation from interpretation?
- What evidence, lineage, and privacy constraints apply?
- Which existing `metric_definition` should it use, or what separate implementation work is required?
- What would make the metric misleading, burdensome, or unsafe to publish?

## Practical Workflow

1. Create a proposal with the proposer, location scope, rationale, intended users, source, method, unit, and frequency.
2. Keep the proposal in `proposed` or move it to `discussed` while collecting stakeholder input.
3. Record discussion notes, unresolved concerns, rejected alternatives, and evidence requirements.
4. After the 30-day period, a human reviewer may approve or reject the proposal.
5. For an approved proposal, link the governed `metric_definition_id` before moving it to `implemented`.
6. Compute draft `metric_value` rows using the normal metric engine, then have an independent human verify each value.
7. Deprecate the proposal when the implemented metric is retired or superseded; retain its history for auditability.

## Example Proposal Context

The Adelphi pilot includes an approved proposal for a Spanish monthly operator-summary delivery metric. Its source context includes `report_snapshot` and `stakeholder_feedback`, its collection method is advisor confirmation and operator acknowledgement, and its intended cadence is monthly. It remains a proposal until a governed metric definition is linked and implementation is explicitly recorded.

## References And Verification

- Schema: `schemas/postgres/031_impact_claims_and_cids.sql`
- Foreign-key indexes: `schemas/postgres/042_fk_index_fixes.sql`
- Directus transition hook: `extensions/kokonut-hooks/src/metric-proposal.ts`
- Directus registration and workflow history: `extensions/kokonut-hooks/src/index.ts`
- Directus permissions: `config/directus/permissions.sql`
- Pilot example: `schemas/seeds/029_pilot_impact_accountability.sql`
- Hook tests: `extensions/kokonut-hooks/src/workflow.test.ts`
- Review checklist: `docs/common-foundations-checklist.md`
- Metric verification: `docs/metric-verification.md`

The proposal lifecycle requires governance review; it does not replace metric computation, evidence review, or publication approval.
