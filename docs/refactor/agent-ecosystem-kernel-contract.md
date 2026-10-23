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

Every `SynthesisAgent.run()` now requires an exact location and a class-declared
source-reference view map, then dispatches both read-only and draft work through
the registered signed worker. An unmapped subclass fails before any database
access. The legacy generic `run_fetch()` symbol remains only to return a clear
retirement error before invoking its callback or accessing a database; the
repository has no production call sites. The legacy
`SynthesisAgent.store_summary(conn, ...)` writer is also retired; it no longer
queries provenance on a caller-provided connection. The registered worker
generates the result, collects source references, and persists a draft within
its signed flow. These changes prevent future subclasses from silently
inheriting the broad runtime login. They do not provision worker credentials
or grants, authenticate the human operator, or cover non-synthesis agent
tasks.

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
- The compatibility `SynthesisAgent.store_summary()` path now also collects
  references declared in its fixed public-view map from the caller-supplied
  source connection and includes them in the signed worker write, after checking
  the agent's read policy for its declared collection. A denied read or source
  collection failure prevents draft persistence. This helper does not itself
  establish a repeatable-read snapshot or authenticate/limit the source
  connection; the canonical one-shot worker remains the path that combines
  source reads and provenance in a bounded read-only snapshot.
- Existing output validation, EBF maturity limits, human-governed collection
  restrictions, and read behavior remain in place.
- Optional Directus hooks keep their role and lifecycle checks. The action-log
  hook marks `verify` as high risk so the audit surface remains aligned with
  Python.
- Migration 350 remains unchanged, but migration 578 replaces the active
  trigger function so it blocks verified/published status changes from
  authenticated `kokonut_worker_execution` logins, including calls routed
  through `SECURITY DEFINER` functions. Migration 579 adds terminal-status
  insert guards to the same 43 tables that had migration 350 update triggers.
  The caller-set `app.agent_id` marker remains an extra restrictive
  compatibility signal and does not establish identity. Migration 579 covers
  terminal inserts on the same 43 tables as migration 350's update triggers;
  the disposable fixture exercises all 43 names, while full ARM64/QEMU schema
  replay confirms migration application. Per-agent identities, protection for
  other governed tables, RLS, and source-query least privilege remain open; this
  is not a complete agent boundary ([migration 578](../../schemas/postgres/578_authenticated_agent_safety_trigger.sql);
  [migration 579](../../schemas/postgres/579_agent_safety_insert_guard.sql);
  [disposable evidence](builds/2026-10-22-recovery/cap-038-agent-safety-insert-disposable.json);
  [ARM64/QEMU evidence](builds/2026-10-22-recovery/arm64-qemu-current-schema-579.json)).
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
Old summaries are not backfilled; other global references in the deterministic
operator-draft path, legacy/background agent sources, and full source snapshots
remain outside that slice. The row
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
AI-summary types and the twelve registered synthesis tasks. Shared
`SynthesisAgent` storage delegates to the signed adapter instead of writing
`ai_summary` directly. The worker resolves every synthesis task through its explicit twelve-module
registry, checks the registered class and class-declared metadata before any
receipt lookup, including its optional fixed `source_reference_query`. The
collector reads the class-registered query and view map rather than an
instance-shadowed value. Focused regressions prove a query override is ignored
by collection and rejected before receipt lookup. This protects the reviewed
in-process provenance contract; it does not authenticate Python code or replace
the worker's signed database scope. The worker checks the stable request
receipt before source queries and runs reads inside a bounded repeatable-read,
read-only transaction. Migrations 580–593 give each registered synthesis task
its own signed source login and reader role, with an exact `ai_summary/read`
grant before querying. The task reader's approved security-barrier wrappers call the database-signed
`current_worker_scope` function on every view read: location views expose only
the granted location, mixed views add explicitly unassigned records, and
network views expose public catalogs only after the same exact-location grant.
The raw public views, worker credential/grant tables, writes, and schema CREATE
remain denied to that source identity. Python filters mirror those database
scopes as defense in depth. Migration 544 applies the same signed-location
pattern to the deterministic summary worker's 13 relations: 11 operational
sources are exact-location filtered, while crop and expense category remain
shared network catalogs. That worker installs the wrapper schema first in its
transaction-local search path, so its legacy query text resolves to filtered
views and the deterministic source login cannot read the original public
relations. Read-only deterministic generation uses this signed source path
without creating a draft. All twelve registered `SynthesisAgent` classes use
their task-specific signed source reader for read-only `run()` calls and draft
generation; unregistered source contracts fail closed before connecting.
Migration 594 disables the historical shared synthesis login, removes its
reader membership and direct privileges, and verifies that the retained
compatibility roles are inert.
Listing and digest-inspection CLI operations remain separate read paths and
need their own operator authorization review. These are scoped source
boundaries for the deterministic and task-specific worker profiles, not a
universal RLS rollout.
Other service/database paths retain separate tenant-boundary reviews.

