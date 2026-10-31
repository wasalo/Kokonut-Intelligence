# gateway

`services.gateway` — Unified API Gateway — single entry point for all API traffic.

## Run

The Compose command below starts the **legacy** integration service. For the
Kernel candidate, use `python3 scripts/kernel-profile.py minimal --action up`
and review the printed isolated Compose command; its application service is
named `app`, and the candidate status guide documents the current port and
acceptance limits.

```bash
# Legacy Compose only (Caddy routes /mobile and /api/mobile/*)
docker compose up -d gateway

# Host process
python3 -m services.gateway.cli --serve --port 8099
python3 -m services.gateway.cli --help
```

Legacy Caddy Field Collector: `https://localhost/mobile/` (or
`https://<lan-ip>/mobile/` on the LAN). The Kernel candidate's local route is
served from the candidate origin; see the
[Field Collector guide](../../docs/field-data-collection-guide.md) and
[current candidate status](../../docs/refactor/current-state-and-implementation.md)
for its deployment and HTTPS acceptance limits.

The OIDC operator API exposes a location-scoped, aggregate-only true-cost read
at `GET /operator/api/true-cost/{location_id}/summary`. It requires the
`true_cost_accounting:read` grant for that location and uses signed database
tenant context in a read-only transaction. It returns statement, hidden-cost,
natural/social valuation, and capital-flow summaries; it does not expose
individual worker or evidence records.

Emergency response aggregates are available to authorized operators at
`GET /operator/api/emergency-response/{location_id}/summary` with the
location-specific `emergency_response:read` grant. The read-only response
contains counts, recovery/deadline measures, affected-area and financial
aggregates; it excludes incident descriptions, actions, support notes, lessons,
and individual incident rows.

Governance-circle operations have an aggregate read at
`GET /operator/api/governance/{location_id}/summary` for operators with the
location-specific `governance_roles:read` grant. The signed-tenant, read-only
response includes circle review state and counts for roles, assignments,
authority domains, tensions, and tactical items. It excludes stakeholder
identities, policy text, tension descriptions, session notes, and requested
actions.

The read-only tension review queue is available at `GET
/operator/api/governance/{location_id}/tensions`, with an optional queue status,
bounded page size, and opaque `cursor` for keyset pagination. Detail is
available at `GET
/operator/api/governance/{location_id}/tensions/{tension_id}`. Both require
the exact location-specific `governance_tension:read` grant and signed tenant
context. Only submitted, triaged, in-progress, and deferred records appear;
page size is capped at 100 and event history at 100 entries. The projection
omits reporter and affected-party identities, evidence, private metadata,
event notes, and actor IDs. The console renders the review projection as text.
These route checks and their bounded database functions do not establish
universal tenant isolation or domain-table RLS.

Location governance roles are available at `GET
/operator/api/governance/{location_id}/roles` with the exact
`governance_roles:read` grant. The bounded read-only registry returns role and
circle labels, lifecycle dates, and aggregate accountability, assignment, and
authority-domain counts; it omits party identities and policy text. Role detail
is available at `GET
/operator/api/governance/{location_id}/roles/{role_id}` under the same grant.
It returns active accountability descriptions and applicable authority-domain
keys, levels, scope types, and human-approval flags, capped at 100 entries per
list. It omits assignee identities, role-policy text, evidence expectations,
and arbitrary constraint metadata. A role outside the requested location or
the reviewable role/circle states returns the same 404 response.

The tactical session registry is available at `GET
/operator/api/governance/{location_id}/tactical-sessions` with the exact
`governance_tactical:read` grant. It returns location-scoped session state,
circle labels, scheduled time, and bounded item counts; agenda text, notes,
outcomes, and party identities are excluded. Signed tenant context, read-only
transactions, and keyset pagination capped at 100 protect the projection.
Open tactical work is available at `GET
/operator/api/governance/{location_id}/tactical-items` under the same exact
grant. It returns bounded open/in-progress items, requested action, priority,
due date, session summary, and owner role key, but omits party identities,
session notes, agenda text, and disposition detail. The console renders both
projections as text.

Scheduling a session uses `POST
/operator/api/governance/{location_id}/tactical-sessions` with the exact
`governance_tactical:create` grant and CSRF protection. The request supplies an
active same-location circle UUID, supported session type, title, reason, and
optional timezone-qualified schedule, same-circle active facilitator/recorder
roles, and agenda scope. PostgreSQL always creates a `planned` session; notes,
outcomes, status, actor identity, and timestamps cannot be supplied. Request-key
retries are idempotent, and immutable actor/reason history commits with the
session. Runtime and Directus direct inserts are revoked and guarded.

