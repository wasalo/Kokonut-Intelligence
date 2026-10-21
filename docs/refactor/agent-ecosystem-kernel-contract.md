# Agent ecosystem Kernel contract

**Status:** first code-level safety slice prepared; MAN-CAP-038 remains open.

## Boundary

The Kernel agent boundary treats each registered task's `writes` declaration as
an executable capability contract. A task may declare only `collection:draft`
or `collection:submitted`; a task marked `high_risk` or a malformed, rejected,
verified, or published write target fails closed. Task definitions returned to
callers are deep copies, so mutating a CLI/API description cannot mutate the
in-process policy registry.

The shared synthesis runner, read-only runner, CIDS task, AI summary task, EBF
draft tasks, and Delphi facilitator validate this contract before any database
connection or task work begins. The catalogue validator also asks the common
agent safety policy whether each write is allowed.

Before processing, those same task entry points validate declared top-level
inputs from the task catalogue: required fields, primitive types, UUID formats,
and exact `YYYY-MM-DD` dates. Malformed IDs and dates fail before the shared or
standalone runner opens a database connection or initializes the Delphi
facilitator. This validates shape only; it does not authenticate the caller,
prove location membership, or authorize access to the referenced object.

The catalogue itself is checked whenever task capabilities are validated. Each
input and output field must use a supported primitive type, a supported
string-only `uuid` or `date` format, a boolean `required` flag, and only schema
keywords the validator actually implements. Unknown types, formats, flags, or
constraints fail closed even when the affected field is optional or omitted.

The policy denies execution actions in `HIGH_RISK_ACTIONS`, including
`verify`, `publish`, `attest`, `onchain_submit`, `delete`, `bulk_update`, and
`financial_write`. `requires_human_approval` remains audit metadata; it does not
authorize an agent operation. Human review must happen through an independently
authorized workflow. No model/provider call or human-approval endpoint is added
by this slice.

Policy-only task listing and validation do not import the database-backed
action logger. Audit persistence is imported only when a caller explicitly
records an action, so the task catalogue and unified `agents list` command can
run without decrypting `.env.sops`.

## Existing safety behavior retained

- Draft creation continues for the write targets declared by the task catalogue.
- Shared synthesis runners validate the generated output before inserting a
  draft. The validator checks declared top-level presence, types, and UUID
  formats. Invalid output now fails before `INSERT`/`COMMIT`, and the connection
  still closes. Nested content is not schema-validated, and this does not
  replace the human review lifecycle.
- Shared synthesis, read-only, AI summary, CIDS, EBF, and Delphi entry points
  validate declared top-level task inputs before work begins. The validator
  checks required fields, primitive types, UUIDs, and exact ISO dates; it does
  not validate nested payloads or replace authentication and tenant grants.
- The full task catalogue is validated for supported top-level input/output
  schema declarations before tasks are listed or invoked. The current validator
  intentionally supports a small top-level subset; nested JSON schemas remain
  undefined rather than being implied by object/array type checks.
- Both shared and standalone draft persistence helpers repeat their write-side
  checks before requesting a cursor. They reject malformed task scope,
  incomplete/empty or over-20,000-character persisted content, invalid
  source-table metadata, or an invalid model-version label; callers cannot bypass the runner's validation
  by invoking the low-level write helper directly. These checks still create
  drafts only and do not approve or publish them. A common validator applies
  the source-table bounds to both shared and standalone writers. Both helpers
  close their cursors after insert/fetch failure and commit only after a
  successful write. The shared helper also validates that its static source
  table metadata contains between one and 20 lowercase
  SQL identifiers, matching the database draft function's shape limits.
  A source-code audit removed two stale labels for tables the bio-factory and
  stakeholder-feedback synthesis paths do not query. Source-table names remain
  hints only; they are not linked row-level evidence.
- Existing output validation, EBF maturity limits, human-governed collection
  restrictions, and read behavior remain in place.
- Optional Directus hooks keep their role and lifecycle checks. The action-log
  hook marks `verify` as high risk so the audit surface remains aligned with
  Python.
- Migration 350 remains unchanged. Its trigger blocks selected status updates
  only when `app.agent_id` is set; that setting is not a database-authenticated
  identity, and inserts are not covered. It is not treated as a least-privilege
  agent boundary.
- The legacy Python `set_agent_context()` helper now fails closed before it
  issues SQL. `SET LOCAL app.agent_id` cannot authenticate the caller, so
  retaining a callable setter would invite code to mistake an arbitrary session
  value for a trusted agent principal. Current production code has no callers.
  Signed worker context and authenticated operator context remain the supported
  identity patterns; the shared synthesis draft writer now records the worker
  principal, while the source-query code still needs runtime least-privilege
  and populated task-parity acceptance.