The EBF evidence-gap reader uses its own credential and connection identity.
Migration 545 creates a security-barrier wrapper filtered through the database-
signed `ebf_scorecard/read` scope and exposes only the scorecard/location keys
and columns consumed by the EBF query. Migration 580 gives this worker a
separate SET-only login and reader role with SELECT on that single projection;
it cannot select synthesis, CIDS, or Delphi views. It runs in a repeatable-
read, read-only transaction and rolls back on failure. Credential and location-
grant provisioning, live runtime acceptance, and operator authorization remain
separate work.

The CIDS Essential Tier export uses its own credential and connection
identity under an exact `cids_export/read` grant. Migration 546 adds six minimal security-barrier
projections for the location, published outcomes, impact mappings, verified
metrics, consent-eligible feedback metadata, and verified impact claims. The
feedback wrapper deliberately excludes the public-summary text; the existing
graph builder receives only the fields declared by the projection contract.
Migration 580 gives CIDS a separate SET-only login and reader role with SELECT
on those six projections only; EBF, Delphi, and synthesis projections are
outside its SQL privileges. The worker establishes signed context before
switching to the NOLOGIN reader and runs in a repeatable-read, read-only transaction. Migration-owned RLS
policies constrain the shared source-view owner to the current exact CIDS
location and separately preserve the existing `ai_summary/read` views. The
optional `cids-export-worker` Compose profile receives the source DSN and
credential only. This does not establish populated-output parity, operator
grant provisioning, live runtime acceptance, or universal RLS.