Tactical item changes use three separate POST routes ending in `/{item_id}/start`,
`/{item_id}/dispose`, or `/{item_id}/cancel`; each requires its own location
grant (`governance_tactical:start`, `:dispose`, or `:cancel`), CSRF, signed
operator context, an active operator/person binding, and a reason. Starting an
item is limited to its assigned person or a current non-recused holder of its
same-location owner role. Completed sessions may still have follow-up actions;
cancelled sessions and inactive circles cannot be changed. Disposal is allowed
only from `in_progress` and requires an allowed disposition type and outcome
summary; cancellation is limited to open or in-progress work. Each transition
and its immutable actor/reason/request ledger
entry commit atomically. Exact retries replay; key reuse with changed content
and stale lifecycle transitions conflict. Gateway and Directus runtime roles
cannot directly mutate tactical items or read the private action ledger. These
ACLs do not establish domain-table RLS for unrelated governance queries.

Role nominations use
`POST /operator/api/governance/{location_id}/roles/{role_id}/assignments`
with the separate location-scoped `governance_roles:create` grant. The request
requires a caller-generated `request_id`, active nominee party UUID,
assignment type, and an optional mandate (required for delegates). A signed
operator context and active operator/person binding attribute the request.
The bounded database function creates only a `proposed` assignment and writes
an immutable idempotency/attribution record; it cannot activate or reject an
assignment. A distinct review queue and approve/reject routes require their
own grants, active person binding, and a reviewer different from the proposer.
Direct assignment-table writes are revoked from the runtime and Directus roles.
Before rollout, inspect the selected target's ordered migration ledger and
effective runtime-role membership. Repository source does not establish which
migrations or credentials are active in a database, and these function/table
boundaries do not imply universal tenant isolation.

The operator console lets a separately authorized creator submit a nomination
using an active person-party UUID and review the status of their own submissions
at `GET /operator/api/governance/{location_id}/assignment-proposals`. Migration
439 enforces same-operator and same-location readback with bounded keyset
pagination. The status projection excludes nominee identity and mandate; the
console does not enumerate a people directory or provide decision controls.

Governance circle and role definitions are created through
`POST /operator/api/governance/{location_id}/circles` and
`POST /operator/api/governance/{location_id}/roles` under
`governance_roles:create`; both always create location-scoped drafts. `PATCH`
on a specific circle or role uses `governance_roles:update` and accepts only
descriptive fields while the definition remains draft. All writes require a
reason, request UUID, signed tenant context, and active operator/person
binding. Migration 443 stores immutable before/after history and blocks runtime
and Directus direct writes. The editor loads circle fields from the no-store
`GET /operator/api/governance/{location_id}/circles/{circle_id}` route, which
requires both exact `governance_roles:read` and `:update` grants; aggregate
summaries continue to exclude circle free text. Lifecycle review and activation
remain separate routes and grants; accountabilities, authority domains, and
policies are not part of this editor. Before applying migrations 442–443 to a
target, verify its database identity and runtime-role configuration using the
selected deployment's migration ledger and Compose profile.

Governance tension intake is available at `POST
/operator/api/governance/{location_id}/tensions` with a caller-generated UUID
`request_id`, title, description, supported tension type, severity, and urgency.
The same operator may submit its own draft through `POST
/operator/api/governance/{location_id}/tensions/{tension_id}/submit`. Both routes
require exact `governance_tension:create` or `governance_tension:submit`
location grants, OIDC/CSRF, and signed tenant context. Submission only moves a
report from draft to submitted. The lifecycle endpoint
`POST /operator/api/governance/{location_id}/tensions/{tension_id}/actions/{action}`
supports `triage`, `start`, `link`, `link_work_item`, `resolve`, and `defer`;
each action requires its matching location grant
(`governance_tension:<action>`), CSRF, signed tenant context, a current operator
person binding, and a reason/request ID. Triage assigns an owner and may set a
review deadline; links are location-validated; resolution and deferral carry
bounded summaries or timestamps. The database function applies state changes,
idempotency receipts, and lifecycle history atomically. Migration 700 must be
present in the selected target's ordered migration ledger before these actions
can run. Verification, publication, and governance approval remain separate
human-controlled processes.

