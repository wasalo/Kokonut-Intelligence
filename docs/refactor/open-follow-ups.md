# Open Follow Ups

Updated: 15 October 2026. This file collects decisions, access, fixtures, and
physical resources that the refactor cannot safely infer. Local implementation,
offline tests, disposable-database acceptance, and documentation continue while
these items are open.

Do not put passwords, API tokens, client secrets, private keys, or vault
passphrases in this document. For credentialed items, provide the provider and
non-secret configuration, then provision credentials through the encrypted
secret workflow.

## Decisions and source data

| ID | Needed from the repository owner or capability owner | Why it blocks closure |
| --- | --- | --- |
| OFU-01 | **Known locations mapped 15 October 2026:** Kokonut Genesis, Kokonut Seeds, Kokonut Adelphi, Kokonut Terra Viva, and Kokonut V1 are operated by Kokonut Network. Adelphi and Genesis are confirmed exclusive to Kokonut Network. No additional shared organizations were named for Seeds, Terra Viva, or V1; keep sharing ungranted unless explicitly confirmed. Genesis, Seeds, Adelphi, and V1 have owner-held data planned for later ingestion; Terra Viva is still in design. Map only these named locations; other/unlocated records stay unassigned pending owner mapping. | This resolves the five named operational-tenant mappings for future import and tenant work. It does not establish legal land title or affiliations for every operator account. |
| OFU-02 | For each legacy OIDC operator: organization membership and allowed location/resource/action scopes; identify disabled or departed operators. | Existing NULL-tenant grants cannot be converted safely without the human-to-organization mapping. |
| OFU-03 | **Jurisdictions provided 15 October 2026:** United States and Dominican Republic. Exact purpose-specific retention periods still need an accountable product/legal owner for notifications, attempts, operator audit, mobile collections, media, canonical derivatives, exports, and backups. Define legal-hold placement/release, archive access, erasure approval, and treatment of withdrawn or retired-form records. | Neither jurisdiction supplies one universal period for every record category. Event cleanup and generic data-governance enforcement now fail closed by default; keep both switches off until a category schedule is approved and target-record legal-hold eligibility is implemented. |
| OFU-04 | **Scope decision received 15 October 2026:** port all repository-verified Kokonut reports and dashboards first; the owner will decide what to keep, remove, or improve after reviewing them. Audience/scope/measures and populated reference outputs can be reconciled after the planned farm-data ingestion. | This clears report selection as a prerequisite to code-first porting. Archived Metabase's 39 generic e-commerce sample-H2 cards are not treated as Kokonut product reports; preserve them as unverified archive items for later owner review. |
| OFU-05 | Select the production external alert destination and accountable on-call owner (SMTP, webhook, or other supported adapter), plus routing/severity expectations. | Local outbox and adapter code do not prove delivery, alert response, or operational ownership. |
| OFU-06 | **Production direction received 15 October 2026:** target hostname `hub.kokonut.network`; 24-hour recovery target; replicas/failover are deferred until production deployment; cutover is approved once readiness gates pass. Still needed before public deployment: ingress/proxy-hop and trusted-proxy policy, TLS/certificate plan, and production topology/RPO details. | The cutover approval is conditional on the documented readiness gates; it does not close those gates or authorize skipping verification. Local loopback profiles do not establish the public topology. |

## Provider and environment access