The native PostgreSQL 16 chain through migration 546 passes 33 grouped checks,
including migration replay, no-context denial, exact-location filtering,
mixed/network behavior, denial for an ungranted location, raw-view and
credential-table access denial, EBF stale-grant cleanup, CIDS forced-RLS
location scope, CIDS raw-table denial, and preservation of AI-summary scope.
The focused CIDS/worker/task/preflight/profile selection passes 88 tests; Ruff,
Python compilation, migration validation, and static worker inventories pass.
Candidate and legacy databases remain untouched; migrations 543–546, source
credentials, and exact location grants have not been deployed. ARM64/QEMU
source-boundary evidence is software emulation only and does not establish
physical Raspberry Pi or full-schema acceptance ([native CIDS evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-disposable.json);
[ARM64/QEMU CIDS evidence](builds/2026-10-22-recovery/cap-038-cids-export-source-worker-arm64-disposable.json);
[native EBF evidence](builds/2026-10-22-recovery/cap-038-ebf-evidence-gap-source-worker-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-deterministic-summary-source-views-arm64-disposable.json)).
Catalogue-only write tasks cannot enter this `ai_summary` worker path. Capital-efficiency, bio-factory, regenerative, Commons, GNH,
Financial Resilience, Open Source Capitalist, Wellbeing, Feedback, and
Kokonut Commons synthesis attach bounded row IDs for forty approved public
summary views through the same private manifest. The migration-owned registry
declares each source as `location` (exact requested farm), `network` (public
network catalogue), or `location_or_network` (exact farm plus explicitly
unassigned shared rows). The base agent contract builds a bounded query from
the registered scope and static view map, collecting IDs inside the source
read's repeatable-read snapshot. No row from another location may enter a
manifest. Network-wide IDs are explicitly labeled and never relabeled as
farm-owned. Migration 540 registers six network-wide views, promotes six
public-safe shared policy/economic views to mixed scope, and grants the drafter
only the ID columns needed to revalidate network rows and ID/location columns
for mixed rows. PostgreSQL checks exact counts and sampled IDs against these
views; the operator review queue preserves the scope labels. Migrations 532–536
register the preceding location-owned views. Migration 537 constrains new
signed-worker draft receipts to the four
deterministic and twelve registered synthesis summary types while preserving
historical receipt reads.
PostgreSQL rechecks exact counts and sampled IDs through the matching public
view before attachment. Other generic synthesis
tasks still persist table-name hints without row-level source manifests; the
deterministic AI-summary path also attaches the bounded manifest. Migration 539
stores each new worker call's bounded structured result in a private append-only
receipt in the same transaction as its draft. Exact retries return that original
JSON result without rerunning source queries. Receipts created before migration
539 have no structured result to reconstruct and keep the content-only
compatibility fallback. Compose separates deterministic summaries from each
task-specific synthesis profile. `agent-summary-worker` uses a dedicated source login limited to the
13 source relations read by the four built-in summaries, requires the fixed
`--deterministic-only` mode, and receives no shared `PG_*`, `DATABASE_URL`, or
`POSTGRES_PASSWORD` values. Each synthesis profile names one registered task
and receives only that task's signed, filtered source login; migration 593
moves the final five Kokonut Commons projections off the broad reader, and
migration 594 disables the historical shared source login and strips its
residual grants. Migration 595 lets deterministic and registered synthesis
task identities create drafts through a function-only writer role; these
logins do not join broad `kokonut_worker_execution`. Before draft creation, a
function derives the task key from the authenticated PostgreSQL session login
and binds it to the signed worker ID in a private attribution table. Reviewers
can read that narrow mapping without querying `worker_principal` through its
forced RLS policy. The review queue disables verification for unregistered
worker identities, and a database trigger enforces that rule while still
allowing a human to reject an unregistered legacy draft. No generic shared
synthesis profile remains.

Migration 596 adds `list_location_ai_summary_reviews_with_worker_run` as the
review-facing wrapper. It calls the existing signed, bounded task-review
function, then joins the request receipt only by the returned summary ID and
the requested location. The wrapper returns the receipt's opaque `request_id`
as `creator_run_id`; it does not expose the worker principal or the request
hash. The reviewer role has column-only SELECT on the receipt's request,
summary, and location IDs. Runtime, Directus, and task writers cannot query the
receipt table directly, and only the runtime may call the wrapper. The operator
console displays the identifier as an agent run. It identifies a worker request
and does not establish which human initiated it; human-initiated run attribution
remains open.
Each task that stores drafts needs its own exact `ai_summary:read` and
`ai_summary:draft` grants at the selected location. Synthesis reads enforce
each location grant at the database view boundary, and deterministic summaries
use a separate signed, location-filtered view boundary. The remaining
runtime/RLS review is open. An operator still needs to provision the runtime
password, task source login/password pairs, worker credentials, separate
  location grants, and service DSNs; migrations 529–596 are not rolled out to