- The current source inventory identifies no literal direct DML site in
  `services/agents`. The standalone AI-summary helper and shared synthesis
  agents persist through the signed worker adapter; the legacy agent-action
  write and global-read helpers fail before database access because their
  caller-supplied `agent_id` and unscoped query do not authenticate a principal.
  The inventory pins one authenticated Gateway draft call and four signed-worker
  summary calls (lookup, create, source-reference attach, and read), with no
  calls to `set_agent_context()` or `audit_agent_action()`. It records source
  locations and table names, not SQL text or runtime values; dynamic SQL may be
  missed. This is source coverage, not proof of role privileges or runtime
  reachability
  ([inventory](agent-write-boundary-inventory.json);
  [checker](../../scripts/agent_write_boundary_inventory.py)).

## Location-scoped AI-summary draft and human-review slice

Migration 521 introduced the bounded location review queue and decision path.
Migration 522 adds an OIDC `POST /operator/api/ai-summaries/{location_id}/drafts`
operation under the exact `ai_summary:draft` grant and signed transaction-bound
operator context. It runs the deterministic existing summary generator on the
same location-scoped connection, records the authenticated operator in
`ai_summary.created_by`, and stores an append-only request receipt. An exact
request retry returns the saved draft before regenerating; a reused request ID
for another location or summary type fails closed. Runtime and Directus cannot
read or mutate the private receipt table or invoke its functions directly.

The operator console exposes draft creation only for the exact draft scope,
uses same-origin no-store requests, CSRF, stable request IDs, and safe text
rendering. Review remains a separate exact `ai_summary:review` operation.
PostgreSQL marks self-authored rows with a `self_review` blocker and refuses
both approval and rejection by the requester. An independent reviewer may move
a valid draft from `draft`/`submitted` to `verified`; publication remains
separate. The agent safety constraint now permits `verified`/`published` for an
attributed summary only when a different reviewer and review timestamp are
recorded. Legacy drafts with `created_by IS NULL` are explicitly marked
`creator_unattributed`, may be rejected, and may not be verified.

This does not identify background/legacy agent runs: the existing CLI and other
agent writers still use the shared database role and do not persist an
authenticated requester. Their unattributed drafts remain approval-blocked.
Migration 523 adds an append-only private source manifest for new authenticated
deterministic drafts. The generator records exact row counts and up to 50 ordered record IDs per
location-owned source table; larger source sets are marked as sampled.
The sensor manifest tracks only the three most frequent types shown, and
the expense manifest tracks only the five configured categories shown;
both selections use deterministic tie ordering. PostgreSQL checks every
supplied record against the exact location, binds manifests to the authenticated request receipt, and exposes
them only through exact location draft/review functions. The console renders
the row IDs safely under the existing review grant. Draft generation uses
`REPEATABLE READ` so summary values and references share one database snapshot.
Migration 524 extends the manifest to shared `crop` and `expense_category`
records only when they are linked through this location's verified sales or
the displayed top-five verified expense categories. The setter checks those
relationships and the drafter role receives only the needed source columns.
Old summaries are not backfilled; other global references, legacy/background
agent sources, and full source snapshots remain outside this slice. The row
references help locate evidence but do not prove its content.

Migration 529 adds a second, isolated write path for background agents. The
`services.agents.worker_draft` adapter accepts output already generated by its
caller, reads only the `agent_summary_draft` worker credential and dedicated
database URL, switches to `kokonut_worker_execution`, establishes the signed
exact-location `ai_summary:draft` context, and calls a bounded function. The
database stores the worker principal separately from `created_by`, uses a
private append-only request receipt, and permits an independent operator to
review the resulting draft through the existing review workflow. A worker
credential has no table-level summary write or private-receipt access. The
database rejects duplicate source-table hints and mismatched location scope.
Migration 530 extends that path with the same private bounded source-reference
manifest used by authenticated operator drafts. The adapter validates a maximum
of ten declared source tables, fifty unique UUIDs per table, exact sample
counts, and a 64 KB serialized bound before opening the worker connection. It
attaches references in the same transaction as draft creation, then reads the
stored manifest through an exact worker/location/request function. PostgreSQL
rechecks source row ownership under forced-RLS disposable acceptance; a failed
attachment rolls back both draft and receipt. The existing reviewer queue includes these references, and the
operator setter behavior remains covered. This applies only to the new signed
worker adapter; legacy/background writers still lack row-level manifests.