| ID | Needed | Safe handling / current state |
| --- | --- | --- |
| OFU-07 | **Provider selected 15 October 2026: self-hosted ZITADEL.** The opt-in Compose/Caddy profile and dedicated database role are implemented and source-checked. Still needed for live acceptance: the identity hostname (the app hostname `hub.kokonut.network` is known, but no identity hostname was selected), non-secret issuer/client ID, callback URL, test identities, and provisioning owner. Provision generated master key, Login V2 cookie secret, database credentials, initial-admin secret, and OIDC client/state secrets through SOPS. | Kokonut's Gateway session, scope, and tenant-authorization layer remains authoritative; ZITADEL supplies identity proof through OIDC. Keep ZITADEL opt-in and separately credentialed. No live provider has been configured. OCI digest and ARM64 image-manifest acceptance also remain open. See [deployment plan](zitadel-provider.md). |
| OFU-08 | **R2 account configuration received 15 October 2026:** account `7219a605e3c2144a30987e20fd4cf397`, S3 endpoint `https://7219a605e3c2144a30987e20fd4cf397.r2.cloudflarestorage.com`, buckets `kokonut-production` and `kokonut-backups`. Still needed: dedicated least-privilege credentials, test prefix/non-production acceptance, and explicit lifecycle/retention rules. | Do not put credentials in this document or chat; provision through SOPS or at production deployment. Live R2 inventory, backup, restore, and deletion acceptance remain open. |
| OFU-09 | **Tenant-model direction received 15 October 2026:** Directus parity should follow organization/location grants. The repository pins Directus 12.1.1; code still needs to bind its authenticated user to Kokonut `operator_identity`, then exercise a disposable schema with representative roles, fields, rows, and hooks under that runtime identity. | Map Directus identity to the same org/location grants as the Gateway; do not use Directus as the tenant authority. Do not point parity checks at production. The archived snapshot has a documented schema mismatch. |
| OFU-10 | Local browser unlock of the Field Collector vault and the candidate browser session when available. | An isolated Chrome context has now verified `navigator.onLine=false`, cached-shell reopen, encrypted local capture, and reconnect retry against mocked API responses ([evidence](builds/2026-10-14-recovery/field-collector-browser-offline-client.json)). Unlock the existing vault only in the browser; do not send the passphrase. Live candidate API re-enrollment and retired-form consent flows remain open. |
| OFU-11 | Trust the candidate's local development HTTPS CA in the browser/OS, or provide an existing approved local certificate. | The earlier browser refused the untrusted certificate. We will not bypass the browser warning. HTTP loopback checks are passing. |

## Physical and timed acceptance

| ID | Needed | Why it blocks closure |
| --- | --- | --- |
| OFU-12 | No hardware input is needed for the agreed code-only assessment. The ARM64 minimal app/PostGIS build, 386-schema bootstrap, health, logical restore, and restart checks passed under Buildx/QEMU with constrained containers ([evidence](builds/2026-10-14-recovery/arm64-qemu-runtime-acceptance.json)). | No Raspberry Pi was available. Physical performance, thermal, storage, power-loss, network, and device restart behavior remain unverified and must not be claimed. See [code-first execution plan](code-first-execution-plan.md). |
| OFU-13 | **Recovery target received 15 October 2026:** run the 24-hour recovery window. Schedule/resource budget and whether the local candidate may be unavailable still need coordination before the timed run. | Short restart/retry checks are not evidence for a 24-hour recovery/scale gate. Replica/failover testing is deferred to production as requested. |
| OFU-14 | The owner plans to ingest source data for Genesis, Seeds, Adelphi, and V1 after the build; Terra Viva data will follow its design phase. No sanitized populated reference exports are available yet. | Port report/provider capabilities from repository evidence now. Close semantic parity against populated outputs after the owner-provided ingestion; do not fabricate expected farm results from synthetic data. |

## Additional product and provider decisions

| ID | Needed | Why it blocks closure |
| --- | --- | --- |
| OFU-15 | **Tenant-model decision received 15 October 2026:** use organization/location grants for Directus-compatible access. The pinned version is 12.1.1; supported consumers and runtime identity must be verified with an isolated fixture. | The archived Field Worker rule uses `$CURRENT_USER.location_id`, but the archived `directus_users` table has no `location_id`; a disposable runtime probe failed closed for synthetic own-location and other-location reads. The next implementation step binds Directus identity to the Gateway's operator model. See [Directus parity inventory](directus-parity-inventory.md). |
| OFU-16 | The owner wants all repository-defined provider/job capabilities ported before choosing what to retain. Active production schedule state and accountable operators are still unknown; obtain a read-only export or approved access before enabling schedules in production. | Code-first parity can proceed from the repository and implementation plan. The candidate reports no scheduled jobs and has no Prefect service, but host/external scheduler state was not queried; source inventory alone cannot identify active production jobs. See [schedule ownership inventory](schedule-ownership-inventory.md). |