the candidate. Stored agent CLI output is reduced to the
draft ID, request ID, status, and replay flag. For example, run a task through
the isolated profile with
`--task-key feedback_synthesis --location-id UUID --request-id UUID`. The database acceptance
uses a synthetic operator-context stub for its review step; production worker
identity is exercised with migration 405's signed worker context. See the
[worker adapter](../../services/agents/worker_draft.py),
[migration 529](../../schemas/postgres/529_signed_agent_ai_summary_drafts.sql),
[migration 530](../../schemas/postgres/530_signed_agent_ai_summary_source_references.sql),
[migration 531](../../schemas/postgres/531_capital_efficiency_synthesis_source_references.sql),
[migration 532](../../schemas/postgres/532_registered_agent_source_reference_views.sql),
[migration 533](../../schemas/postgres/533_regenerator_synthesis_source_references.sql),
[migration 534](../../schemas/postgres/534_public_synthesis_source_reference_views.sql),
[migration 535](../../schemas/postgres/535_consent_safe_wellbeing_feedback_source_views.sql),
[migration 536](../../schemas/postgres/536_location_scoped_kokonut_commons_source_views.sql),
[migration 537](../../schemas/postgres/537_registered_worker_summary_types.sql),
[migration 540](../../schemas/postgres/540_scoped_agent_source_references.sql),
[migration 541](../../schemas/postgres/541_agent_synthesis_source_reader.sql),
[migration 542](../../schemas/postgres/542_agent_deterministic_summary_source_reader.sql),
[migration 543](../../schemas/postgres/543_tenant_scoped_agent_synthesis_source_views.sql),
[migration 544](../../schemas/postgres/544_tenant_scoped_deterministic_summary_source_views.sql),
[focused tests](../../tests/test_agent_worker_draft.py),
[capital-efficiency tests](../../tests/test_capital_efficiency.py),
[bio-factory tests](../../tests/test_bio_factory_operations.py),
[regenerator tests](../../tests/test_regenerative_outcomes.py),
[multi-agent source-reference tests](../../tests/test_synthesis_source_references.py),
[worker orchestration tests](../../tests/test_agent_worker_cli.py),
[disposable checker](../../scripts/check-agent-worker-ai-summary-disposable.py),
and [capital-efficiency evidence](builds/2026-10-21-recovery/cap-038-capital-efficiency-source-references-disposable.json).
The [registered-view evidence](builds/2026-10-21-recovery/cap-038-bio-factory-source-references-disposable.json)
also covers migration 532 replay and the bio-factory mappings.
The [regenerative-view evidence](builds/2026-10-21-recovery/cap-038-regenerator-source-references-disposable.json)
covers migration 533 replay, location matching, and cross-location rejection.
The [multi-agent view evidence](builds/2026-10-21-recovery/cap-038-public-synthesis-source-references-disposable.json)
covers migration 534 replay, the 15 new mappings, and exact view-column grants.
The [consent-safe evidence](builds/2026-10-21-recovery/cap-038-wellbeing-feedback-source-references-disposable.json)
covers migration 535 replay and rejection of private/no-consent feedback IDs.
The [Kokonut Commons evidence](builds/2026-10-21-recovery/cap-038-kokonut-commons-source-references-disposable.json)
covers migration 536 replay and exclusion of unassigned/network-wide policies.
The [registered-summary-type evidence](builds/2026-10-21-recovery/cap-038-registered-worker-summary-types-disposable.json) covers migration 537 replay, all fourteen supported types, and atomic rejection of an unregistered type.
The [scoped-source evidence](builds/2026-10-22-recovery/cap-038-scoped-agent-source-references-disposable.json)
covers migration 540 replay, all three scope modes, cross-location rejection,
ID-only drafter grants for network views, and scope-label preservation in the
operator review queue. The same evidence now covers migration 541 replay and
the source-reader's explicit SELECT grants on the 40 approved public views,
the permitted PostGIS metadata catalog names, denial of private summary and other
application-relation reads, and no-write privileges. That database identity
reduces relation access but remains separate from tenant RLS acceptance.
The [signed synthesis source-view evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-agent-synthesis-source-views-disposable.json)
covers migration 543 replay, no-context and ungranted-location denial, exact
location filtering, shared and network scope, and denial of direct raw-view and
credential-table access.
The [deterministic summary source-view evidence](builds/2026-10-22-recovery/cap-038-tenant-scoped-deterministic-summary-source-views-disposable.json)
covers migration 544 replay, setter-only source-login access, no-context and
ungranted-location denial, exact-location operational filtering, network
catalog access, and denial of raw relations and writes.

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
arguments before worker dispatch. Generation delegates directly to the
validated deterministic runner. Listing uses a dedicated inspection login and
NOLOGIN reader role; digest inspection uses that same signed identity through
the [migration 581](../../schemas/postgres/581_isolated_ai_summary_inspection_worker.sql)
digest-only projection. The source login sets the
signed `ai_summary/read` context, then switches to the reader role in a
repeatable-read, read-only transaction. Both operations require one exact
`--location-id`; the former global `--all-locations` inventory is removed. The
list view returns at most twenty rows with an 80-character preview. Digest
inspection reads one exact ID/location pair and returns only metadata, content
length, and a database-computed SHA-256 digest; it never returns summary
content to Python. The inspection role cannot read deterministic operational
source views or the raw `ai_summary` table, and its login has no direct view or
digest-function grant. The digest does not change lifecycle status or compare a
stored digest, so it is not the human review action. Disposable PostgreSQL
checks exercise both views under forced RLS, no-context and foreign-location
denial, raw-table and operational-source denial, migration replay, and stale
grant cleanup. This establishes the database read boundary and worker
authorization contract; it does not authenticate a human operator, provision
production credentials/grants, prove populated parity, or complete MAN-CAP-038.

