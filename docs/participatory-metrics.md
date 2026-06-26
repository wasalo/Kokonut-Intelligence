# Participatory Metrics

Participatory metrics let farm operators, workers, advisors, and DAO reviewers propose measurements that are useful locally before they become governed platform metrics.

## Workflow

`metric_proposal.status` uses a proposal workflow, not the governed record lifecycle:

```text
proposed -> discussed -> approved -> implemented -> deprecated
proposed -> rejected
rejected -> proposed
```

## Required Review Questions

- Who proposed the metric and why?
- Which stakeholder groups will use the metric?
- What data source and collection method are feasible?
- How often should it be collected?
- What decision will it support?

## Implementation

When a proposal reaches `implemented`, it must link to `metric_definition_id`. The Directus hook in `extensions/kokonut-hooks/src/metric-proposal.ts` enforces transition rules and stamps reviewer metadata.
