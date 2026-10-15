# ZITADEL provider plan

**Decision:** 15 October 2026 — use self-hosted ZITADEL as Kokonut's OIDC
identity provider.

## Boundary

ZITADEL will prove the operator's identity. Kokonut's Gateway continues to own
opaque browser sessions, CSRF checks, operator identity mapping, organization
membership, location grants, tenant context, and resource/action authorization.
ZITADEL organization or role claims do not grant Kokonut access. The optional
`docker-compose.kernel-oidc.yml` currently configures the Gateway client only;
it does not start an identity provider.

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
- Pin the API and Login images to a reviewed release and OCI digests. The
  ZITADEL v4.19.4 release was published 1 October 2026; it includes a Login V2
  session-cookie security fix in v4.19.2, so the Login UI cookie secret must be
  configured before startup and kept stable across replicas.
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
- [ZITADEL v4.19.4 release](https://github.com/zitadel/zitadel/releases/tag/v4.19.4)
