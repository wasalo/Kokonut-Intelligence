# Kernel operations console boundary

**Status:** OIDC identity/session foundation and a same-origin operator shell
are implemented in source. The shell includes location-scoped Field Collector
enrollment, submitted-report reads, a private Field Collector review queue and
append-only review notes, plus source-level farm-activity intake, private draft
promotion, canonical activity reads, grant-filtered submit/verify/reject/
rework/publish/exception controls, and a native draft editor. Focused migration,
route/query, immutable-schema, grant-lock, append-only rollback, and console
checks now pass; all 376 schema migrations and a synthetic edit/rollback
acceptance passed on disposable PostGIS 16 ([evidence](builds/2026-10-13-recovery/farm-activity-draft-edit-acceptance.json)).
The queue/detail, edit route, and console are deployed to the local candidate
after migration 385 and an app-only rebuild from `f854d47`. Candidate health
returns 200 and unauthenticated protected reads and draft edits return 401.
OIDC remains disabled because no provider settings have been configured.
Real-provider login, browser-runtime acceptance, and live payload acceptance
remain open. This remains a partial implementation, not an accepted console.

## Current repository boundary

The existing `prototypes/cloudflare-edge-preview/` remains synthetic-only and
has no KI API or authentication connection. `services/mobile/field-collector.html`
is the field collection client, not an operator console. The new
`apps/operator-console/` shell displays a verified OIDC principal, issues
single-use Field Collector enrollment codes for explicitly granted locations,
reads submitted report snapshots, reviews synced Field Collector rows, and
provides a governed farm-activity workflow for explicitly granted locations. The local
[`kernel overview CLI`](kernel-operator-cli.md) is read-only and has no browser
identity.

The Gateway's [`auth.py`](../../services/gateway/auth.py) continues to accept
capability tokens and API keys for existing protected routes. A separate
optional OIDC path now uses an opaque PostgreSQL-backed browser session. Its
audit caller is the stable internal operator UUID; rate limiting hashes the
opaque cookie. The default Kernel image still excludes Authlib and session
middleware dependencies.

Therefore, the console must never put `DIRECTUS_ADMIN_TOKEN`, another API key,
or a capability token in browser JavaScript, local storage, or a static
configuration file. The synthetic Cloudflare preview must remain disconnected
from real KI services unless it is deliberately redesigned and reviewed.

## Identity and authorization contract

The OIDC adapter implements a provider port before protected browser
operations are added:

```python
@dataclass(frozen=True)
class OperatorPrincipal:
    operator_id: str
    issuer: str
    subject: str                 # stable identity-provider subject
    display_name: str | None
    email: str | None

@dataclass(frozen=True)
class OperatorSession:
    session_id: str
    csrf_token_hash: str
    operator: OperatorPrincipal

class OperatorIdentityProvider(Protocol):
    def authenticate_request(self, request) -> OperatorSession | None: ...
    def csrf_valid(self, request, session) -> bool: ...
    def has_scope(self, operator_id, resource, action, location_id) -> bool: ...
    def list_scopes(self, operator_id) -> list[dict]: ...
    def revoke_session(self, session_id) -> None: ...
```

The implemented adapter is OIDC. The Kernel does not require Directus for
operator identity. Local username/password accounts would add a separate
credential lifecycle and are not part of this slice.

Map the verified `(issuer, subject)` to explicit location assignments and
`resource:action` permissions on the server. Migration 380 adds the identity,
scope-grant, and session tables. The provisioning CLI enables a specific
issuer/subject and grants one resource/action for one existing location. No
role, tenant, location, or permission claim from the browser is trusted.
Wildcard operator permissions are not accepted by the CLI or schema.

