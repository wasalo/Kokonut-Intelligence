# Kokonut Intelligence front-end modernization

## Purpose and status

This plan organizes the existing browser interfaces into three independently
built front-end applications: **General Operations**, **Field Operations**, and
**Governance**. The goal is a coherent, usable front end for the Kernel without
dropping any workflow or changing the authorization and data contracts that the
backend already enforces.

This is a supporting design plan, not evidence that the applications have been
migrated or accepted. The candidate completion guide remains authoritative for
refactor status and acceptance gates. Keep the existing applications available
until the replacement for their workflows passes the corresponding acceptance
checks.

The initial TypeScript workspace and three route shells now exist under
[`apps/frontend`](../../apps/frontend/README.md). They provide navigation and
handoffs to the existing interfaces only; feature parity, identity acceptance,
Cloudflare routing, and R2 acceptance remain open.

## Existing surfaces and boundaries

| Current surface | Current purpose | Preserve during migration |
|---|---|---|
| [`apps/operator-console/index.html`](../../apps/operator-console/index.html) | Authenticated operator workbench. It is a standalone HTML file of about 1.85 MB, with inline styles and application code and same-origin `/operator/auth/*` and `/operator/api/*` requests. | Every location-scoped read/write, capability-gated workflow, CSRF behavior, status and error handling, pagination, stale-response protection, and human approval boundary listed below. |
| [`apps/delphi-participant`](../../apps/delphi-participant) | Separate participant-facing consultation app. Invite material is taken from the URL fragment into session storage and removed from the address bar. It uses same-origin, no-store API requests. | Notice preview and consent, private study participation, paginated questions, contribution handling, optional minority reports, and consent withdrawal. Invite credentials must not enter application logs, caches, analytics, or referrers. |
| [`services/mobile/field-collector.html`](../../services/mobile/field-collector.html), [`field-collector-vault.js`](../../services/mobile/field-collector-vault.js), and [`field-collector-service-worker.js`](../../services/mobile/field-collector-service-worker.js) | Mobile-first offline field app, currently served by the Python service. Its shell and cryptographic helper are cached by an explicit service-worker allowlist. | Encrypted offline queue and lock, form validation/versioning, location/device binding, photos, retry-safe sync, consent-aware capture, update/reconnect behavior, and exact shell/service-worker cache rules. |

The Gateway remains the authority for identity, tenant/location scope, consent,
CSRF, lifecycle decisions, and data access. Hiding a screen or navigation item
is a usability feature; it never authorizes an API operation.

## Application boundaries and route plan

Build and deploy three app entry points. Use path prefixes on one HTTPS
application origin for the first candidate so existing same-origin session,
CSRF, and API behavior can be retained. Suggested UI paths are `/ops/*`,
`/field/*`, and `/governance/*`. The paths are a front-end routing choice; the
existing Gateway API paths remain stable during migration. A Cloudflare edge
router may serve the static bundle for each prefix and forward only explicit
Gateway/auth paths to the VPS. Dynamic requests, invite flows, and personal data
must be `no-store`; cache only versioned static assets. Do not put API secrets,
database credentials, or authorization decisions in the browser or Worker.

| App | Audience and feature groups | Current console panels to migrate |
|---|---|---|
| **General Operations** (`/ops/*`) | Operators coordinating reports, organizational programs, planning, analysis, and administration. | Submitted report review; metric computation and review; private report exports; AI summary review, draft generation, and authorized task requests; operating-pilot demand/capacity/resources/competency/coaching/learning plans/work claims and their independent queues; sequential evidence; solution lifecycle, funding, experiment, scale, replication, learning, adoption, and retirement workflows; coordination overview; extension learning and peer groups; cooperatives and shared assets; trend analysis; spatial autocorrelation, cross-validation, variograms, sensor design, kriging and realization summaries; business model canvases; business architecture; budgets; management work; competitive landscape; strategy plans; backcasting plans; stakeholder identity review. |
| **Field Operations** (`/field/*`) | Field staff and authorized supervisors working with locations, devices, and farm records. The Field Collector remains an offline-first PWA within this app boundary. | Device enrollment and inventory; Field Collector collection review/disposition; farm activity intake, lifecycle, draft, and audit detail; other farm activity records; produce traceability; harvest yield; farm energy; waste/pollution; landscape/pollinator records; irrigation status; crop simulations; nutrient records. Preserve each panel's exact location grants and content allowlists. |
| **Governance** (`/governance/*`) | Facilitators, reviewers, participants, and operators using the governance and deliberation workflows. The participant experience is a distinct entry point and layout inside this app boundary. | Governance tension review and actions; governance role registry, circles, nominations, assignment review, and tactical sessions/actions; Delphi study creation/lifecycle/items; versioned participant notices and their review; participant invites; facilitator recommendations; recommendation review; minority-report review. Preserve independent review, consent, and publication boundaries. |

Enrollment, inventory, and collection review are supervisor workflows inside
Field Operations; the Field Collector is its role-specific offline mobile
experience. They can share API and domain modules, but each screen must keep
its own audience, capability visibility, and Gateway authorization. The Delphi
participant page belongs to Governance at a public participation route such as
`/governance/participate/`, but remains a separate entry experience with no
operator shell or operator session requirement.

### Legacy panel-ID preservation manifest

These are the existing operator-console top-level panel IDs. They identify the
source behaviors to map into the new routes; the new React components do not
need to retain these DOM IDs. Each ID must have one explicit destination before
the legacy console is retired.

