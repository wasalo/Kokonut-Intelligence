# Agent Task Attribution Inventory

Updated: 25 October 2026

This is a source-level inventory of the current human-authenticated Gateway
surfaces related to agent-generated drafts. It is not a production request
log, live OIDC acceptance, or proof that CLI and scheduled work has a human
initiator.

| Surface | What it does | Authenticated operator attribution | Boundary |
| --- | --- | --- | --- |
| `POST /operator/api/ai-summaries/{location_id}/drafts` | Runs deterministic AI-summary generation and creates a private draft. | The route takes `operator_id` from the authenticated Gateway session. Migrations 522 and 597 bind the draft to an immutable request receipt; the review projection returns the operator UUID only when the receipt matches the summary's `created_by`. | The worker's database identity/task key remains separate from the operator who requested the run. No provider output or human review is implied. |
| `POST /operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts` | Stores facilitator recommendation text as a private Delphi draft; it does not launch the facilitator. | The route takes the operator UUID from the authenticated Gateway session. Migration 451 writes it to both `delphi_recommendation.created_by` and the append-only request receipt. | The standalone `draft-recommendation` CLI returns an in-memory suggestion only; its legacy `--created-by` argument is ignored. The persisted Gateway draft records the submitting operator, not a separately executed model run. |
| Generic `agent_task` execution | No OIDC-protected Gateway route invoking the generic task catalogue or `agent_task` creation was found in the current route registrations. | No current authenticated human-run request exists to attribute through that surface. | CLI, scheduler, and signed worker identity are service execution identities. Do not infer a human operator from a worker credential, free-form CLI flag, or legacy nullable `agent_task.requested_by`. A future human-run endpoint must create an immutable operator/request/task link before execution. |
| Per-agent synthesis CLI draft storage | `services.agents.agent_cli --store` and `SynthesisAgent.run(store=True)` previously persisted through a registered worker identity without a human request receipt. | Both now fail before synthesis or worker/database access unless an authenticated operator/request/task path is added. Read-only synthesis remains available. | The separately exposed `services.agents.worker_cli` one-shot Compose profiles still persist drafts and can be invoked manually; their worker identity is not human attribution. That profile path remains open and must receive a verified request receipt before human-triggered use. |

The Gateway route tests verify session-derived operator identity is forwarded
for both draft surfaces. Source review of migrations 451, 522, and 597 confirms
the corresponding creator/request records and review boundary. This closes
the current-source route inventory only. Authenticated runtime provisioning,
other service/CLI attribution policy, worker/database least privilege,
populated parity, live OIDC, and MAN-CAP-038 acceptance remain open.

`tests/test_operator_route_policy_inventory.py` also keeps generic operator
task execution routes absent until an immutable operator/request/task
attribution contract is implemented. Its route-registration regression covers
the conventional agent-task and agent-run path forms; exact route-policy
coverage independently requires every new OIDC route to receive a reviewed
policy entry. The regression passed four tests on 25 October 2026 ([evidence](builds/2026-10-25-recovery/cap-038-generic-agent-route-guard.json)).

The unauthenticated per-agent CLI and library persistence path now also fails
closed before worker or database access; its read-only path and the registered
service worker implementation remain. The focused agent-base and worker CLI
selection passes 79 tests with Ruff and Python compilation. The Compose worker
profiles are one-shot manual commands, so they remain an unattributed entry
point until an authenticated request receipt is verified before persistence
([evidence](builds/2026-10-25-recovery/cap-038-human-cli-agent-draft-disable.json)).
