# Metric Value Lifecycle

Spec: `metric_value`

## Invariants

- Metric computation creates draft, unverified metric_value rows.
- A human reviewer must verify individual values before public metric views expose them.
- Verification is a human decision; agents cannot auto-verify.
- The verified state is terminal.

## Decision Table

| Step | Actor | Current state | Action | Guard | Outcome | Next state | Target | Controls |
|---|---|---|---|---|---|---|---|---|
| mv_draft_entry | system | draft | Compute metric value | human reviewer verified | verify | verified | mv_verify | entry |
| mv_verify | reviewer | verified | Human verification of metric value | - | terminal | - | - | human-approval, terminal |

## Sources

- `schemas/postgres/007_modeled_outputs.sql`
- `services/metrics/engine.py`

## Governance Controls

- Computation creates draft values; a human verifies values before public exposure.
- Agents cannot verify or publish metric values.

## Data and Persistence

- metric_value | metric definition, period, source records, verification

## Audit Controls

- Formula version, source lineage, reviewer, and verification notes are retained.

## Tests

- `tests/test_metrics.py`
- `tests/test_bpm_state_models.py`
- `tests/test_evidence_lineage_integrity.py`

## Mermaid

```mermaid
flowchart TD
    mv_draft_entry[mv_draft_entry: Compute metric value [system]]
    mv_verify((mv_verify: Human verification of metric value [reviewer]))
    mv_draft_entry -->|human reviewer verified / verify -> verified| mv_verify
```
