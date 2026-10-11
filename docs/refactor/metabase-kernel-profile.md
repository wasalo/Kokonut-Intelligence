# Optional Kernel Metabase profile

**Status (11 October 2026):** the candidate-only overlay is running and healthy
on `127.0.0.1:3001`. The one-shot bootstrap created `kokonut_metabase` with the
bounded `kokonut_metabase_app` owner. Its real login can create metadata objects
and cannot connect to `kokonut_intelligence`. Metabase's fresh metadata has one
sample H2 source, 39 generic demo cards, and one demo dashboard; no Kokonut
PostgreSQL source or Kokonut cards are configured. The legacy stack remains
stopped. See [sanitized evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json).

## Boundaries

- `metabase` runs only with the explicit `analytics` Compose profile.
- The service shares the private candidate network with PostgreSQL. PostgreSQL
  has no host-published port; Metabase is published only at
  `127.0.0.1:${KOKONUT_METABASE_PORT:-3001}`.
- The pinned Metabase image stores its own schema in
  `kokonut_metabase`, owned by `kokonut_metabase_app`. That login cannot connect
  to `kokonut_intelligence`.
- The configured Kokonut source must use `kokonut_analytics_ro`, which can read
  only the three named views in `kokonut_reporting`. The metadata login is not
  a source login.
- Public sharing and static embedding are disabled. The JVM heap defaults to
  768 MiB for this optional service.
- `MB_ENCRYPTION_SECRET_KEY` is supplied by a distinct SOPS-managed
  `KOKONUT_METABASE_ENCRYPTION_KEY`; Metabase reported saved-credential
  encryption enabled before any source was registered. Preserve this key with
  encrypted metadata backups. See [Metabase credential encryption](https://www.metabase.com/docs/latest/databases/encrypting-details-at-rest).
- The default/minimal candidate profile does not start Metabase, create its
  metadata database, or publish port 3001.

## Provision and start

Load the encrypted environment, then run the explicit one-shot metadata-role
bootstrap:

```bash
source scripts/load-secrets.sh
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  --profile analytics-admin \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-metabase.yml \
  run --rm metabase-role-bootstrap
```

This operation is guarded for a dedicated Kernel PostgreSQL instance. It
refuses to proceed if another database still grants inherited `PUBLIC CONNECT`,
creates or verifies the separate metadata database/login, and tests a
transaction-rolled-back metadata table create. It does not register a source or
change application tables.

Start the UI only when needed:

```bash
docker compose --env-file /dev/null -p kokonut-kernel-candidate \
  --profile analytics \
  -f docker-compose.kernel-candidate.yml \
  -f docker-compose.kernel-metabase.yml \
  up -d metabase
```

Complete Metabase's local first-run administrator setup at
`http://127.0.0.1:3001`. Add a PostgreSQL source with host `database`, port
`5432`, database `kokonut_intelligence`, user `kokonut_analytics_ro`, and the
SOPS-managed source credential. Select `kokonut_reporting` as the reporting
schema. Do not use `kokonut`, the metadata login, or the archived H2 sample as
the Kokonut source.

## Promotion gate

Before treating this as a supported analyst profile:

1. Record the metadata-role bootstrap output and confirm the role cannot connect
   to the application database. **Passed**; see the evidence above.
2. Start Metabase and record a healthy status while verifying PostgreSQL remains
   private and default Compose still excludes Metabase. **Passed:** Metabase
   Docker health and host health both returned healthy/200, PostgreSQL has no
   host binding, and the default manifest lists only `database` and `app`.
3. Register the reviewed source and verify access only to the three curated
   reporting views.
4. Build first-party cards for farm summary, verified metrics, and Celo
   attestations. Compare each result to independent SQL and populated fixtures,
   including empty results, date bounds, and eligibility filters.
5. Keep the legacy E-commerce Insights board labeled as demo content; do not
   promote it as Kokonut parity.

The current candidate database is empty, so zero-row card output alone cannot
complete item 4. Use an isolated populated copy or a rollback-only synthetic
fixture and retain sanitized aggregate evidence.

## Rollback

Stop and remove only the Metabase service. Keep the candidate PostgreSQL volume
and metadata database through the rollback window. If the profile is retired,
revoke `kokonut_analytics_ro`'s explicit view grants or set the login to
`NOLOGIN`; do not drop reporting views or alter canonical application data.

Implementation: [`docker-compose.kernel-metabase.yml`](../../docker-compose.kernel-metabase.yml),
[`services.migration.metabase_role`](../../services/migration/metabase_role.py),
and [the reporting contract](metabase-reporting-contract.md).