Focused source tests cover all current catalogue write declarations, defensive
copy behavior, denied high-risk actions, malformed policy input, preflight
before database access, and location-view collector/adapter contracts for all
ten shared synthesis agents. These checks do not establish Directus runtime-role
parity, authenticated operator identity, database table isolation,
provider/model behavior, populated task parity, or human approval workflow
acceptance. Those remain open gates for MAN-CAP-038.

Delphi recommendation generation now returns only an in-memory suggestion from
the agent path. The legacy facilitator and CLI draft, list, approve, and reject
methods fail closed before opening a database connection; persisted drafts and
review decisions must use the authenticated, location-scoped Delphi Gateway
routes. This prevents caller-supplied actor IDs and unscoped recommendation
reads from bypassing the CAP-027 request receipts and review audit. It does not
retire other legacy Delphi study or panel operations, or establish live OIDC,
browser, runtime-role, or populated-data parity.

## Delphi facilitator agent source boundary

The agent-facing live summary takes both `study_id` and `location_id`, validates
them before opening a connection, and reads only through
`kokonut_agent_source.delphi_live_summary`. Migration 548 binds that
security-barrier projection to a signed `delphi/read` scope on the exact
location. The projection recalculates from currently consented panel members;
it withholds panel and item aggregates until the greater of three and the
study's configured minimum participant count is met. It never returns
participant display tokens or contribution reasoning.

The Delphi source worker has a separate credential, SET-only login, and
NOLOGIN reader role. Migration 580 grants it SELECT on `delphi_live_summary`
only; it cannot query synthesis, EBF, or CIDS projections. The connection runs
repeatable-read/read-only and switches to that reader before selecting the
exact study/location pair.
The in-memory recommendation suggestion includes the same location scope;
persistence and review remain on the authenticated Delphi Gateway routes.
This closes the agent facilitator's shared-runtime read path only. The legacy
`services.delphi.cli live-summary` and `consensus` commands now call the same
signed source adapter and require the exact location UUID. The legacy unscoped
study-list command fails before database access. Other panel/study operations,
authenticated operator grant provisioning, populated parity, live OIDC/runtime behavior,
Directus parity, and MAN-CAP-038 acceptance remain open. Migration 548 is
additive: reverting the CLI/worker/profile leaves the view and policy unused;
retain the migration if it has been applied.