The database creates a locked, dedicated `kokonut_agent_summary_draft_login`
role that may switch only to the bounded worker execution role. A one-shot
`services.agents.worker_cli` exercises this path for the four deterministic
AI-summary types and the ten registered shared synthesis tasks. Shared
`SynthesisAgent` storage delegates to the signed adapter instead of writing
`ai_summary` directly. The worker checks the stable request receipt before
source queries, runs reads inside a bounded read-only transaction using the
runtime database identity, and creates the draft through the separate signed
worker connection. Capital-efficiency, bio-factory, and regenerative synthesis
attach bounded row IDs for twelve exact-location published summary views through
the same private manifest. The base agent contract accepts a fixed per-agent
query and view map, collects IDs inside the source read's repeatable-read
snapshot, excludes the bio-factory's network-wide regional catalogue, and keeps
global governance records out of the location-scoped regenerative references.
Migration 532 creates the migration-owned view map; migrations 532–533 register
the bio-factory and regenerative views. PostgreSQL rechecks exact counts and
sampled IDs through the matching public view before attachment. Other generic synthesis
tasks still persist table-name hints without row-level source manifests; the
deterministic AI-summary path also attaches the bounded manifest. On replay,
generic task callers receive the
stored draft text and receipt rather than regenerating the task's full structured
output. Compose exposes the dedicated DSN and high-entropy credential only to
the opt-in `agent-summary-worker` service. An operator still needs to provision
the runtime password, worker login/password, worker credential, and service DSN;
migrations 529–533 are not rolled out to the candidate. Stored shared-agent CLI
output is reduced to the draft ID, request ID, status, and replay flag. For
example, run a task through the isolated profile with
`--task-key feedback_synthesis --location-id UUID --request-id UUID`. The database acceptance
uses a synthetic operator-context stub for its review step; production worker
identity is exercised with migration 405's signed worker context. See the
[worker adapter](../../services/agents/worker_draft.py),
[migration 529](../../schemas/postgres/529_signed_agent_ai_summary_drafts.sql),
[migration 530](../../schemas/postgres/530_signed_agent_ai_summary_source_references.sql),
[migration 531](../../schemas/postgres/531_capital_efficiency_synthesis_source_references.sql),
[migration 532](../../schemas/postgres/532_registered_agent_source_reference_views.sql),
[migration 533](../../schemas/postgres/533_regenerator_synthesis_source_references.sql),
[focused tests](../../tests/test_agent_worker_draft.py),
[capital-efficiency tests](../../tests/test_capital_efficiency.py),
[bio-factory tests](../../tests/test_bio_factory_operations.py),
[regenerator tests](../../tests/test_regenerative_outcomes.py),
[worker orchestration tests](../../tests/test_agent_worker_cli.py),
[disposable checker](../../scripts/check-agent-worker-ai-summary-disposable.py),
and [capital-efficiency evidence](builds/2026-10-21-recovery/cap-038-capital-efficiency-source-references-disposable.json).
The [registered-view evidence](builds/2026-10-21-recovery/cap-038-bio-factory-source-references-disposable.json)
also covers migration 532 replay and the bio-factory mappings.
The [regenerative-view evidence](builds/2026-10-21-recovery/cap-038-regenerator-source-references-disposable.json)
covers migration 533 replay, location matching, and cross-location rejection.

The focused Gateway, route-policy, console, source-reference, and safety
selection passes 64 tests with nine PostgreSQL-dependent skips; Ruff, Python
compilation, and JavaScript syntax checks pass. Disposable PostgreSQL 16
applies/replays migrations 521–524 on a network-disabled container and passes
12 grouped draft/review, attribution,
idempotency, location binding, manifest privacy/immutability, self-review,
legacy-blocker, lifecycle, and privilege checks. Candidate and legacy
databases remain untouched; migration 524 is not rolled out. See the
[migration 521](../../schemas/postgres/521_location_scoped_ai_summary_review.sql),
[migration 522](../../schemas/postgres/522_authenticated_ai_summary_drafts.sql),
[migration 523](../../schemas/postgres/523_ai_summary_source_references.sql),
[migration 524](../../schemas/postgres/524_ai_summary_global_source_references.sql),
[draft Gateway tests](../../tests/test_gateway_ai_summary_draft.py),
[review Gateway tests](../../tests/test_gateway_ai_summary_review.py),
[source reference tests](../../tests/test_ai_summary_source_references.py),
[console checks](../../tests/test_operator_console_ai_summary_review.py), and
[disposable evidence](builds/2026-10-20-recovery/cap-038-ai-summary-global-source-references-disposable.json).

## Verification and limits

The standalone `ai_summary` CLI validates required mode selection and UUID
arguments before opening PostgreSQL. Generation delegates directly to the
validated runner rather than opening and discarding a preliminary connection.
List and verify modes acquire a connection only for their query and close it in
`finally`; verify also closes its cursor when the query fails. Focused offline
CLI checks exercise missing/malformed inputs and cleanup failures. This is a
resource-lifecycle and input-preflight guarantee only: the CLI still uses its
configured database principal and does not authenticate an operator or establish
tenant authorization. The legacy `--verify` option is a read-only inspection:
it computes a SHA-256 digest without comparing it to a stored digest and never
changes lifecycle status, so it is not the human-review action. Summary listing
requires an exact location filter or explicit `--all-locations`; the unfiltered
inventory omits summary previews, while a location-scoped list retains its
preview field.

Focused source tests cover all current catalogue write declarations, defensive
copy behavior, denied high-risk actions, malformed policy input, and preflight
before database access. These checks do not establish Directus runtime-role
parity, authenticated agent identity, database table isolation, provider/model
behavior, populated task parity, or human approval workflow acceptance. Those
remain open gates for MAN-CAP-038.
