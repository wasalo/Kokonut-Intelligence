# EBF Trust Graph Guide

The EBF trust graph is a provenance export around scorecards, pillar scores,
evidence, reviewers, calibration, attestations, reports, dashboards, and
recommendations. It links graph records to canonical entities using a reference
type and reference ID. It is an audit/provenance representation, not the
canonical scorecard store and not a general graph database.

## Scope And Related Graphs

The EBF graph uses:

- `ebf_trust_graph_node`
- `ebf_trust_graph_edge`

It is distinct from the evaluator trust network in:

- `services/scoring/evaluator.py`
- `services/scoring/network.py`
- `services/scoring/rankings.py`

The evaluator network measures evaluator reputation, transitive trust, and
preference/ranking behavior. The EBF graph describes provenance around a
scorecard and its evidence. Similar words such as “trust” do not imply the same
data model or score.

## Node Types

The schema allows these node types:

| Node type | Typical reference |
|-----------|-------------------|
| `farm` | Farm record |
| `location` | Location record |
| `operator` | Operator or responsible party |
| `pillar` | EBF pillar |
| `metric` | Metric definition or metric value |
| `scorecard` | EBF scorecard |
| `score` | EBF pillar score |
| `evidence` | Evidence record or evidence link |
| `data_source` | Source system or dataset |
| `measurement_method` | Measurement method |
| `reviewer` | Reviewer identity/reference |
| `calibration_session` | Calibration session |
| `calibration_decision` | Calibration decision |
| `attestation` | EAS or attestation record |
| `report_snapshot` | Frozen report output |
| `dashboard_output` | Dashboard or dataset output |
| `improvement_recommendation` | EBF improvement recommendation |

Each node includes a canonical `reference_type`, `reference_id`, a node type,
and public-safety metadata. The exact database columns and constraints remain in
`schemas/postgres/033_ebf_p1_operations.sql`.

## Edge Types

The schema allows these typed relationships:

| Edge type | Meaning |
|-----------|---------|
| `produced` | Source or operator produced a record |
| `supports` | Evidence or score supports another record |
| `reviewed_by` | Record was reviewed by a reviewer |
| `measured_by` | Metric or score uses a measurement method |
| `calibrated_by` | Score or scorecard is associated with calibration |
| `attested_by` | Evidence or output is associated with an attestation |
| `published_in` | Output appears in a report or dashboard |
| `derived_from` | Output derives from another record |
| `requires` | Record requires another record or evidence |
| `summarized_by` | Record is summarized by a report output |
| `recommended_for` | Recommendation targets a record |

Edges should be typed, directional, and backed by explicit canonical references.
Do not infer a relationship only from free-text metadata.

## Common Provenance Pattern

```text
farm ──produced──> scorecard
scorecard ──requires──> pillar
score ──supports──> scorecard
evidence ──supports──> score
score ──measured_by──> measurement_method
score ──reviewed_by──> reviewer
scorecard ──calibrated_by──> calibration_session
evidence ──attested_by──> attestation
scorecard ──summarized_by──> report_snapshot
recommendation ──recommended_for──> scorecard
```

These are recommended provenance patterns, not relationships automatically
created by every scorecard operation. No EBF graph-builder or graph-population
service was found that guarantees the complete pattern.

## Export Commands

The scoring CLI supports JSON and Mermaid output:

```bash
# Internal graph export
python3 -m services.scoring --trust-graph UUID

# Public-safe export request
python3 -m services.scoring --trust-graph UUID --public-safe

# Public-safe Mermaid output
python3 -m services.scoring --trust-graph UUID --public-safe --mermaid
```

The UUID is used as a reference ID to select seed nodes. The exporter returns a
JSON object with this shape:

```json
{
  "export_type": "ebf_trust_graph",
  "reference_id": "UUID",
  "public_safe": true,
  "nodes": [],
  "edges": []
}
```

`trust_graph_to_mermaid()` renders the returned nodes and edges as a Mermaid
`graph TD` diagram. An empty export produces an empty graph rather than an
error.

