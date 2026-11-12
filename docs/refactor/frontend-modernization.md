# Kokonut Intelligence front-end modernization

## Purpose and status

This plan organizes the browser experience as one **Kokonut Intelligence
Control Plane**: a public ecosystem overview at `/` and three lazy-loaded
authenticated route modules—**General Operations**, **Field Operations**, and
**Governance**. The goal is a coherent, usable front end for the Kernel without
dropping any workflow or changing the authorization and data contracts that
the backend already enforces. The Delphi participant app and encrypted offline
Field Collector remain separate clients because their consent, invitation,
device-identity, and offline-storage boundaries differ from the operator
Control Plane.

This is a supporting design plan, not candidate acceptance evidence. The
Control Plane now contains deployed slices, while many workflows remain
unmigrated or unaccepted. The candidate completion guide remains authoritative
for refactor status and gates. Keep existing applications available until each
replacement workflow passes its corresponding acceptance checks.

The TypeScript workspace, shared shell, public landing page, and three route
modules are implemented under
[`apps/frontend`](../../apps/frontend/README.md). As of 11 November 2026, the
candidate is deployed at `hub.kokonut.network` through Cloudflare Worker Static
Assets; Gateway and retained compatibility routes continue to the Coolify
origin. This is candidate deployment evidence, not production readiness or
complete workflow parity. The canonical
[candidate completion guide](current-state-and-implementation.md) owns current
acceptance status.

General Operations has submitted-report review at `/ops/reports`, metric reads
at `/ops/metrics`, coordination summaries at `/ops/planning`, location/farm
setup at `/ops/administration`, and private report-export requests at
`/ops/exports`. The report and metric reads use exact location scopes; metric
drafts remain visibly unverified. Export creation and download are bounded,
location-scoped operations and do not generate, verify, or publish reports.
The location form can add a farm beneath an existing active, verified tenant
location without modifying its parent.

Field Operations at `/field/records` lists non-Collector Gateway farm
activities and supports draft creation, detail, and grant-controlled lifecycle
actions. Draft entry offers bounded farm, plot, crop-cycle, and farm-task
choices. Wasabi confirmed that the signed-in existing-location picker and these
relation controls load on 11 November 2026. Field Collector submissions remain
separate from this form.

Governance includes the read-only Delphi facilitator recommendation queue at
`/governance/recommendations`, with exact location review scopes, bounded
pagination, and approval blockers shown without decision or publication
controls. Participant invite handling remains on its separate compatibility
path.

G4 still needs negative live ID-token nonce validation, a denial check against
a second authorized location, and Field Collector offline/media/consent/sync
acceptance. G5 populated farm/report references and provider acceptance, G6
recovery and soak, and G7 sign-off remain open.

The shared `@kokonut/operator-client` foundation now enforces same-origin
operator API paths, no-store requests, the existing operator CSRF cookie/header
contract for mutations, and stale-read cancellation primitives. Its shared
operator-session hook validates session/scope data and cancels on unmount. The
report, metric, and coordination read slices use it for no-store requests,
validate location-bound identities and response contracts, and cancel stale
requests when selection changes. The export workspace adds idempotent,
location-scoped request and download operations; the Field Operations workflow
adds draft creation and separately granted lifecycle actions. Those writes use
existing Gateway contracts and do not grant authority through the UI. The
Delphi and Field Collector auth protocols remain separate. Browser and
populated-data acceptance is still required for the remaining capabilities.

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