An administrator maps OIDC operators to governance people using explicit UUIDs
with `python3 -m services.cli operator identity party bind|revoke|list`. This
mapping is never inferred from email or display name. The provisioning commands
use the `kokonut_governance_identity_admin` database role; grant that role only
to an administrative database login, never to the Gateway or Directus runtime.

Stored Celo attestation metadata can be read at
`GET /operator/api/attestations/{location_id}` with the location-specific
`attestation:read` grant. The route excludes claim payloads, evidence references,
and review notes. It reports persisted database state and does not verify a
live EAS contract or chain result.

Location ecocredit batches are available at
`GET /operator/api/ecocredits/{location_id}/batches` with the location-specific
`ecocredit:read` grant. The read-only response separates batch quantities from
aggregated tradable, retired, and escrowed ledger totals, preserves four-decimal
precision, and omits wallet addresses and account-level balances. It does not
issue, transfer, retire, or verify credits.

Carbon-credit custody summaries are available at
`GET /operator/api/credit-custody/{location_id}/summary`. Operators need both
`carbon_credit:read` and `credit_retirement:read` for the location. The summary
reports aggregate reservation and retirement status quantities separately and
omits beneficiary, wallet, statement, evidence, request-key, and reviewer-note
details. Retirement approval, rejection, cancellation, and chain actions are
not exposed by this read.

Location-scoped produce traceability is available at
`GET /operator/api/traceability/{location_id}/batches` and
`GET /operator/api/traceability/{location_id}/batches/{batch_id}` with an exact
`traceability:read` grant. The list is paginated; detail returns bounded custody,
quality, certification, food-safety, and provenance records. Actor identities,
free text, GPS, evidence URLs, and arbitrary metadata are omitted. These routes
are read-only and do not establish public/community visibility or populated-data
parity; see the [Kernel read contract](../../docs/refactor/traceability-kernel-read-contract.md).

Extension-learning activity is available at
`GET /operator/api/extension-learning/{location_id}/summary` under the exact
location `extension_learning:read` grant. The private read returns grouped
enrollment, delivery, assessment-count, and peer-network/member-count data;
learner identities, scores, notes, contact details, delivery errors, and
arbitrary metadata are omitted. It does not perform enrollments, deliveries,
assessments, or peer-network writes. See the
[Kernel read contract](../../docs/refactor/extension-learning-kernel-read-contract.md).
The same grant can list the paginated active, public module catalog at
`GET /operator/api/extension-learning/{location_id}/modules`, with optional
category, difficulty, and content-type filters. Course URLs and free-text
descriptions are withheld pending content review.

Two location-scoped extension-learning writes are also available: create a peer
network with `POST /operator/api/extension-learning/{location_id}/peer-networks`
under `extension_learning:create_peer_network`, and update a progress record
with `PATCH /operator/api/extension-learning/{location_id}/progress/{progress_id}`
under `extension_learning:update_progress`. Both require signed tenant context,
CSRF, bounded request bodies, and idempotent database receipts; migration 701
must be present in the target ledger. These routes do not enroll learners,
deliver courses, or create assessments.

Landscape conservation has an aggregate read at
`GET /operator/api/landscape/{location_id}/summary` and capture routes at
`POST /operator/api/landscape/{location_id}/habitats`, `/corridors`,
`/hedgerows`, `/buffer-checks`, and `/biodiversity-assessments`. They require
the exact location `landscape_conservation:read` or `:create` grant. Captures
are location-bound, idempotent, and stored in their source lifecycle's initial
state; they do not verify or publish ecological claims. Migration 702 must be
present in the selected target's ledger.

Metric values can be listed at
`GET /operator/api/metrics/{location_id}/values` and created as unverified
drafts with `POST` to the same route, using the respective location-scoped
`metric_value:read` and `metric_value:compute` grants. A separate human
verification uses `POST
/operator/api/metrics/{location_id}/values/{metric_value_id}/verify` and the
`metric_value:verify` grant. Migration 703 must be present in the selected
target's ledger; computation creates a draft and is not verification.

Completed crop-simulation run summaries are available at
`GET /operator/api/crop-simulations/{location_id}/runs` with an exact
location-scoped `digital_twin:read` grant. Results are paginated and include
run timing, yield, water, nitrogen, and soil-carbon summaries. Raw parameter
JSON, metadata, errors, and financial values are excluded. The route reads
persisted completed runs only; it does not execute simulations or claim model
parity. A matching
`GET /operator/api/crop-simulations/{location_id}/runs/{run_id}` route returns
the same allowlisted run summary plus a paginated set of persisted daily soil,
crop, water, weather, and carbon states. Every query is scoped by location and
completed-run lifecycle; state IDs and metadata remain private. See the
[Kernel read contract](../../docs/refactor/crop-simulation-runs-kernel-read-contract.md).

