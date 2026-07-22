# Metrics By Development Era

Kokonut Intelligence grew from a farm data model into a governed measurement,
analytics, and decision-support platform. This guide explains how that growth
enabled the current metric layer and what questions the metrics answer
together.

It makes one distinction up front:

- **Governed metrics** are defined in `metric_definition`, computed into
  `metric_value`, and independently verified before public exposure.
- **Analytics indicators** are read-only calculations or domain summaries.
- **Reports and framework scores** compose governed records and analytics for a
  particular audience; they are not automatically additional `metric_value`
  rows.

## At A Glance

The repository currently contains:

- 20 registered metric calculators.
- 323 numbered PostgreSQL migrations, through migration 330.
- 94 report generators.
- 18 named agent modules, alongside shared agent infrastructure.
- 53 Metabase dashboard definitions.
- 117 SQL seed files.

These are repository inventory counts, not guarantees about the number of
records or reports currently populated in a deployment.

## Measurement Path

Every governed metric follows the same controlled path:

```text
governed source records
        -> metric definition and calculator
        -> draft metric_value
        -> human verification
        -> verified public metric projection
```

Computation records the value, unit, period, computation method, definition
version, and provenance. Computation never verifies its own output. The public
metric view additionally requires an active location and a verified or
published farm registry record.

See [Metric Verification](metric-verification.md) for the operational workflow,
CLI, provenance model, lifecycle ledger, and recovery rules.

## Governed Metric Catalog

The current registry is maintained in
`services/metrics/calculators/__init__.py`. The metric definition seeds provide
the semantic descriptions, formulas, validation tests, report usage, and
deprecation policies.

### Baseline

These values come from the location's pre-intervention baseline fields. They
are comparison anchors, not computed claims about current performance.

| Metric | Main source | Question answered |
|---|---|---|
| `baseline_revenue` | Migration 001, `location.baseline_revenue` | What revenue was recorded before the intervention? |
| `baseline_asset_value` | Migration 001, `location.baseline_asset_value` | What productive or asset value was recorded at baseline? |
| `baseline_cash_flow` | Migration 001, `location.baseline_cash_flow` | What cash-flow position was recorded at baseline? |
| `baseline_cost` | Migration 001, `location.baseline_cost` | What operating cost was recorded at baseline? |

### Crop Economics

These metrics connect crop cycles and harvest activity to revenue, cost, and
profitability. They use the canonical revenue and expense records and the
crop-cost allocation model.

| Metric | Main source | Question answered |
|---|---|---|
| `crop_revenue` | Migrations 002-004, `revenue_event` | How much gross crop revenue was recorded? |
| `net_crop_revenue` | Migrations 004 and 070, revenue adjustments | What revenue remains after applicable returns and discounts? |
| `direct_crop_cost` | Migration 004, direct crop expenses | What costs are directly attributable to the crop? |
| `allocated_shared_cost` | Migration 004, `crop_cost_allocation` | What share of common costs is allocated to the crop? |
| `crop_noi` | Migration 004, revenue less crop costs | What net operating income did the crop generate? |
| `loss_rate_pct` | Migrations 003-004, harvest loss fields | What share of harvested output was lost rather than saleable? |
| `operating_margin_pct` | Migration 004, crop NOI and net revenue | What percentage margin remains after crop operating costs? |

The calculator preserves source provenance where source IDs are available and
applies the inclusion and exclusion rules defined for the metric. A computed
value is not a financial statement or a claim that all economic externalities
have been captured.

### Value And Web3 Engagement

These metrics describe value movement and participation in the platform's
digital infrastructure.

| Metric | Main source | Question answered |
|---|---|---|
| `value_flowed` | Migration 004, `value_flow_event` | What recorded value flowed through the governed activity? |
| `wallet_retention` | Migration 006, `wallet_profile` | How many eligible wallets remain active under the metric definition? |
| `digital_lego_usage` | Migration 006, `digital_lego_usage` and verified records | Which verified digital protocols or building blocks are being used? |

`value_flowed` is not the same as revenue, profit, treasury balance, or token
value. The metric definition and source filters determine what counts.

### Environmental And Evidence Signals

These metrics summarize environmental change and attestation coverage from
governed source records.

| Metric | Main source | Question answered |
|---|---|---|
| `soil_carbon_delta` | Migration 005, soil-carbon measurements | How did measured soil carbon change across the comparison period? |
| `biodiversity_delta` | Migration 005, species observations | How did observed biodiversity change across the comparison period? |
| `attestation_coverage` | Migrations 013 and 024, attestation and MRV records | What share of eligible claims has the required attestation coverage? |

