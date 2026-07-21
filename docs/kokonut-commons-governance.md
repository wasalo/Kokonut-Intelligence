# Kokonut Commons Governance

Kokonut records anti-capture governance, flexible redistribution policies,
federation protocols, algorithmic redistribution mechanisms, and participatory
signals as governed evidence.

These records are scenario-specific and advisory unless a separate governed
implementation says otherwise. They do not hardcode one universal allocation
percentage, execute treasury transfers, implement automatic airdrops, or
override evidence, privacy, legal, or human-approval controls.

## Records

| Table | Purpose | Scope/state fields |
|---|---|---|
| `anti_capture_governance_policy` | Voting caps, veto rights, Sybil resistance, delegation limits, enforcement mode, and anti-plutocratic safeguards | `policy_scope`, `voting_method`, `status` |
| `commons_redistribution_policy` | Scenario or active allocation policies by revenue basis, trigger, enforcement, and audit cadence | `policy_scope`, `policy_status`, allocation percentages |
| `federation_protocol` | Permissionless reuse, local adaptation, mutual aid, shared infrastructure, onboarding, and anti-extractive safeguards | `federation_scope`, `protocol_status` |
| `algorithmic_redistribution_mechanism` | Proposed, pilot, or active redistribution mechanisms with eligibility and privacy safeguards | `mechanism_type`, `beneficiary_scope`, `implementation_status` |
| `participatory_signal_experiment` | Advisory meme, vibes, sentiment, story, or ranked-preference experiments with safety boundaries | `signal_type`, `governance_scope`, `decision_binding`, `experiment_status` |

All five records use the governed lifecycle:

```text
draft -> submitted -> verified -> published
                         \-> rejected
```

`status` is separate from the domain state fields such as `policy_status`,
`protocol_status`, `implementation_status`, and `experiment_status`.

## Anti-Capture Policies

`anti_capture_governance_policy` supports these policy scopes:

```text
farm, guild, dao, network, publication_review, other
```

Supported voting methods are:

```text
one_person_one_vote
quadratic
conviction
token_vote_capped
consent
consensus
hybrid
other
```

Policies can document:

- `voting_cap_pct`, constrained to `0-100` when present;
- quadratic or conviction voting status;
- one-person-one-vote status;
- Sybil-resistance method;
- worker/operator veto or rework rights;
- community veto rights;
- delegation limits;
- enforcement mode;
- internal and public summaries.

Enforcement modes include `offchain_policy`, `directus_hook`,
`smart_contract`, `multisig_policy`, `manual_review`, and `other`.

A published policy is evidence that safeguards were documented. It does not
prove that a voting method or veto is technically enforced. Reports must use
the recorded enforcement mode and must not infer on-chain enforcement from a
policy description.

## Redistribution Policies

`commons_redistribution_policy` supports:

### Policy Scopes

```text
farm, guild, dao, network, scenario, other
```

### Policy States

```text
proposed, active, paused, superseded, rejected
```

### Revenue Basis

```text
net_profit, gross_revenue, surplus, grant_pool, treasury_inflow, scenario, other
```

Allocation fields are independently bounded from `0` to `100`:

- `commons_allocation_pct`;
- `local_cooperative_allocation_pct`;
- `operator_allocation_pct`;
- `digital_commons_allocation_pct`;
- `reserve_allocation_pct`.

The schema does not require these percentages to sum to `100`. A policy may
describe only part of a value flow, and the remaining share must not be inferred
as an unrecorded allocation.

Policies can also record scenario name, trigger conditions, enforcement mode,
audit cadence, and public summary. Redistribution enforcement modes include
off-chain policy, smart contract, multisig policy, reporting policy, manual
review, and other.

`policy_status = 'active'` identifies an active policy record. A published
record with `policy_status = 'proposed'` is a public scenario, not a financial
commitment. The current and proposed statuses must be reported separately.

## Federation Protocols

`federation_protocol` is global rather than location-scoped. It supports:

```text
farm_network, guild_network, regional_cluster, open_source_framework, other
```

Protocol states are:

```text
draft, pilot, active, paused, deprecated
```

The record can document:

- target region;
- permissionless forking;
- local adaptation rights;
- mutual-aid commitments;
- shared infrastructure;
- onboarding requirements;
- anti-extractive safeguards;
- conflict-resolution path.

Permissionless reuse does not guarantee unlimited scaling or successful
replication. New communities require local registry, governance, cultural,
financial, and evidence records before stronger public claims are made.

## Algorithmic Redistribution

`algorithmic_redistribution_mechanism` supports these mechanism types:

```text
targeted_grant
fee_rebate
progressive_fee
airdrop
public_goods_matching
operator_support
other
```

Beneficiary scopes are group-level categories:

```text
farm_operator, local_cooperative, guild_contributor,
community_steward, public_goods_pool, other
```

Implementation states are:

```text
proposed, pilot, active, paused, completed, rejected
```

