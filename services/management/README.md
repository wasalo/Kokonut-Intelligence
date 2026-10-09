# management

`services.management` — Management package entrypoint.

## CLI Usage

```bash
python3 -m services.management
```
```bash
python3 -m services.management.cli --help
```

## Modules

- `capacity_signals` — Capacity and demand signals for the dual-scope operating model.
- `cli` — Management CLI for work items and RACI responsibility assignments.
- `escalation` — Process auto-escalation / handover (BPM human-interaction phase).
- `learning_plans` — Competency evidence and learning plans for role development.
- `model` — Management domain constants and spec-derived helpers.
- `operating_pilot` — Bootstrap and inspect the dual-scope operating pilot.
- `operating_support` — Private coaching and explicit resource requests.
- `responsibility` — RACI responsibility assignments linking governed entities to parties.
- `work_selection` — Governed work opportunities and bounded self-selection.
- `workbench` — Work item workbench: create, assign, transition, and SLA sweeps.

## Files

11 Python modules