Build and deploy one Control Plane entry point. Its shared Router, operator
session, navigation shell, API client, and design system contain a public root
page and three capability-oriented modules at `/ops/*`, `/field/*`, and
`/governance/*`. Lazy loading keeps inactive module code and styles out of the
initial download while preserving one web application and workspace switching.
The paths are a front-end routing choice; existing Gateway API paths remain
stable. The candidate uses `hub.kokonut.network`, with
`auth.kokonut.network` reserved for ZITADEL. The deployed Cloudflare Worker
serves `/`, the three module roots and descendants, and `/assets/*`. Other
same-origin paths continue to the proxied Coolify/VPS Gateway origin, including
`/operator/*`, `/api/mobile/*`, and `/participation/*`. Dynamic requests, invite
flows, and personal data must be `no-store`; cache only static assets. Do not
put API secrets, database credentials, or authorization decisions in the
browser or Worker. The exact route patterns are maintained in
[`wrangler.jsonc`](../../apps/frontend/apps/control-plane/wrangler.jsonc); the
current deployment version and acceptance limits are recorded in the candidate
completion guide.

The workspace pins Wrangler 4.148.0 for its deployment toolchain. Keep
`workers_dev` disabled in the configured candidate and retain exact-root plus
descendant route pairs so paths such as `/ops-other` continue to the VPS instead
of matching the app Worker. The `preview` environment intentionally enables a
`workers.dev` visual preview and has no `hub` routes or Gateway-origin setup.

| Control Plane module | Audience and feature groups | Current console panels to migrate |
|---|---|---|
| **General Operations** (`/ops/*`) | Operators coordinating reports, organizational programs, planning, analysis, and administration. | Submitted report review; metric computation and review; private report exports; AI summary review, draft generation, and authorized task requests; operating-pilot demand/capacity/resources/competency/coaching/learning plans/work claims and their independent queues; sequential evidence; solution lifecycle, funding, experiment, scale, replication, learning, adoption, and retirement workflows; coordination overview; extension learning and peer groups; cooperatives and shared assets; trend analysis; spatial autocorrelation, cross-validation, variograms, sensor design, kriging and realization summaries; business model canvases; business architecture; budgets; management work; competitive landscape; strategy plans; backcasting plans; stakeholder identity review. |
| **Field Operations** (`/field/*`) | Field staff and authorized supervisors working with locations, devices, and farm records. This is the operator and supervisor module; the encrypted offline Field Collector remains a separate client at `/api/mobile/app`. | Device enrollment and inventory; Field Collector collection review/disposition; farm activity intake, lifecycle, draft, and audit detail; other farm activity records; produce traceability; harvest yield; farm energy; waste/pollution; landscape/pollinator records; irrigation status; crop simulations; nutrient records. Preserve each panel's exact location grants and content allowlists. |
| **Governance** (`/governance/*`) | Facilitators, reviewers, and operators using governance and deliberation workflows. The Delphi participant experience remains a separate client at `/participation/delphi`. | Governance tension review and actions; governance role registry, circles, nominations, assignment review, and tactical sessions/actions; Delphi study creation/lifecycle/items; versioned participant notices and their review; participant invites; facilitator recommendations; recommendation review; minority-report review. Preserve independent review, consent, and publication boundaries. |

Enrollment, inventory, and collection review are supervisor workflows inside
the Control Plane's Field Operations module; the Field Collector is a separate
offline mobile client. They can share API and domain modules, but each screen
must keep its own audience, capability visibility, and Gateway authorization.
Delphi facilitation belongs to the Control Plane's Governance module. Delphi
participants continue to use `/participation/delphi` with no operator shell or
operator session requirement.

### Legacy panel-ID preservation manifest

These are the existing operator-console top-level panel IDs. They identify the
source behaviors to map into the new routes; the new React components do not
need to retain these DOM IDs. Each ID must have one explicit destination before
the legacy console is retired.