Environmental deltas are measurements within their defined source, location,
and period. They are not automatically equivalent to a carbon credit, an
ecological causal claim, or independent third-party verification.

### Process Quality

These metrics were added with the value-stream and lifecycle instrumentation
work. They use the append-only `lifecycle_transition` ledger rather than
inventing a separate status model.

| Metric | Main source | Question answered |
|---|---|---|
| `governed_lead_time_days` | Migration 103, lifecycle transitions | How long do published lifecycle records take from first draft? |
| `first_time_through_yield_pct` | Migration 103, lifecycle transitions | What share reaches publication without a rejection or rework transition? |
| `rework_rate_pct` | Migration 103, lifecycle transitions | What share reaches publication after at least one rejection transition? |

The process metrics exclude entities that never reach the relevant terminal
state. They describe flow performance, not the substantive quality of the
underlying record.

## Development Eras

The original documentation grouped only migrations `001-062`. That history is
still useful, but it is no longer the complete platform. The current schema
continues through migration 330, so the phases below are presented as eras
rather than as a claim that every migration creates a metric.

### Era 1: Foundation, Migrations 001-008

The foundation established locations, farms, plots, crop cycles, field
activity, finance, environmental observations, wallets, metric definitions,
metric values, and initial governance tables.

This era enables the baseline, crop economics, environmental, value-flow, and
engagement metric families. Migration 007 is especially important because it
defines the semantic `metric_definition` and computed `metric_value` layer.

### Era 2: Governance And Public Infrastructure, Migrations 009-024

Workflow history, market data, sensors, MRV and impact claims, revenue
multiplier configuration, public-safe views, and metric-definition versioning
make measurement governable.

This era establishes the distinction between a computed value and a verified
public value. Migration 018 defines the public metric projection, while
migration 024 records semantic metric-definition changes. Attestation coverage
is tied to the MRV and attestation work in this era.

### Era 3: Frameworks And Environmental Evidence, Migrations 025-033

Impact framework alignment, ground analytics, carbon accounting, evidence
maturity, CIDS mapping, and the EBF scorecard add interpretation around the
core metrics.

These capabilities help answer whether observed changes align with impact
frameworks and evidence requirements. They should not be mistaken for a new
set of core metric calculators unless explicitly registered in the metric
engine.

### Era 4: Wellbeing, Finance, And Commons, Migrations 034-041

Holistic wellbeing, financial sustainability, capital efficiency, commons
liberation, GNH alignment, regenerative outcomes, community governance, and
anti-capture mechanisms expand the platform beyond farm output.

Most outputs from this era are domain records, analytics, framework scores, and
reports. They complement the governed metrics by adding human, social,
financial, and governance context.

### Era 5: Regenerative Operations, Migrations 042-078

Bio-factory operations, ecological modeling, pest management, training,
revenue streams, prediction validation, livestock feed, grants, organic
readiness, carbon credits, and retirement certificates turn measurement into
operational and value-chain workflows.

The primary contribution is richer evidence and decision context around the
metric layer. Claims, credits, certificates, and reports retain their own
lifecycles and verification gates.

### Era 6: Field Intelligence And Applied Analytics, Migrations 079-156

Field collection, content, spatial imports, weather, forecasting, mobile
offline capture, precision irrigation, pest biology, crop rotation,
traceability, digital finance, extension, identity, energy, waste, landscape,
pollinator, marketplace, cooperative, and related modules add operational
resolution.

These modules produce many analytics indicators, observations, and governed
records that can become metric inputs. They do not all create rows in
`metric_value`.

### Era 7: Platform Integrity And Durable Workflows, Migrations 157-196

Backcasting, Delphi, OODA feedback, decision policies, process mining,
predictive BPM, lifecycle transitions, process health, escalation, and process
costing make the platform's governed flows observable.

Migration 179 introduces the lifecycle transition ledger. Migration 187 maps
`metric_value.verified` to the ledger's `draft -> verified` process model.
Migration 103's three flow metrics use this lifecycle infrastructure.

### Era 8: Stakeholder, Business, And Coordination Architecture, Migrations 197-249

Revenue models, channel orchestration, partner lifecycle, business model
canvas, pitch and business-plan outputs, capability maps, strategy maps,
stakeholder landscape, consent, engagement, grievance, representation, trust,
and coordination governance broaden the questions the platform can answer.