## Traversal Behavior

The current exporter is a bounded one-hop export:

1. Select seed nodes matching the reference ID.
2. Select immediately connected edges.
3. Select nodes connected by those edges.
4. Serialize nodes and edges.

It is not recursive multi-hop traversal and does not build a complete historical
lineage graph. It does not automatically discover every related scorecard,
metric, evidence record, or report in the platform.

## Public Safety

Nodes and edges have a `public_safe` flag. Public exports are intended to omit
reviewer identities, internal calibration details, private evidence, and other
non-public records. Public dashboard/report consumers should prefer the public
EBF views and aggregates rather than raw graph records.

### Current Implementation Defect

`services/scoring/trust_graph.py` filters seed nodes and edges for
`--public-safe`, but the final connected-node query does not consistently apply
`n.public_safe = TRUE`. A non-public connected node can therefore appear in a
requested public-safe export if it is connected through an otherwise public-safe
edge.

Until this is fixed and covered by a regression test, do not treat
`--public-safe` output as a complete privacy guarantee. Apply an additional
consumer-side node filter and inspect the output before publication.

The intended public rule is:

```text
public-safe export = public-safe seed nodes
                   + public-safe edges
                   + public-safe connected nodes
```

## Relationship To Public EBF Views

The graph is not a substitute for:

- `v_public_ebf_scorecard`
- `v_public_ebf_scorecard_summary`
- `v_public_ebf_pillar_summary`

Those views enforce scorecard lifecycle, public-claim, evidence, registry, and
carbon-specific gates. The graph exporter primarily filters graph metadata and
does not reproduce every public scorecard view condition.

Portfolio dashboards should use messy public-safe rollups by pillar, confidence,
and evidence maturity. They should not rank farms as interchangeable units or
use raw graph edge counts as a trust score.

Portfolio dashboards should still use messy roll-ups and public-safe views, not
raw graph records.

## Agent And Write Boundaries

The graph is an export surface. It is not an autonomous write path. Agents may
draft scorecards, identify evidence gaps, or prepare calibration memos within
their task and safety boundaries, but they cannot verify or publish scorecards,
raise evidence maturity, certify carbon claims, or expose private feedback.

The standalone EBF agent modules do not populate the full trust graph. Graph
nodes and edges require explicit canonical writes or future graph-projection
workflows.

## Operational Review Checklist

Before sharing an internal graph:

1. Confirm the requested reference ID and audience.
2. Use `--public-safe` for any public-facing export.
3. Filter connected nodes again until the public-safe defect is fixed.
4. Remove reviewer, calibration, and private-evidence details not required for
   the audience.
5. Compare scorecard values against the authoritative public EBF views.
6. Preserve the export's `reference_id`, timestamp, and software version.
7. Do not treat graph presence as evidence that the underlying score or claim is
   verified.

## Tests And Limitations

Relevant tests include EBF scoring, public carbon gates, platform schema checks,
and scoring exports. Add or maintain regression coverage for:

- all allowed node and edge types;
- JSON and Mermaid output shape;
- one-hop traversal boundaries;
- public-safe connected-node filtering;
- private reviewer/calibration/evidence exclusion;
- empty graph output;
- reference-ID scoping.

Current limitations:

- No canonical graph population service was found.
- Export is one-hop, not recursive.
- Public-safe connected-node filtering has the defect described above.
- Graph export does not replace public EBF view gates.
- The EBF graph is separate from evaluator reputation and ranking data.

## Source References

- `schemas/postgres/033_ebf_p1_operations.sql`
- `services/scoring/trust_graph.py`
- `services/scoring/export.py`
- `services/scoring/evaluator.py`
- `services/scoring/network.py`
- `services/scoring/rankings.py`
- `services/scoring/cli.py`
- `dashboards/metabase/sql/25_ebf_portfolio_messy_rollup.sql`
- `docs/ebf-scorecard.md`
