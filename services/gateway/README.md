# gateway

`services.gateway` — Unified API Gateway — single entry point for all API traffic.

## Run

```bash
# Compose (preferred; Caddy proxies /mobile and /api/mobile/*)
docker compose up -d gateway

# Host process
python3 -m services.gateway.cli --serve --port 8099
python3 -m services.gateway.cli --help
```

Field Collector: `https://localhost/mobile/` (or `https://<lan-ip>/mobile/` on the LAN).

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
event notes, and actor IDs. The console renders these reads as text and has no
triage, assignment, resolution, verification, publication, or approval action.
Underlying legacy tables do not yet have domain-table RLS, so these protected
routes do not establish universal tenant isolation.

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

Open tactical work is available at `GET
/operator/api/governance/{location_id}/tactical-items` with the separate exact
`governance_tactical:read` grant. It returns bounded open/in-progress items,
requested action, priority, due date, session summary, and owner role key, but
omits party identities, session notes, agenda text, and disposition detail.
The role registry and tactical queue use signed tenant context before
location-filtered SQL, read-only transactions, and keyset pagination capped at
100; role detail uses the same tenant context and read-only transaction with
each nested list capped at 100. All three projections are rendered as text in
the console. They expose no mutation or approval action; the
underlying governance tables do not yet have domain-table RLS.

Role nominations use
`POST /operator/api/governance/{location_id}/roles/{role_id}/assignments`
with the separate location-scoped `governance_roles:create` grant. The request
requires a caller-generated `request_id`, active nominee party UUID,
assignment type, and an optional mandate (required for delegates). A signed
operator context and active operator/person binding attribute the request.
The bounded database function creates only a `proposed` assignment and writes
an immutable idempotency/attribution record; it cannot activate, approve, end,
or reject an assignment. Direct assignment-table writes are revoked from the
runtime and Directus roles. A distinct human approval route is not implemented
yet, so proposals remain pending for a future reviewed approval flow.
These ACLs protect only those non-superuser roles. The local candidate app
currently connects as the administrative `kokonut` login, so its database
session can bypass these grants; migration 438 has not been applied to that
candidate. Do not treat the route or this migration as a database isolation
boundary until the candidate is switched to its least-privilege runtime role.

Governance tension intake is available at `POST
/operator/api/governance/{location_id}/tensions` with a caller-generated UUID
`request_id`, title, description, supported tension type, severity, and urgency.
The same operator may submit its own draft through `POST
/operator/api/governance/{location_id}/tensions/{tension_id}/submit`. Both routes
require exact `governance_tension:create` or `governance_tension:submit`
location grants, OIDC/CSRF, and signed tenant context. Submission only moves a
report from draft to submitted; the Gateway does not expose triage, verification,
publication, tension disposition, or governance approval actions.

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

## Modules

- `app` — Gateway application — FastAPI app with auth, routing, rate limiting, and audit.
- `attestations` and `attestation_routes` — scoped metadata reads for location EAS proofs.
- `credit_custody` and `credit_custody_routes` — aggregate carbon-credit and retirement state.
- `ecocredits` and `ecocredit_routes` — location-scoped batch and aggregate ledger reads.
- `audit` — Gateway audit — request logging.
- `auth` — Gateway auth — unified authentication (API key, capability token, session).
- `cli` — CLI for the API gateway.
- `operator_auth` — OIDC operator sessions, scope policies, and protected operator routes.
- `emergency_response` and `emergency_response_routes` — scoped emergency aggregates.
- `governance` — bounded, read-only Baal Gateway projections for global DAO state.
- `governance` — bounded, read-only Baal Gateway projections for global DAO state.
- `rate_limiter` — Gateway rate limiter — per-caller token bucket rate limiting.
- `router` — Gateway router — route definitions and backend proxying.
- `true_cost` and `true_cost_routes` — tenant-scoped aggregate true-cost reads.

## Files

Python modules are organized by route, identity, audit, and domain service under this package.