These capabilities provide stakeholder and organizational context for metric
interpretation. Consent, privacy, participation, and grievance boundaries
remain separate from metric verification.

### Era 9: Operating Model And Strategy Execution, Migrations 250-307

Work selection, capacity-aware planning, competencies, learning, coaching,
operating pilots, strategy plans, choices, investments, evidence lineage,
competitive analysis, and execution snapshots connect evidence to coordinated
action.

The management and strategy layers can use metric keys as targets or evidence
links, but they do not grant agents authority to verify metrics or publish
governed records.

### Era 10: Integrity, Governance, Guild, And Capital Extensions, Migrations 308-330

Relationship entities, cardinality and temporal integrity, reference-policy
validation, consent append-only controls, public financial governance, the KGP
protocol, Guild projections, Baal governance, strategic reserves, tactical
layers, and capital accounting harden the platform's later-stage boundaries.

For metrics, the important additions include normalized provenance through
`metric_value_source`, semantic uniqueness for verified values, and stronger
cross-domain evidence lineage.

## Questions Answered Together

Metrics become more useful when interpreted with their source records,
uncertainty, evidence maturity, and domain context.

| Question | Governed metrics | Complementary analytics and records |
|---|---|---|
| How is current performance changing from baseline? | Baseline metrics plus `crop_revenue`, `crop_noi`, `operating_margin_pct` | Forecasts, crop cycles, verified revenue and expense events |
| Is the crop operation economically viable? | `net_crop_revenue`, `direct_crop_cost`, `allocated_shared_cost`, `crop_noi`, `operating_margin_pct` | Market prices, unit economics, revenue model, financial sustainability |
| Is value being created and retained? | `value_flowed`, `wallet_retention` | Value-flow records, treasury data, retention context, capital accounting |
| Is there evidence of environmental improvement? | `soil_carbon_delta`, `biodiversity_delta` | Soil measurements, species observations, carbon balance, tree and habitat records |
| Can the public trust the measurement? | `attestation_coverage` and verified metric values | Evidence maturity, reviewer attribution, provenance, farm registry, claim gates |
| Is the governed system flowing well? | `governed_lead_time_days`, `first_time_through_yield_pct`, `rework_rate_pct` | Lifecycle transitions, process mining, predictive BPM, escalation, work items |
| Is the farm ready for a particular claim or standard? | Relevant verified metrics | CRISP, EBF, organic readiness, CIDS, external verification, methodology evidence |
| Are people and communities benefiting? | Metrics used as supporting evidence where explicitly mapped | Wellbeing, GNH, stakeholder feedback, consent, representation, grievance, governance |
| Can the operating model scale responsibly? | Flow, financial, and environmental metrics as evidence | Capacity, strategy execution, reserves, capital accounting, competitive and regional readiness |

No single metric establishes that a farm is regenerative, financially
sustainable, culturally respectful, or ready for a public claim. Those are
composite interpretations that require explicit evidence and governance.

## What A Metric Does Not Mean

- A computed row is draft data, not verification.
- A verified metric is not automatically a published impact claim.
- A public metric value is not an attestation, credit, certificate, or financial
  settlement.
- A positive delta does not prove causality without the relevant design,
  comparison, and evidence.
- A report or framework score may include modeled or advisory outputs and must
  retain its own uncertainty and public-interest context.
- Agent and analytics outputs remain advisory or draft-only wherever the
  applicable governance workflow requires human review.

## Source References

- [Metric Verification](metric-verification.md)
- [Metric Value Lifecycle](workflow-metric-value.md)
- [Evidence Maturity](evidence-maturity.md)
- [Platform Integrity](platform-integrity.md)
- [Value Stream Workflow](workflow-value-stream.md)
- `services/metrics/calculators/__init__.py`
- `services/metrics/engine.py`
- `schemas/postgres/007_modeled_outputs.sql`
- `schemas/postgres/018_public_views.sql`
- `schemas/postgres/024_metric_governance_enforcement.sql`
- `schemas/seeds/103_flow_metrics.sql`
- `schemas/postgres/179_lifecycle_transition.sql`
- `schemas/postgres/187_state_model_triggers.sql`
- `schemas/postgres/309_relationship_entities.sql`
- `schemas/postgres/310_cardinality_temporal_integrity.sql`

## Maintenance Rule

When adding a governed calculator, update the metric registry, definition seed,
metric-governance tests, and this catalog together. When adding an analytics
module, report, or framework score that does not write `metric_value`, document
it in the relevant domain guide rather than inflating the governed metric
count.