Each mechanism stores an allocation formula, optional funding source,
eligibility criteria, privacy safeguards, enforcement mode, and public summary.
Enforcement modes include manual review, Directus hook, smart contract, multisig
policy, off-chain policy, and other.

The existence of an algorithmic mechanism record does not mean payments are
automated. A mechanism is not an on-chain payout implementation unless its
enforcement mode and separate execution records establish that behavior.
Private beneficiary identities and household-level eligibility remain outside
public output.

## Participatory Signals

`participatory_signal_experiment` supports these signal types:

```text
meme_poll, vibes_check, sentiment_signal, ranked_preference, community_story, other
```

Governance scopes are:

```text
farm, guild, dao, network, publication_review, other
```

Decision-binding modes are:

```text
advisory, ratification_required, nonbinding_research, binding_after_review
```

Experiment states are:

```text
proposed, pilot, active, completed, paused, rejected
```

Every experiment requires participation rules, optional moderation policy, and
safety boundaries. Signals are advisory unless their recorded decision-binding
mode and human review workflow explicitly authorize further use. Meme, vibes,
sentiment, story, and ranked-preference signals cannot override evidence
maturity, privacy, treasury, or legal controls.

## Public Views

The schema defines one public view per record type:

| View | Public eligibility |
|---|---|
| `v_public_anti_capture_governance_policy` | Published, maturity `>= 3`, non-empty public summary, and either global scope or a verified/published location registry |
| `v_public_commons_redistribution_policy` | Published, maturity `>= 3`, non-empty public summary, and either global scope or a verified/published location registry |
| `v_public_federation_protocol` | Published, maturity `>= 3`, non-empty public summary |
| `v_public_algorithmic_redistribution_mechanism` | Published, maturity `>= 3`, non-empty public summary, and either global scope or a verified/published location registry |
| `v_public_participatory_signal_experiment` | Published, maturity `>= 3`, non-empty public summary |

Each view joins `evidence_maturity_level` for
`evidence_maturity_label`. The current SQL uses `SELECT record.*`, so source
metadata columns such as `metadata`, `source_system`, `source_id`, and
`source_raw` are part of the view result. Do not place private source payloads or
identity-sensitive beneficiary data in those fields for records eligible for a
public view. The public-safe boundary depends on the source record being
sanitized as well as on the view filters.

Global federation and participatory-signal records are included in location
scoped reports and agent summaries because they have no `location_id`.

## Governed Metrics

The seed defines these active metrics:

| Metric | Meaning | Unit/frequency |
|---|---|---|
| `anti_capture_policy_count` | Published policies with anti-capture safeguards | count, quarterly |
| `community_veto_enabled` | Whether published policy evidence documents community veto/rework rights | boolean, quarterly |
| `commons_redistribution_pct` | Policy-specific commons/public-goods allocation | percentage, quarterly |
| `operator_or_community_allocation_pct` | Operator plus local-cooperative allocation | percentage, quarterly |
| `federation_protocol_count` | Published federation or mutual-aid protocols | count, quarterly |
| `mutual_aid_support_count` | Public mutual-aid commitments | count, quarterly |
| `redistribution_mechanism_count` | Public redistribution mechanisms | count, quarterly |
| `participatory_signal_experiment_count` | Public participatory signal experiments | count, quarterly |

Metric definitions preserve scenario-specific meaning. They do not establish a
universal commons percentage, guarantee an allocation, or convert a proposed
mechanism into a payment event. Metric computation creates draft, unverified
`metric_value` rows and is not verification.

The `reserve_allocation_pct` field is also consumed by strategic-reserve pilot
data as a proxy input. That linkage does not turn a redistribution policy into
an autonomous reserve drawdown.

## Reports

Generate the five report types:

```bash
python3 -m services.export.report_generator --type anti_capture_governance --location-id UUID
python3 -m services.export.report_generator --type redistribution_policy --location-id UUID
python3 -m services.export.report_generator --type federation_mutual_aid --location-id UUID
python3 -m services.export.report_generator --type algorithmic_redistribution --location-id UUID
python3 -m services.export.report_generator --type participatory_signal --location-id UUID
```

The report outputs include the requested `location_id`, public records, report
limitations, and generation timestamp. Report-specific summaries include:

- anti-capture: `community_veto_count` and `operator_veto_count`;
- redistribution: `active_policy_count` and `scenario_policy_count`;
- federation: `permissionless_forking_count`;
- algorithmic redistribution: `active_or_pilot_count`;
- participatory signals: `advisory_count`.

The report generator accepts `--period-start` and `--period-end` globally, but
these commons report functions do not apply those values when reading the
public views. Do not describe these five reports as date-filtered until the
implementation adds date-aware fields and query filters.

Reports explicitly state that policies may be off-chain, proposed scenarios are
not commitments, algorithmic mechanisms are not automatically on-chain, and
participatory signals are advisory unless reviewed.

## Dashboards