The browser session response includes only the signed-in operator's active
grant tuples so the page can offer assigned locations. The report review grant
is `report_snapshot_review:read`. Field Collector list/detail grants are
`mobile_collection_review:read` and `mobile_collection_review:read_detail`.
The Gateway checks each grant against the requested canonical location UUID;
the mobile detail grant is intentionally separate from list access. Each
read-only SQL query rechecks the active grant and binds record ID and location.
The mobile list includes only synced rows that are review-flagged or fail the
eligibility view, and it omits participant linkage, collector/device identity,
and payload. Detail returns a bounded payload only under `read_detail`; it omits
media bytes and object references. Append-only reviewer notes require both
`mobile_collection_review:review` and `mobile_collection_review:read_detail`,
CSRF, and an authenticated OIDC session. Migration 382 binds each event to the
operator, collection, and location, validates bounded reason/evidence fields,
and rejects edits/deletes. Notes do not alter consent eligibility or governed
lifecycle state.

The disposition impact inventory is a separate queue action. It requires
`mobile_collection_retention:inventory` plus `mobile_collection_review:read`,
but not the payload detail grant. It returns counts/statuses for the collection,
private media, promoted farm activities, and review/workflow events; it omits
payload values, participant identifiers, object keys, and hashes. The source
rechecks both grants and location in SQL. It is read-only and covers direct
database lineage only; it cannot decide or execute retention, erasure, or
de-identification.

For browser requests, prefer serving the console from the Gateway's own origin
or an explicitly trusted same-site origin. The server should keep provider
tokens out of JavaScript and use a short-lived, `HttpOnly`, `Secure`,
`SameSite` session cookie plus CSRF protection for unsafe methods. Logout and
local identity disablement revoke the local session. Provider-initiated logout
and upstream session-revocation notifications are not implemented. If
deployment uses a separate origin, require a specific CORS origin and
credential policy; wildcard origins are forbidden.

The existing access-audit path records route/action, caller, outcome, IP/user
agent, and bounded request metadata. The queue uses the stable internal
operator UUID as caller and records the canonical location in the audit event.
It does not add request IDs or affected-record fields; a future decision route
may need those. Never record raw cookies, bearer tokens, API keys, or submitted
evidence.

## OIDC implementation and deployment

The opt-in identity endpoints are `GET /operator/auth/login`,
`GET /operator/auth/callback`, `GET /operator/auth/session`, and
`POST /operator/auth/logout`. The page at `/operator/` displays the verified
principal and provides Field Collector enrollment to authorized operators.
Enrollment uses `/operator/api/mobile/locations/{location_id}/enrollments`,
with matching routes to revoke an unused enrollment or active device. These
routes require `mobile_device:enroll` or `mobile_device:revoke` for the path's
location. The form accepts a collector attribution ID separate from participant
identity, limits code lifetime to 15 minutes through 24 hours, and shows the
plaintext code once in a `no-store` response. The page signs out with a
double-submit CSRF token, uses same-origin requests, does not put credentials in
local storage, and renders claims with `textContent`.

The callback validates OIDC through Authlib discovery, authorization-code
flow, state/nonce handling, and S256 PKCE. Provider access/ID tokens are not
stored in browser state or PostgreSQL. Session and CSRF values are random,
short-lived cookies; PostgreSQL stores only their SHA-256 digests. Session
cookies are HttpOnly, Secure, SameSite=Lax, and scoped to `/operator`. Unsafe
operator-auth requests require the CSRF header, readable CSRF cookie, and
matching stored hash. Local logout revokes the database session.

The default `kernel` image remains dependency-light. Build the `oidc` target
with `requirements/oidc.txt` by adding
`docker-compose.kernel-oidc.yml` to the candidate and TLS proxy overlays.
Configure issuer, client ID, client secret, callback URL, and a random
32-byte-or-longer state secret via the existing SOPS-loaded environment. The
callback URL must be HTTPS and end in `/operator/auth/callback`. The Compose
overlay refuses to start without all required values. `.env.example` lists the
setting names and a localhost HTTPS callback example; client and state secrets
belong in `.env.sops`, not plaintext `.env`. A Compose contract check verifies
the overlay remains opt-in and rejects missing provider settings. No real
provider or credentials have been configured by that source check.
The profile planner exposes `--oidc` and requires `--proxy` alongside it;
`python3 scripts/kernel-profile.py minimal --proxy --oidc` prints the complete
candidate/proxy/OIDC Compose command without loading secrets or starting it.

```sh
source scripts/load-secrets.sh
docker compose -p kokonut-kernel-candidate \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-proxy.yml \
  -f docker-compose.kernel-oidc.yml up -d --build
```