| App | Existing panel IDs |
|---|---|
| General Operations | `review`, `metric-value-review`, `report-exports`, `ai-summary-review`, `ai-summary-draft-create`, `ai-summary-task-request`, `operating-pilot`, `sequential-evidence`, `solution-lifecycle`, `coordination-summary`, `extension-learning`, `cooperative-management`, `trend-analysis`, `geostatistics-autocorrelation`, `business-planning-canvases`, `business-architecture-summary`, `planning-budget-summary`, `management-work-summary`, `competitive-landscape-summary`, `strategy-plan-summary`, `threatcasting-backcasts`, `stakeholder-identity-review` |
| Field Operations | `mobile-enrollment`, `mobile-operations`, `mobile-review`, `farm-activity`, `farm-activity-record-operations`, `traceability`, `yield-monitoring`, `energy-monitoring`, `waste-management`, `landscape-pollinator`, `irrigation-status`, `crop-simulations`, `nutrient-operations` |
| Governance | `delphi-recommendation-review`, `delphi-minority-review`, `delphi-study-draft-create`, `delphi-study-lifecycle`, `delphi-study-item-create`, `delphi-consent-notice-draft`, `delphi-consent-notice-review`, `delphi-participant-invites`, `delphi-recommendation-draft-create`, `governance-tension-review`, `governance-role-registry`, `governance-role-assignment-review`, `governance-tactical-queue` |

## Technical shape

- Use React, TypeScript, and Vite with a shared, small design system and three
  independently buildable applications. Give each app its own entry point,
  routes, CSS, API modules, and feature ownership. Lazy-load domain sections so
  users download only the workflows they can use. Keep the Field Collector
  bundle and offline startup lean; do not load the General Operations or
  Governance bundles on field devices.
- Keep API request/response types in a shared client generated or checked
  against the Gateway's published contract. Centralize same-origin fetch,
  CSRF headers, `no-store` behavior, error translation, request cancellation,
  and location-change stale-response protection.
- Keep server authorization authoritative. Build navigation from the session's
  capability inventory for usability, but rely on Gateway route policy and
  database checks for enforcement. Do not cache signed-in page data in a
  service worker or Cloudflare cache.
- Keep app-specific identity and lifecycle behavior separate: operator OIDC
  and CSRF; participant invitation and consent; Field Collector device
  credentials, encrypted local queue, offline sync, and service-worker update
  rules.
- Keep browser-visible user data out of analytics and logs. Avoid tokens in
  query strings; preserve the Delphi hash-fragment handling and URL cleanup.
- Use Cloudflare Workers Static Assets for compiled assets. A small router may
  serve each app path and forward an allowlist of dynamic paths to the Gateway.
  Do not cache API/auth routes, collection payloads, participant submissions,
  report contents, or signed media responses. The existing local-only
  `prototypes/cloudflare-edge-preview` remains a prototype until the real app
  contract and deployment origin are configured.

## R2 storage direction

R2 is the selected object-store target, not a replacement for PostgreSQL.
Existing S3-compatible adapters already cover private Field Collector media
and report artifacts; backup transport also has an R2-compatible path. Keep
separate private buckets and credentials for media, report exports, and
checkpoints/backups. Do not make participant media, private exports, or backup
objects public.

The current Field Collector upload validates device/location and collection
policy, accepts a JPEG up to 2 MB, writes it through the Gateway to the
configured object store, and verifies stored metadata during sync. First
configure and accept this existing server-to-R2 flow with a synthetic prefix.
Only then consider a direct browser/device-to-R2 presigned `PUT` flow to reduce
VPS bandwidth and memory work. That later flow must issue short-lived,
single-object authorization after the same policy checks, bind the upload to a
random scoped key, verify size/type/checksum and registration before sync, and
retain expiry, orphan reconciliation, and deletion evidence. Never send R2
credentials to a browser. R2 remains private by default; do not use `r2.dev`
for production media.

## No-loss migration sequence

1. Freeze the source feature inventory above and derive an acceptance manifest
   from the existing panel IDs, route policies, API operations, and app tests.
   This is the preservation baseline; don't remove or silently combine an
   operation without documenting the replacement.
2. Create the TypeScript workspace, app shells, route guards for navigation,
   shared API client, design tokens, responsive layout, and error/loading/empty
   states. Do not alter Gateway behavior in this step.
3. Migrate one complete vertical slice per app. Start with high-value
   read-only workflows, then forms and lifecycle decisions. Keep the existing
   endpoint, payload, CSRF, location, consent, and human-review semantics.
4. Migrate the Delphi participant and Field Collector clients as their own
   specialized experiences; validate consent recovery, invite secrecy, offline
   encryption, queue durability, media reconciliation, and service-worker
   upgrade behavior before replacing their current entry points.
5. Deploy candidate builds to Cloudflare preview URLs with synthetic data and
   no production credentials. Verify same-origin auth/API routing, restrictive
   cache headers, accessibility, mobile layout, reconnect/offline behavior,
   and rollback before custom domains or live R2 access are enabled.
6. Retire an old UI route only after every feature ID assigned to it has
   explicit parity evidence and its owners accept the new workflow. The backend
   refactor can continue independently; UI modernization does not waive G1–G7
   candidate acceptance.

## Completion criteria

- Every existing panel/operation has a destination and a passing equivalent
  contract; no old workflow disappears due only to navigation redesign.
- Each app has direct-linkable routes, responsive layouts, keyboard/screen
  reader labels, loading/empty/error/retry states, and clear lifecycle and
  reviewer separation.
- OIDC, participant consent, tenant/location authorization, CSRF, media
  privacy, and offline queue protections are browser-accepted against the
  candidate Gateway.
- Static files can be cached globally, while all personalized/API/auth/media
  responses are explicitly excluded from shared caching.
- Cloudflare builds have preview/production separation, scoped deployment
  credentials, observable deployment revisions, and a verified rollback path.
- R2 synthetic upload/read/head/delete/reconciliation and backup restore
  acceptance pass before live provider credentials, production media, or
  production backup claims are enabled.