## Answers

When ready, reply with the ID and answer, or edit this file directly. Names and
IDs are enough for ownership mapping; do not provide secret values here. Any item
that remains undecided stays fail-closed and is not treated as accepted.

## Additional candidate operation

| ID | Needed from owner | Why it blocks closure |
| --- | --- | --- |
| OFU-17 | **Seed scope selected 15 October 2026: reference catalogs only; hold pilot rows.** Implemented `scripts/seed.sh --catalog-only` with the exact five-file allowlist in [reference seed scope](reference-seed-scope.md). The existing `scripts/seed.sh --reference-only` flag remains legacy behavior: it skips schema/ClickHouse/Directus setup but still applies the full curated seed list, so it must not be used for the selected scope. | This is a local candidate data write, not a schema migration or production import. Scope selection is not rollout approval. No candidate seed SQL has run. Any future approved write needs a fresh age-encrypted checkpoint of the current candidate, restore-rehearsed in isolation; skip applied `140_mobile_forms.sql`, exclude `064-068_impact_network.sql`, and leave the other pending files untouched. Restore the checkpoint if a later seed fails after earlier transactions commit. |
| OFU-18 | **Completed 14 October 2026:** approved candidate rollout of migrations 392–397. | A fresh age-encrypted checkpoint was restore-rehearsed in an isolated `template0` database, all six ordered migrations applied there and on the candidate, the second replay had zero pending migrations, and the candidate app alone was recreated. The candidate later advanced through migrations 398–400 under the owner's migration authorization; current state is 391 applied schemas through 400, one curated seed ledger row, zero pending/failed schema migrations, and no RLS-enabled application tables. The temporary restore project was removed; the encrypted checkpoint remains. See [rollout evidence](builds/2026-10-14-recovery/candidate-migration-392-397-fresh-checkpoint-rollout.json) and [migration-400 evidence](builds/2026-10-14-recovery/candidate-migration-400-restore-owner-repair.json). Applying the five selected catalog seeds is still open under OFU-17. Reviewed hash/scope rows for existing tenant-bound API keys remain a separate prerequisite for their protected use. |
| OFU-19 | Approve provisioning distinct generated `KOKONUT_RUNTIME_PASSWORD` and `KOKONUT_OPERATOR_AUTH_PASSWORD` values in encrypted `.env.sops` for the local candidate, or provide an approved secret-provisioning workflow. | The local candidate still runs as the database superuser because these variables are absent. The role bootstrap and least-privilege code are ready, but provisioning credentials would change the encrypted runtime configuration; the actual candidate role and authenticated HTTP path should be verified only after that human gate. Never send the generated or existing secrets in chat. |

The owner’s 14 October instruction authorizes focused test execution and
required refactor migrations through 400 for this code progress. Candidate seed SQL has not run. On 15 October the owner confirmed the five named locations' Kokonut Network operating tenant, org/location access direction, all-reports-first porting scope, R2 account/buckets/endpoint, `hub.kokonut.network`, 24-hour recovery target, and conditional cutover approval. The owner selected self-hosted ZITADEL, supplied USA and Dominican Republic as retention jurisdictions, and chose reference-catalog-only seed scope. Live provider configuration, exact retention periods, and separately approved candidate seed application remain open.
Migration 392–397 rollout was completed under OFU-18; migrations 398–400 were
applied under the owner’s 14 October permission for required refactor
migrations. The curated seed write remains gated under OFU-17 and runtime
credential provisioning remains gated under OFU-19.
