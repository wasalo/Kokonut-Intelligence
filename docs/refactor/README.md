# Refactor documentation

Start with the **[candidate completion guide](current-state-and-implementation.md)**. It alone owns current status, remaining work, owner inputs, acceptance gates and execution order. The selected finish line is candidate acceptance, separate from production cutover.

The guide indexes all supporting Markdown records and reconciles historical unchecked requirements. Contracts, profile/runbooks, inventories and dated evidence remain references; old TODOs and batch lists are not active queues. Preserve historical evidence and append progress without duplicating current status. Source code remains authoritative for implemented behavior.

The approved [front-end modernization plan](frontend-modernization.md) maps the existing browser workflows into General Operations, Field Operations, and Governance apps while preserving their API, identity, consent, and offline contracts. It is a supporting design plan; it does not change the candidate acceptance status.

Update the guide after each acceptance batch; update capability classifications only when their criteria change. Do not synchronize competing checklist totals. Run `python3 scripts/check-capability-matrix.py` and documentation link checks for documentation changes.