This command is for a deployment with an already configured provider; it has
not been run in this batch.

Before allowing an operator to sign in, apply migration 380 and provision the
OIDC subject locally:

```sh
python3 -m services.cli operator identity provision --issuer ISSUER --subject SUBJECT --display-name NAME
python3 -m services.cli operator grant --operator-id UUID --resource RESOURCE --action read --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator list
```

The OIDC login does not auto-provision identities or grants. Disabled identities
cannot create sessions, and disabling an identity revokes its current sessions.
The report snapshot was selected as the first review source because its schema
and workflow specify `draft → submitted → verified → published`. The report
queue returns at most 100 location-specific submitted summaries; its detail
read returns `report_data` only for the selected submitted record under the
same grant, with a 512 KiB payload ceiling. The Field Collector queue returns
at most 100 synced ineligible/review-required summaries. Its separate detail
read requires `read_detail`, returns payloads up to 512 KiB, and exposes only a
photo count. The farm-activity intake list returns at most 100 eligible native
1.2.0 summaries without free text. Private intake detail requires
`farm_activity:read_detail` and `mobile_collection_review:read_detail`; draft
promotion additionally requires `farm_activity:create_draft` and repeats all
three grants in the transaction. The canonical lifecycle list is also capped
at 100 and omits descriptions and notes. Detail requires the same two detail
grants and returns bounded activity fields plus append-only decision history.
Detail includes the newest 100 events at most and indicates when older events
are omitted.

Native `farm_activity_v1` 1.2.0 drafts can be corrected with
`PATCH /operator/api/farm-activities/{activity_id}/draft?location_id=...`.
The request requires `farm_activity:edit_draft`, `farm_activity:read_detail`,
and `mobile_collection_review:read_detail` at that location, plus the normal
OIDC session and CSRF token. Its body is `{ "content": { ... }, "reason":
"..." }`; `content` accepts only `activity_type`, `activity_date`,
`description`, `labor_hours`, and `notes`. The service merges the patch with the
current canonical fields and validates the result against the immutable form
revision referenced by the original collection. Optional fields set to `null`
are cleared; unknown fields and values outside the form schema are rejected.
The database keeps `source_raw` and the captured collection unchanged, and
appends a same-state `draft_edited` event with the operator, reason, changed
field names, and SHA-256 of the resulting canonical content. The event contains
no copied description or notes. Migration 385 is applied to the candidate;
focused service/route/console checks and isolated PostGIS acceptance passed,
and the candidate rejects unauthenticated draft-edit requests with 401. No
candidate workflow rows have been created.
Actions are shown only when the operator session contains the matching
location grant, and the Gateway and database recheck authorization and legal
state on every write. Verification, rejection, and publication retain the
independent-actor rules. Neither queue exposes arbitrary SQL or other location
scopes. Network-level snapshots with a null `location_id` are excluded until a
separate network-scope model is designed.

Grant a console capability explicitly after applying migration 380:

```sh
python3 -m services.cli operator grant --operator-id UUID \
  --resource report_snapshot_review --action read \
  --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID \
  --resource mobile_device --action enroll \
  --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID \
  --resource mobile_collection_review --action read \
  --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID \
  --resource mobile_collection_review --action read_detail \
  --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID \
  --resource mobile_collection_retention --action inventory \
  --location-id LOCATION_UUID --granted-by OPERATOR
```

After migration 382 has been applied, reviewer-note access also needs an
explicit location grant:

```sh
python3 -m services.cli operator grant --operator-id UUID --resource mobile_collection_review --action review --location-id LOCATION_UUID --granted-by OPERATOR
```

Farm activity access is separate from Field Collector form review. `read` lists
eligible intake and canonical summaries; `read_detail` is also required before
private intake or canonical content can be opened. Draft promotion requires
`create_draft` in addition to both detail grants. Give each lifecycle decision
only to the operators expected to perform it:

```sh
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action read --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action read_detail --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action create_draft --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action edit_draft --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action submit --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action verify --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action reject --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action rework --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action publish --location-id LOCATION_UUID --granted-by OPERATOR
python3 -m services.cli operator grant --operator-id UUID --resource farm_activity --action close_exception --location-id LOCATION_UUID --granted-by OPERATOR
```

