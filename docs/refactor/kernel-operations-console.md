# Kernel operations console boundary

**Status:** OIDC identity/session foundation and a same-origin principal shell
are implemented in source. OIDC remains disabled because no provider settings
have been configured. The scoped review queue and its governed read endpoint
are still pending; this shell is not yet an operational review console.

## Current repository boundary

The existing `prototypes/cloudflare-edge-preview/` remains synthetic-only and
has no KI API or authentication connection. `services/mobile/field-collector.html`
is the field collection client, not an operator console. The new
`apps/operator-console/` shell displays a verified OIDC principal but does not
yet expose a review queue. The local
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

For browser requests, prefer serving the console from the Gateway's own origin
or an explicitly trusted same-site origin. The server should keep provider
tokens out of JavaScript and use a short-lived, `HttpOnly`, `Secure`,
`SameSite` session cookie plus CSRF protection for unsafe methods. Logout and
local identity disablement revoke the local session. Provider-initiated logout
and upstream session-revocation notifications are not implemented. If
deployment uses a separate origin, require a specific CORS origin and
credential policy; wildcard origins are forbidden.

The existing access-audit path records route/action, caller, outcome, IP/user
agent, and bounded request metadata. This slice uses the stable internal
operator UUID as caller and does not add request IDs or affected-record fields.
Add those fields with the review-queue endpoint if its audit contract needs
them. Never record raw cookies, bearer tokens, API keys, or submitted evidence.

## OIDC implementation and deployment

The opt-in endpoints are `GET /operator/auth/login`,
`GET /operator/auth/callback`, `GET /operator/auth/session`, and
`POST /operator/auth/logout`. The small page at `/operator/` displays the
verified principal and signs out with a double-submit CSRF token. The page
uses same-origin requests, does not put credentials in local storage, and
renders claims with `textContent`.

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
overlay refuses to start without all required values.

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
The first browser page currently proves only sign-in, principal display, and
sign-out. The scoped review queue is deliberately not populated until its
canonical submitted-record source, filters, and read contract are selected.

## First console slice

Extend `apps/operator-console/` with a read-only queue after its canonical
submitted-record source and policy are chosen. Use the JavaScript SDK's typed
HTTP client only after it has a browser-safe session transport; never inject a
backend key. Queue reads must use the principal's explicit location grant. Do
not expose arbitrary SQL, broad Directus collection CRUD, service-health probes,
or administration controls.

Add governed actions later as explicit resource/action routes. Verification,
rejection, publication, credit retirement, and agent execution must retain the
existing independent human-review and confirmation boundaries. The UI cannot
grant itself permission or skip the domain service's lifecycle checks.

## Likely implementation touchpoints

- `services/gateway/operator_auth.py` (OIDC adapter, session and CSRF handling,
  principal-to-scope port)
- `services/gateway/operator_cli.py` and `services/cli.py` (local identity,
  grant, and revocation administration)
- `services/gateway/app.py` (auth routes, opaque sessions, CSRF, and stable
  audit caller identity; existing API-key/capability routes stay separate)
- `schemas/postgres/380_operator_identity_sessions.sql` (additive identity,
  location-grant, and session storage)
- `Dockerfile.kernel`, `requirements/oidc.txt`, and
  `docker-compose.kernel-oidc.yml` (optional dependency/image/deployment path)
- `apps/operator-console/index.html` (same-origin principal shell; no review
  queue yet)
- `sdk/javascript/src/client.ts` (browser cookie transport when the queue
  endpoint is implemented)
- `docker-compose.kernel-candidate.yml`, the OIDC and Caddy overlays, and
  console docs (same-origin deployment, exact origin policy, secure headers,
  rollback)

## Acceptance and rollback

Before protected console use, verify discovery/signature/state/PKCE handling,
login/callback/logout, expired and revoked sessions, upstream provider logout
behavior, CSRF rejection,
unauthorized location access, least-privilege scope checks, audit actor
attribution, and that no credential appears in browser storage. Add review
queue authorization and unauthenticated-data checks when the read endpoint is
implemented. Confirm the console does not bypass Gateway or database policy.

Roll back by removing the console route/assets and disabling the selected
identity adapter. Keep the local read-only CLI, Directus admin surface, and
existing public reads available under their own policies. Do not revoke or
rotate existing service keys as part of console rollback.

## Remaining deployment input

The identity source is selected: OIDC. No issuer/client configuration has been
added to SOPS yet, so authentication remains disabled and no live login has
been attempted. Configure a provider and callback URL through the encrypted
secret workflow before using the opt-in profile. OIDC readiness, session/CSRF
acceptance, the scoped review queue, and the full browser workflow remain open.
