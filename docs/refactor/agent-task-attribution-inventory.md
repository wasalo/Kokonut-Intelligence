# Agent Task Attribution Inventory

Updated: 25 October 2026

This is a source-level inventory of the current human-authenticated Gateway
surfaces related to agent-generated drafts. It is not a production request
log, live OIDC acceptance, or proof that CLI and scheduled work has a human
initiator.

| Surface | What it does | Authenticated operator attribution | Boundary |
| --- | --- | --- | --- |
| `POST /operator/api/ai-summaries/{location_id}/drafts` | Runs deterministic AI-summary generation and creates a private draft. | The route takes `operator_id` from the authenticated Gateway session. Migrations 522 and 597 bind the draft to an immutable request receipt; the review projection returns the operator UUID only when the receipt matches the summary's `created_by`. | The worker's database identity/task key remains separate from the operator who requested the run. No provider output or human review is implied. |
| `POST /operator/api/ai-summaries/{location_id}/synthesis-requests` | Creates or replays an immutable authorization receipt for one registered synthesis task and summary type. It does not dispatch or execute that task. | The route takes `operator_id` from the authenticated Gateway session and sets signed exact-location `ai_summary:draft` context. Migration 628 records the operator, location, task, summary type, intent digest, and request UUID; the task worker verifies the exact receipt before retry lookup, source reads, and draft creation. | The grant-gated operator console now selects a registered task, creates the receipt, and displays the exact isolated Compose worker profile command. The operator must still run it from the repository root; the Compose service receives that task's dedicated credentials only. Automatic dispatch is not implemented. The review queue identifies the operator and request UUID without exposing the receipt digest. |
| `POST /operator/api/delphi/{location_id}/studies/{study_id}/recommendation-drafts` | Stores facilitator recommendation text as a private Delphi draft; it does not launch the facilitator. | The route takes the operator UUID from the authenticated Gateway session. Migration 451 writes it to both `delphi_recommendation.created_by` and the append-only request receipt. | The standalone `draft-recommendation` CLI returns an in-memory suggestion only; its legacy `--created-by` argument is ignored. The persisted Gateway draft records the submitting operator, not a separately executed model run. |
| Legacy Delphi CLI and direct services | Study creation/open/close, study listing, panel add/list/removal, diversity assessment, item creation, contribution submission, stopping checks, calibration, recommendation review, and minority-report lifecycle. | The CLI fails before database setup. Direct database-backed methods on `Facilitator`, `PanelManager`, and `MinorityReportManager` now raise before using an injected/shared connection or cursor; tests assert that no cursor or commit is attempted. | The Kernel Gateway provides signed, exact-location study creation, question authoring, open-readiness/open/close, consent-notice review, pseudonymous single-use invite issuance/revocation, participant acceptance/withdrawal/workspace/contribution writes, consent-aware stopping evaluation, facilitator draft creation, and independent recommendation review. Participant acceptance creates pseudonymous panel membership. Panel administration, diversity review, minority reports, and calibration remain unavailable pending separate scoped contracts. Worker credentials and caller-supplied IDs do not substitute for operator authorization. |
| Generic `agent_task` execution | No OIDC-protected Gateway route invoking the unrestricted task catalogue or generic `agent_task` creation was found. The synthesis request route is limited to the registered summary-task map and only mints an authorization receipt. | That bounded route records the session operator before execution. It does not claim that CLI, scheduled, or background runs have human initiators. | Do not infer a human operator from a worker credential, free-form CLI flag, or legacy nullable `agent_task.requested_by`. Automatic task dispatch remains open. |
| Per-agent synthesis CLI draft storage | `services.agents.agent_cli --store` and `SynthesisAgent.run(store=True)` fail before synthesis or worker/database access. The one-shot `services.agents.worker_cli` accepts either `--read-only` or `--persist-draft --request-id`; default/ambiguous use, missing IDs, and malformed IDs fail before task resolution. | Worker lookup, source generation, and persistence require a matching immutable Gateway receipt under signed worker/task/location scope, including a currently active operator draft grant. Migration 628 enforces the match again at the database write boundary and the review queue exposes operator/request attribution. | Compose worker profiles remain read-only by default. The operator console runs only the selected task's service/profile with its dedicated credentials and overrides the read-only entrypoint only for a receipt-backed request; it does not dispatch automatically. Live OIDC and real task grants/credentials remain unverified. |

The legacy Delphi study/panel CLI fails before shared database access for all
operations without an authenticated location grant. The direct database
facades `Facilitator`, `PanelManager`, and `MinorityReportManager` also fail
before connection/cursor use for every database-backed method. Signed
aggregate reads and in-memory recommendation suggestions remain available;
Gateway paths cover the implemented scoped study and participant lifecycle.
Panel administration, diversity assessment, minority reports, calibration,
and any other unlisted legacy operation remain unavailable until separately
scoped and reviewed. Consensus distance is not a forecast-accuracy signal;
there is no approved calibration algorithm or independent-review contract.

The non-synthesis task helpers are not persistence paths: the EBF scorecard and
calibration agents return in-memory draft templates, the EBF evidence-gap helper
uses the signed read-only EBF worker, and Delphi facilitation returns a
read-only aggregate plus an in-memory recommendation. Persisted Delphi
recommendations use the separate authenticated operator Gateway route. A
source scan finds no literal direct DML call sites in `services/agents`; the
only AI-summary worker write calls use the signed worker functions, and
`worker_draft.py` verifies the immutable operator task receipt before retry
lookup and again immediately before the database write. The generated
[write-boundary inventory](agent-write-boundary-inventory.json) records the
Gateway receipt creator, worker receipt verifier, review projection, and draft
functions. It is a static literal-SQL inventory; dynamic SQL and runtime
privileges require separate review.

The Gateway route tests verify session-derived operator identity is forwarded
for all three draft/request surfaces. Source review of migrations 451, 522,
597, and 628 confirms the corresponding creator/request records and review
boundary. This closes the code-level attribution check for manually invoked
registered synthesis workers only. Authenticated runtime provisioning,
automatic dispatch, other service/CLI attribution policy, worker/database least
privilege, populated parity, live OIDC, and MAN-CAP-038 acceptance remain open.

`tests/test_operator_route_policy_inventory.py` also keeps generic operator
task execution routes absent until an immutable operator/request/task
attribution contract is implemented. Its route-registration regression covers
the conventional agent-task and agent-run path forms; exact route-policy
coverage independently requires every new OIDC route to receive a reviewed
policy entry. The regression passed four tests on 25 October 2026 ([evidence](builds/2026-10-25-recovery/cap-038-generic-agent-route-guard.json)).

The unauthenticated per-agent CLI and library persistence path fails closed
before worker or database access. The worker CLI's only write mode requires an
authenticated Gateway request UUID and the database verifies the exact task,
location, summary type, worker login, and current initiating-operator grant.
The Compose worker profiles stay read-only by default; the console now makes
this manual receipt workflow runnable through the exact task service and its
dedicated credentials. A request receipt alone does not launch a worker.
Automatic dispatch, task credential provisioning, and live OIDC remain open.
See the current progress record for focused and disposable acceptance evidence.