## Current console slices

The report and Field Collector queues, append-only reviewer-note action, and
enrollment action are implemented in the Gateway and
`apps/operator-console/`. The farm-activity workflow now has source-level
intake and canonical queues, separately granted private detail, explicit
review acknowledgement before draft promotion, and grant-filtered lifecycle
actions. It uses same-origin cookie requests and CSRF for writes. The mobile
list omits identity and payload, detail is bounded, and no media download route
is exposed. Reviewer notes use `review` plus `read_detail` and cannot mutate
eligibility or lifecycle state. No backend key is sent to the browser. The
enrollment code response is not cached and the code is displayed once. The new
farm-activity read/edit UI passed focused source and disposable database
checks, but it is not yet deployed or accepted with a real identity provider.
Do not expose
arbitrary SQL, broad Directus collection CRUD, service-health probes, or
administration controls.

Other governed actions must use explicit resource/action routes. Verification,
rejection, publication, credit retirement, and agent execution retain the
existing independent human-review and confirmation boundaries. The UI cannot
grant itself permission or skip the domain service's lifecycle checks.

## Likely implementation touchpoints

- `services/gateway/operator_auth.py` (OIDC adapter, session and CSRF handling,
  principal-to-scope port, location-scoped enrollment/revocation routes)
- `services/gateway/operator_cli.py` and `services/cli.py` (local identity,
  grant, and revocation administration)
- `services/gateway/app.py` (auth routes, opaque sessions, CSRF, stable audit
  caller identity, exact route policy, and location-scope enforcement; existing
  API-key/capability routes stay separate)
- `services/gateway/operator_review.py` and
  `services/gateway/operator_mobile_review.py` (bounded report and Field
  Collector queries, append-only reviewer events, and content-free disposition
  impact inventory)
- `schemas/postgres/382_mobile_collection_review_events.sql` (append-only
  operator-attributed review notes with collection eligibility guards)
- `schemas/postgres/380_operator_identity_sessions.sql` (additive identity,
  location-grant, and session storage)
- `Dockerfile.kernel`, `requirements/oidc.txt`, and
  `docker-compose.kernel-oidc.yml` (optional dependency/image/deployment path)
- `apps/operator-console/index.html` (same-origin principal shell, report and
  Field Collector list/detail reads, reviewer-note form, read-only disposition
  inventory, and one-time
  enrollment-code form)
- `sdk/javascript/src/client.ts` (possible follow-on typed console methods;
  current same-origin console uses browser `fetch` and the session cookie)
- `docker-compose.kernel-candidate.yml`, the OIDC and Caddy overlays, and
  console docs (same-origin deployment, exact origin policy, secure headers,
  rollback)

## Acceptance and rollback

Before protected console use, verify discovery/signature/state/PKCE handling,
login/callback/logout, expired and revoked sessions, upstream provider logout
behavior, CSRF rejection, unauthorized location access, least-privilege scope
checks, audit actor attribution, and that no credential appears in browser
storage. Verify the report queue excludes drafts, verified/published rows,
null-scope network reports, cross-location IDs, and unauthenticated requests.
Verify the mobile queue excludes pending transport rows and only returns synced
records within the active location grant; verify list/detail grant separation,
the payload size bound, no participant/collector identity, and no media bytes or
links. Real-provider and live database checks remain open. Confirm the console
does not bypass Gateway or database policy.

Roll back by removing the console route/assets and disabling the selected
identity adapter. Keep the local read-only CLI, Directus admin surface, and
existing public reads available under their own policies. Do not revoke or
rotate existing service keys as part of console rollback.

## Remaining deployment input

The identity source is selected: OIDC. No issuer/client configuration has been
added to SOPS yet, so authentication remains disabled and no live login has
been attempted. Configure a provider and callback URL through the encrypted
secret workflow before using the opt-in profile. OIDC readiness, session/CSRF
acceptance, live grant-denial/audit behavior, report and mobile queue/detail
runtime acceptance, and the full browser workflow remain open.
