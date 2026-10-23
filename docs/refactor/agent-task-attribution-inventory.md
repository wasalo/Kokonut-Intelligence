# Agent Task Attribution Inventory

Updated: 23 October 2026

This is a source-level inventory of the current human-authenticated Gateway
surfaces related to agent-generated drafts. It is not a production request
log, live OIDC acceptance, or proof that CLI and scheduled work has a human
initiator.

| Surface | What it does | Authenticated operator attribution | Boundary |
| --- | --- | --- | --- |
| `POST /operator/api/ai-summaries/{location_id}/drafts` | Runs deterministic AI-summary generation and creates a private draft. | The route takes `operator_id` from the authenticated Gateway session. Migrations 522 and 597 bind the draft to an immutable request receipt; the review projection returns the operator UUID only when the receipt matches the summary's `created_by`. | The worker's database identity/task key remains separate from the operator who requested the run. No provider output or human review is implied. |
| `POST /operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts` | Stores facilitator recommendation text as a private Delphi draft; it does not launch the facilitator. | The route takes the operator UUID from the authenticated Gateway session. Migration 451 writes it to both `delphi_recommendation.created_by` and the append-only request receipt. | The standalone `draft-recommendation` CLI returns an in-memory suggestion only; its legacy `--created-by` argument is ignored. The persisted Gateway draft records the submitting operator, not a separately executed model run. |
| Generic `agent_task` execution | No OIDC-protected Gateway route invoking the generic task catalogue or `agent_task` creation was found in the current route registrations. | No current authenticated human-run request exists to attribute through that surface. | CLI, scheduler, and signed worker identity are service execution identities. Do not infer a human operator from a worker credential, free-form CLI flag, or legacy nullable `agent_task.requested_by`. A future human-run endpoint must create an immutable operator/request/task link before execution. |

The Gateway route tests verify session-derived operator identity is forwarded
for both draft surfaces. Source review of migrations 451, 522, and 597 confirms
the corresponding creator/request records and review boundary. This closes
the current-source route inventory only. Authenticated runtime provisioning,
other service/CLI attribution policy, worker/database least privilege,
populated parity, live OIDC, and MAN-CAP-038 acceptance remain open.
