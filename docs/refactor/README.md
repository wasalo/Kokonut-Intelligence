# Refactor documentation

Start with the **[candidate completion guide](current-state-and-implementation.md)**. It alone owns current status, remaining work, owner inputs, acceptance gates and execution order. The selected finish line is candidate acceptance, separate from production cutover.

## Documentation authority

Use each document for the question it owns. Source code, migration files, and
the selected environment's live state remain authoritative for implementation
and actual behavior.

| Question | Source of truth |
|---|---|
| Which refactor gates are open or accepted? | [Candidate completion guide](current-state-and-implementation.md) |
| How do current Hub screens, form relations, sessions, and Worker routes behave? | [Control Plane guide](../../apps/frontend/README.md) |
| Which native Gateway routes and capabilities exist in source? | [Gateway route reference](../../services/gateway/README.md), with policy context in [Gateway guide](../gateway.md) |
| What does the optional Directus API expose? | [Directus compatibility API reference](../api-reference.md) |
| What are the main entities and relationships? | [Data dictionary](../data-dictionary.md); ordered SQL under `schemas/postgres/` defines exact constraints and columns |
| What is the current deployment topology? | [Deployment topology](../deployment-topology.md), checked against the selected Compose/Worker configuration |
| What did an earlier audit, test, rollout, or owner decision establish? | The explicitly dated supporting record and its linked evidence; do not treat an old snapshot as current environment state |

The guide indexes supporting Markdown records and reconciles historical
unchecked requirements. Contracts, profile/runbooks, inventories and dated
evidence remain references; old TODOs and batch lists are not active queues.
Preserve historical evidence and append progress without duplicating current
status. Do not copy candidate status, migration counts, or acceptance claims
into other documents as competing live summaries.

The approved [front-end modernization plan](frontend-modernization.md) maps the existing operator workflows into General Operations, Field Operations, and Governance modules within one Control Plane application while preserving their API, identity, consent, and offline contracts. Delphi participation and the offline Field Collector remain separate clients. It is a supporting design plan; it does not change the candidate acceptance status.

Update the guide after each acceptance batch; update capability classifications only when their criteria change. Do not synchronize competing checklist totals. For documentation changes, run `python3 scripts/check-capability-matrix.py`, review every changed local link, and use the source files linked by the touched guide to confirm the described contract.