Verified and published nutrient balances are available at
`GET /operator/api/nutrients/{location_id}/balances` with an exact
location-scoped `nutrient_budget:read` grant. The paginated output aggregates
nitrogen, phosphorus, and potassium input, removal, surplus, and area by season
and crop from the canonical verified/published balance view. It omits
plot/budget identifiers, product-level inputs, soil-test notes, and costs. See
the [Kernel read contract](../../docs/refactor/nutrient-balances-kernel-read-contract.md).

Location-scoped soil-test observations and recommendations are available at
`GET /operator/api/nutrients/{location_id}/soil-tests` with the same exact
`nutrient_budget:read` grant. The bounded read retains `recorded` versus
`verified` status, returns measured values and advisory N/P/K rates, and only
includes a plot ID when its farm belongs to the requested location. Notes and
arbitrary metadata are excluded. See the
[soil-test Kernel read contract](../../docs/refactor/nutrient-soil-tests-kernel-read-contract.md).

Nutrient input and harvest-removal records are available at
`GET /operator/api/nutrients/{location_id}/events/inputs` and
`GET /operator/api/nutrients/{location_id}/events/removals` under the same
exact location grant. Each is paginated, retains both event and parent-budget
status, and omits notes, metadata, costs, budget IDs, and unvalidated removal
source text. A plot ID is returned only when its farm belongs to the requested
location. Input costs remain unavailable until the schema defines their
currency. See the
[event Kernel read contract](../../docs/refactor/nutrient-events-kernel-read-contract.md).

Global Baal governance reads are available at:

- `GET /api/v1/governance/baal/config`
- `GET /api/v1/governance/baal/proposals?limit=50` (limit 1–100)
- `GET /api/v1/governance/baal/proposals/{proposal_id}`
- `GET /api/v1/governance/baal/members/{wallet}`

These routes use the Gateway's existing protected authentication. Non-admin
API keys and capability tokens require the global `governance:read` scope; a
location-specific scope cannot authorize them. The configured Directus admin
key retains the existing Gateway-wide admin bypass. These are global DAO reads,
so no farm tenant context is used. The service checks Gnosis chain ID 100 and
returns no transaction methods, raw provider payloads, vote-event arrays, or
proposal content URIs. Proposal text is bounded and should be rendered as
plain text by clients. Large share, loot, and vote quantities are returned as
decimal strings to preserve exact values. OIDC location grants do not imply
global DAO access.

The versioned public read API also exposes the enabled driver catalog at
`GET /api/v1/drivers`. It returns only driver name, version, and type, ordered
by type and name. `limit` is bounded to 1–50 and `offset` to 0–5000; the
`data` envelope includes `has_more` only while another bounded page can be
requested. Loader paths, configuration, credentials, and disabled drivers are
not returned. The route is an explicit anonymous read policy and has no write
methods.

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `attestations` and `attestation_routes` — scoped metadata reads for location EAS proofs.
- `credit_custody` and `credit_custody_routes` — aggregate carbon-credit and retirement state.
- `traceability` and `traceability_routes` — bounded location-scoped batch, custody, quality, certification, food-safety, and provenance reads.
- `ecocredits` and `ecocredit_routes` — location-scoped batch and aggregate ledger reads.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `operator_auth` — OIDC operator sessions, scope policies, and protected operator routes.
- `emergency_response` and `emergency_response_routes` — scoped emergency aggregates.
- `extension_learning_routes` — location-scoped extension-learning reads and bounded writes.
- `governance_role_routes`, `governance_tension_review`, and `governance_tension_actions` — location-scoped governance reads and human-attributed definition, assignment, tactical, and tension lifecycle operations; global Baal projections remain read-only.
- `landscape_conservation_routes` and `landscape_conservation_mutation_routes` — location-scoped landscape summaries and draft capture.
- `metric_value_routes`, `metric_value_reads`, and `metric_value_writes` — metric draft computation, scoped reads, and separate human verification.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.
- `true_cost` and `true_cost_routes` — tenant-scoped aggregate true-cost reads.

## Files

Python modules are organized by route, identity, audit, and domain service under this package.
