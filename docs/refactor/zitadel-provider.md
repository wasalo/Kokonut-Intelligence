# ZITADEL provider plan

**Decision:** 15 October 2026 — use self-hosted ZITADEL as Kokonut's OIDC
identity provider.

## Boundary

ZITADEL will prove the operator's identity. Kokonut's Gateway continues to own
opaque browser sessions, CSRF checks, operator identity mapping, organization
membership, location grants, tenant context, and resource/action authorization.
ZITADEL organization or role claims do not grant Kokonut access. The optional
`docker-compose.kernel-oidc.yml` configures the Gateway OIDC client. The
separate `docker-compose.kernel-zitadel.yml` overlay starts the optional
self-hosted provider. Use `python3 scripts/kernel-profile.py minimal
--zitadel` to select the complete candidate, HTTPS proxy, OIDC client, and
ZITADEL deployment set.

```text
Browser ── HTTPS ── Caddy ──┬── hub.kokonut.network ── Kernel Gateway
                            └── <identity-hostname> ── ZITADEL Login/API
Kernel Gateway ── OIDC discovery/token verification ── ZITADEL issuer
```

The owner has selected `hub.kokonut.network` for the application but has not
selected a separate identity hostname. Keep that value configurable until the
DNS name is provided. The OIDC callback remains on the app origin at
`/operator/auth/callback`.

## Optional deployment shape

The code-first ZITADEL profile is now implemented as an opt-in Compose overlay.
It runs the API and Login V2 images behind the existing Caddy service, with a
dedicated PostgreSQL service and a non-superuser `zitadel` database owner on an
internal-only data network. The database, provider API, and Login UI publish no
host ports. Caddy routes `/ui/v2/login/*` to Login V2 and other identity-host
traffic to ZITADEL over h2c with the upstream `TE` header removed. The profile
sets Login V2 base/login/logout URLs from the configured identity hostname and
the same HTTPS port used by Caddy. Compose/planner checks validate the merged service topology,
Caddy validates the proxy configuration, and the database bootstrap passed in
an isolated PostgreSQL 17 container; these checks do not start ZITADEL or
establish live OIDC acceptance.

- Keep the IdP outside the `minimal` and `edge` profiles. The Kernel API can use
  a reachable self-hosted issuer, while an edge device stays focused on
  PostgreSQL/PostGIS, the Gateway, and local collection. ZITADEL's current
  Compose guide lists 2 GB RAM as a prerequisite; its production guide gives
  about 512 MB for the ZITADEL process and notes CPU spikes during password
  hashing. A physical Raspberry Pi was not available, so colocated performance
  is not accepted from source review alone.
- Run ZITADEL with its own database and credentials. A separate Postgres
  database/role on a managed or shared server may be considered after privilege
  and backup boundaries are verified; never reuse the Kokonut operational
  superuser credential. ZITADEL supports PostgreSQL 14–18.
- Reuse the existing Caddy ingress where topology permits. Caddy must forward
  HTTP/2 to ZITADEL over h2c when it terminates TLS. Route `/ui/v2/login/*` to
  the Login UI and all other IdP paths to the API. Strip the upstream `TE`
  header as ZITADEL documents to avoid hanging error responses.
- Do not add Redis for ZITADEL by default; its cache is optional and disabled
  by default. Add it only after measured need and a separate profile review.
- The profile currently selects versioned API/Login image tags at ZITADEL
  v4.20.0 and PostgreSQL 17.10. A registry manifest lookup could not run from
  this host because registry DNS was unavailable, so OCI digest pinning and
  ARM64 manifest verification remain release gates. Do not use floating
  `latest` tags. The Login UI cookie secret must be configured before startup
  and kept stable across replicas.
- Keep ZITADEL migration/setup and backup/restore separate from Kokonut schema
  migrations. ZITADEL's master key is exactly 32 characters and is durable
  encryption state: losing or replacing it can make encrypted IdP data
  inaccessible.

## Configuration and acceptance

Before live acceptance, record the identity hostname and provision the
following through SOPS: ZITADEL database credentials, 32-character master
key, first-admin credential, Login V2 session-cookie secret (at least 32
characters), and Kokonut OIDC client secret/state secret. Keep values out of
this document and chat.

For the database DSN's URL-safe password, generate a 32-byte hexadecimal
value (for example, with `openssl rand -hex 32`) and store it only in the
encrypted secret file. Compose config uses synthetic values in tests; the
profile does not generate or provision production/local secrets automatically.

Then configure the non-secret issuer, client ID, HTTPS callback, and logout
redirect; create synthetic operator accounts; and verify discovery, PKCE,
login, callback, Gateway session creation, CSRF logout, grant provisioning,
scope denial, audit attribution, and Field Collector browser behavior. A
successful ZITADEL login alone does not establish tenant or authorization
parity.

## Source references

- [ZITADEL Docker Compose deployment](https://zitadel.com/docs/self-hosting/deploy/compose)
- [ZITADEL Caddy reverse proxy](https://zitadel.com/docs/self-hosting/manage/reverseproxy/caddy)
- [ZITADEL requirements](https://zitadel.com/docs/self-hosting/manage/requirements)
- [ZITADEL database configuration](https://zitadel.com/docs/self-hosting/manage/database)
- [ZITADEL release history](https://github.com/zitadel/zitadel/releases)
