# Kernel operations console boundary

**Status:** Architecture contract prepared; no operator identity provider or
browser console has been selected or implemented.

## Current repository boundary

There is no first-party operations web application in the repository. The
existing `prototypes/cloudflare-edge-preview/` is explicitly synthetic-only
and has no KI API or authentication connection. `services/mobile/field-collector.html`
is the field collection client, not an operator console. The local
[`kernel overview CLI`](kernel-operator-cli.md) is read-only and has no browser
identity.

The Gateway's [`auth.py`](../../services/gateway/auth.py) accepts capability
tokens and API keys on protected routes. A configured Directus admin token is
treated as full access, and non-admin keys require configured scopes. There is
no human session or federated identity implementation in that request path.
`app.py` permits explicit CORS origins, but it does not establish a browser
session or CSRF boundary. Gateway audit records currently identify API callers
by token holder/key name and rate-limit callers by a credential digest or IP;
that is not a stable human operator identity.

Therefore, the console must never put `DIRECTUS_ADMIN_TOKEN`, another API key,
or a capability token in browser JavaScript, local storage, or a static
configuration file. The synthetic Cloudflare preview must remain disconnected
from real KI services unless it is deliberately redesigned and reviewed.

## Identity and authorization contract

Add a provider port before adding protected browser operations:

```python
@dataclass(frozen=True)
class OperatorPrincipal:
    issuer: str
    subject: str                 # stable identity-provider subject
    display_name: str | None
    tenant_ids: frozenset[str]
    permissions: frozenset[tuple[str, str]]  # resource, action

class OperatorIdentityProvider(Protocol):
    def authenticate(self, request) -> OperatorPrincipal | None: ...
    def revoke_session(self, request) -> None: ...
```

The identity adapter is replaceable. The recommended default is a standard
OIDC provider configured by issuer/client settings; Directus login can be an
optional adapter for deployments that already operate Directus. The Kernel
must not require Directus for operator identity. Local username/password
accounts would add a separate credential lifecycle and are not part of this
slice.

Map the verified `(issuer, subject)` to explicit tenant/location assignments
and `resource:action` permissions on the server. Do not trust role, tenant, or
location values supplied by the page. A request with a location identifier
must be authorized against the principal's assignment for that location, and
database/RLS scope must be derived from the verified principal. Wildcard
operator permissions are not a default.

For browser requests, prefer serving the console from the Gateway's own origin
or an explicitly trusted same-site origin. The server should keep provider
tokens out of JavaScript and use a short-lived, `HttpOnly`, `Secure`,
`SameSite` session cookie plus CSRF protection for unsafe methods. Logout and
provider revocation must invalidate the session according to the selected
adapter. If deployment uses a separate origin, require a specific CORS origin
and credential policy; wildcard origins are forbidden.

Extend audit events to retain the stable issuer/subject (or a privacy-reviewed
stable internal operator ID), action, resource, affected record, authorized
tenant/location, request ID, outcome, and denial reason. Never record raw
cookies, bearer tokens, API keys, or complete submitted evidence payloads.

## First console slice

After identity configuration is selected, build a small first-party app in
`apps/operator-console/` (or the repository's chosen frontend directory) and
serve it same-origin where practical. Use the JavaScript SDK's typed HTTP client
only after it has a browser-safe session transport; never inject a backend key.
The first slice should be read-only and show the authenticated principal and
only that principal's scoped review queue. Do not expose arbitrary SQL, broad
Directus collection CRUD, service-health probes, or administration controls.

Add governed actions later as explicit resource/action routes. Verification,
rejection, publication, credit retirement, and agent execution must retain the
existing independent human-review and confirmation boundaries. The UI cannot
grant itself permission or skip the domain service's lifecycle checks.

## Likely implementation touchpoints

- `services/gateway/operator_auth.py` (new provider port, session handling, and
  principal-to-scope resolution)
- `services/gateway/auth.py` and `services/gateway/app.py` (session-aware
  authorization and CSRF enforcement, while retaining API-key/capability
  adapters for non-browser clients)
- `services/gateway/router.py` (explicit operator routes and policy entries)
- `services/security/audit.py` and the access-audit schema (stable human actor
  fields, additive migration only if the current audit model cannot carry them)
- `sdk/javascript/src/client.ts` (browser cookie transport only after the
  Gateway contract exists)
- `apps/operator-console/` (new, minimal UI; no service credential)
- `docker-compose.kernel-candidate.yml`, the Caddy overlay, and console docs
  (same-origin deployment, exact origin policy, secure headers, rollback)

## Acceptance and rollback

Before protected console use, verify login/callback/logout, expired and revoked
sessions, CSRF rejection, unauthorized tenant/location access, least-privilege
scope checks, audit actor attribution, and that no credential appears in the
browser bundle or storage. Confirm that unauthenticated users see no private
queue data and that console access does not bypass the Gateway or database
policy.

Roll back by removing the console route/assets and disabling the selected
identity adapter. Keep the local read-only CLI, Directus admin surface, and
existing public reads available under their own policies. Do not revoke or
rotate existing service keys as part of console rollback.

## Product choice required

Before implementing login, select one identity source:

1. **OIDC provider (recommended):** provider-neutral and keeps Directus optional;
   requires the issuer/client settings for each deployment.
2. **Directus account/session adapter:** fastest for the current stack, but
   browser operator access depends on the optional Directus service.
3. **Self-managed local accounts:** adds password storage, recovery, rotation,
   MFA, and account lifecycle responsibilities to the Kernel.

Until that choice is made, only the provider-neutral contract and read-only
console architecture are in scope; no credential or session implementation is
safe to guess.