The seed registers five published dashboard datasets. Each has a 1,440-minute
refresh interval and public-safe metadata:

| Dataset | SQL |
|---|---|
| Anti-Capture Governance Policies | `dashboards/metabase/sql/52_anti_capture_governance.sql` |
| Commons Redistribution Policies | `dashboards/metabase/sql/53_redistribution_policy.sql` |
| Federation And Mutual Aid Protocols | `dashboards/metabase/sql/54_federation_mutual_aid.sql` |
| Algorithmic Redistribution Mechanisms | `dashboards/metabase/sql/55_algorithmic_redistribution.sql` |
| Participatory Signal Experiments | `dashboards/metabase/sql/56_participatory_signal.sql` |

Dashboard queries read the public views. Dashboard visibility must not bypass
publication, maturity, summary, or registry filters.

## Commons Synthesis Agent

Run the public-safe synthesis agent:

```bash
python3 -m services.agents.kokonut_commons_agent --location-id UUID
```

The location is optional. With a location supplied, location-scoped views include
that location and global rows where `location_id IS NULL`; federation and signal
views are always global. Without a location, all public rows are summarized.

Store an optional draft `ai_summary`:

```bash
python3 -m services.agents.kokonut_commons_agent \
  --location-id UUID \
  --store
```

The agent reads:

- `v_public_anti_capture_governance_policy`;
- `v_public_commons_redistribution_policy`;
- `v_public_federation_protocol`;
- `v_public_algorithmic_redistribution_mechanism`;
- `v_public_participatory_signal_experiment`.

Its output includes:

- `anti_capture_policy_count`;
- `redistribution_policy_count`;
- active and proposed redistribution counts;
- `federation_protocol_count`;
- `algorithmic_redistribution_count`;
- `participatory_signal_count`;
- five public record arrays;
- synthesis text;
- a safety note.

The catalogue task is `kokonut_commons_synthesis`:

- risk: medium;
- optional input: `location_id`;
- optional input: `store`;
- required output: `summary`;
- permitted write: `ai_summary:draft` only;
- high risk: false.

The agent excludes unsupported Hypercert, Ecocertain, Venus Farm, and AMUSA
claims. It cannot publish policies, activate mechanisms, execute payments, or
override governance.

## Adelphi Pilot Boundaries

The pilot seed contains:

- an off-chain anti-capture policy with a 20% voting-cap guideline and operator/
  community veto rights;
- a published current policy scenario with 10% public-goods allocation and a
  20% reinvestment target represented in the policy fields;
- a proposed surplus-year scenario with flexible allocation percentages;
- a pilot federation starter protocol for a Dominican Republic cluster;
- a proposed manual-review operator-support matching pool;
- a proposed advisory vibes-check experiment.

These records intentionally do not claim:

- on-chain quadratic or one-person-one-vote enforcement;
- a committed majority-commons allocation;
- implemented airdrops or progressive fees;
- automatic redistribution payments;
- unlimited federation scaling;
- binding meme/vibes governance;
- unsupported Hypercert, Ecocertain, Venus Farm, or AMUSA allocations.

## Safety And Governance Rules

1. Keep lifecycle status separate from policy, implementation, protocol, and
   experiment state.
2. Treat proposed redistribution scenarios as scenarios, not commitments.
3. Report every allocation percentage with its policy scope, revenue basis, and
   policy status.
4. Do not infer that allocation percentages sum to `100`.
5. Do not describe off-chain, manual-review, or reporting policies as smart
   contract enforcement.
6. Keep beneficiary identities, protected-class details, household data, and
   private capital terms out of public summaries.
7. Treat participatory signals as advisory unless human-reviewed binding use is
   explicitly recorded.
8. Require local governance and evidence records before federation replication
   claims expand.
9. Agents may draft summaries only; they cannot activate policies or execute
   financial state changes.
10. Keep redistribution policy evidence separate from Moloch treasury execution
    and strategic-reserve drawdown workflows.

## References

Implementation:

- `schemas/postgres/041_kokonut_commons_governance.sql`
- `schemas/seeds/042_kokonut_commons_governance.sql`
- `schemas/seeds/042_pilot_kokonut_commons_governance.sql`
- `services/export/report_generator.py`
- `services/agents/kokonut_commons_agent.py`
- `services/agents/tasks.py`
- `services/agents/safety.py`
- `services/capital/capture.py`
- `services/strategic_reserve`

Dashboards:

- `dashboards/metabase/sql/52_anti_capture_governance.sql`
- `dashboards/metabase/sql/53_redistribution_policy.sql`
- `dashboards/metabase/sql/54_federation_mutual_aid.sql`
- `dashboards/metabase/sql/55_algorithmic_redistribution.sql`
- `dashboards/metabase/sql/56_participatory_signal.sql`

Tests:

- `tests/test_kokonut_commons_governance.py`
- `tests/test_commons_liberation.py`
- `tests/test_capital_accounting.py`