| Control Plane module | Existing panel IDs |
|---|---|
| General Operations | `review`, `metric-value-review`, `report-exports`, `ai-summary-review`, `ai-summary-draft-create`, `ai-summary-task-request`, `operating-pilot`, `sequential-evidence`, `solution-lifecycle`, `coordination-summary`, `extension-learning`, `cooperative-management`, `trend-analysis`, `geostatistics-autocorrelation`, `business-planning-canvases`, `business-architecture-summary`, `planning-budget-summary`, `management-work-summary`, `competitive-landscape-summary`, `strategy-plan-summary`, `threatcasting-backcasts`, `stakeholder-identity-review` |
| Field Operations | `mobile-enrollment`, `mobile-operations`, `mobile-review`, `farm-activity`, `farm-activity-record-operations`, `traceability`, `yield-monitoring`, `energy-monitoring`, `waste-management`, `landscape-pollinator`, `irrigation-status`, `crop-simulations`, `nutrient-operations` |
| Governance | `delphi-recommendation-review`, `delphi-minority-review`, `delphi-study-draft-create`, `delphi-study-lifecycle`, `delphi-study-item-create`, `delphi-consent-notice-draft`, `delphi-consent-notice-review`, `delphi-participant-invites`, `delphi-recommendation-draft-create`, `governance-tension-review`, `governance-role-registry`, `governance-role-assignment-review`, `governance-tactical-queue` |

## Technical shape

- Use React, TypeScript, and Vite for one Control Plane application with a
  shared Router, operator session, shell, API modules, and small design system.
  Keep General Operations, Field Operations, and Governance in clear feature
  modules with their own route trees, CSS, and ownership. Lazy-load modules so
  the initial operator download contains only the active vertical. Keep the
  separate Field Collector bundle and offline startup lean; do not load the
  Control Plane on field devices.
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
- Use one Cloudflare Worker Static Assets deployment for the compiled Control
  Plane, with exact route patterns for `/ops`, `/field`, `/governance`, and the
  shared `/assets/*` bundle path on `hub.kokonut.network`. Requests outside
  those prefixes do not match the Worker and are served by the existing
  proxied VPS origin.
  Do not cache API/auth routes, collection payloads, participant submissions,
  report contents, or signed media responses. The existing local-only
  `prototypes/cloudflare-edge-preview` remains a synthetic prototype and is not
  part of the candidate app routing.

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

The shared app, representative workflows, and candidate Cloudflare route are
implemented. The remaining sequence is for parity and retirement; the
[candidate completion guide](current-state-and-implementation.md) records
which acceptance items have passed.

1. Maintain the source feature inventory and acceptance manifest derived from
   the existing panel IDs, route policies, API operations, and app behavior.
   Do not remove or silently combine an operation without recording its
   replacement and acceptance evidence.
2. Continue the TypeScript workspace, shared application shell, route guards
   for navigation, shared API client, Kokonut design tokens, responsive layout,
   and error/loading/empty states. The current Control Plane is partial and
   does not change Gateway authorization.
3. Migrate a complete vertical slice per module. Preserve the existing
   endpoint, payload, CSRF, location, consent, and human-review semantics.
   Existing location/farm setup and relational farm-activity draft entry are
   implemented; other farm and legacy workflows remain to be reconciled.
4. Preserve the Delphi participant and Field Collector clients as their own
   specialized experiences. Their consent recovery, invite secrecy, offline
   encryption, queue durability, media reconciliation, and service-worker
   upgrade behavior still require candidate acceptance.
5. The candidate has already been deployed to `hub.kokonut.network`; this is
   not production sign-off. Complete authenticated API routing, restrictive
   cache, accessibility, mobile layout, offline/reconnect behavior, and
   rollback acceptance while keeping the existing Gateway compatibility paths
   intact. Do not infer acceptance from the custom-domain deployment.
6. Retire an old UI route only after every feature ID assigned to it has
   explicit parity evidence and its owners accept the new workflow. The backend
   refactor can continue independently; UI modernization does not waive G1–G7
   candidate acceptance.

## Completion criteria

- Every existing panel/operation has a destination and a passing equivalent
  contract; no old workflow disappears due only to navigation redesign.
- Each Control Plane module has direct-linkable routes, responsive layouts,
  keyboard/screen reader labels, loading/empty/error/retry states, and clear
  lifecycle and reviewer separation. The Delphi participant and Field
  Collector clients retain their separate entry points and acceptance checks.
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
