# EBF Trust Graph Guide

The EBF trust graph records provenance relationships around scorecards, pillar scores, evidence, reviewers, calibration sessions, attestations, reports, dashboards, and recommendations.

## Tables

- `ebf_trust_graph_node`: graph nodes linked to canonical records by `reference_type` and `reference_id`
- `ebf_trust_graph_edge`: typed relationships between nodes

Supported node types include `farm`, `location`, `pillar`, `metric`, `scorecard`, `score`, `evidence`, `reviewer`, `calibration_session`, `attestation`, `report_snapshot`, `dashboard_output`, and `improvement_recommendation`.

Supported edge types include `produced`, `supports`, `reviewed_by`, `measured_by`, `calibrated_by`, `attested_by`, `published_in`, `derived_from`, `requires`, `summarized_by`, and `recommended_for`.

## Public Safety

Graph records have a `public_safe` flag. Public exports should use only public-safe nodes and edges. Reviewer identities, calibration details, and private evidence should remain internal unless explicitly governed for publication.

Run:

```bash
python3 -m services.scoring --trust-graph UUID --public-safe
```

## Internal Export

Internal operators may export a graph without `--public-safe` to inspect provenance and evidence gaps:

```bash
python3 -m services.scoring --trust-graph UUID
```

## Recommended Edges

Common scorecard relationships:

- farm `produced` scorecard
- scorecard `requires` pillar
- score `supports` scorecard
- evidence `supports` score
- reviewer `reviewed_by` score
- calibration session `calibrated_by` scorecard
- attestation `attested_by` evidence
- report snapshot `summarized_by` scorecard

## Dashboard Use

The trust graph is intended for provenance inspection and audit trails. Portfolio dashboards should still use messy roll-ups and public-safe views, not raw graph records.
