# Metabase source inventory

Updated: 11 October 2026.

## Result

The encrypted legacy `metabase` metadata archive was restored into a fresh
internal-only PostgreSQL recovery project. A sanitized read-only inventory found:

- One registered source, engine `h2`, marked as the sample source and not a stub.
- No configured host or database name, and no nonempty password value on that source.
- All 39 saved cards reference that H2 source and use Metabase's `query` type.
- The single dashboard has 22 card placements, all referencing H2.
- The metadata database contains one user.
- No PostgreSQL or ClickHouse source is registered in this restored metadata.

The fixture read connection details in memory only to categorize them. It did
not print connection values, source names, card names, saved-query definitions,
or SQL. It queried only source engine/flags, card query type/source references,
and aggregate card/dashboard/user counts. Exact sanitized output is retained in
[machine evidence](builds/2026-10-11-recovery/metabase-source-inventory.json).

## What this establishes

The saved dashboard is not evidence of analytics parity against Kokonut's
PostgreSQL or ClickHouse data. Its cards point to Metabase's sample H2 source;
the current archive inventory does not identify a configured application or
analytics database for those cards. Preserve the original metadata and avoid
granting the analytics read role to Metabase until the intended source and
published-view contract are chosen.

The initial inventory did not start Metabase against the populated metadata
copy, execute cards, read query SQL, or compare result values. It did not
establish whether the sample H2 dataset is available in the selected Metabase
image. The saved-content review below resolves the disposition question for the
sample dashboard, while source connectivity and Kokonut report parity remain
open.

## Populated metadata startup rehearsal

The pinned Metabase `v0.62.4` image subsequently started against a fresh
populated metadata restore using the non-superuser `kokonut_metabase_app` role.
Its health endpoint returned HTTP 200 and Docker reported the service healthy.
Post-startup aggregate counts matched the earlier inventory of the same
encrypted metadata archive: 39 cards, one dashboard, 22 dashboard placements,
and one user. All cards still referenced the sample H2 source. The
source detail field-name inventory contains only `db`; its value was not read.
No card definitions or SQL were read or executed. This verifies populated
metadata startup and aggregate preservation only, not source connectivity,
rendering, or analytics parity. See [startup evidence](builds/2026-10-11-recovery/metabase-populated-startup.json).

## Saved-content review and disposition

A second fresh internal-only restore was inspected with a structural inventory
that reports card/dashboard titles, visualization types, source-table
categories, and aggregate query-feature counts. It never emits saved query
definitions, SQL, filter values, connection values, domain rows, card
descriptions, or user records. It did not run Metabase or execute saved cards.
The restored board is titled **E-commerce Insights**. Its cards cover orders,
products, subscriptions, checkout funnels, revenue, and customer survey
examples. They reference sample H2 tables such as `ORDERS`, `PRODUCTS`,
`PEOPLE`, `FEEDBACK`, `ANALYTIC_EVENTS`, and `ACCOUNTS`; the board contains 22
placements and the metadata contains 39 saved cards spanning 19 visualization
types. All 39 cards point to the H2 sample source. These titles and source
categories identify generic e-commerce demo content, not Kokonut farm,
finance, ecological, governance, or dMRV reporting.

**Disposition:** preserve this metadata only as an explicitly labeled Metabase
demo/compatibility fixture. Do not migrate the sample board as Kokonut's
analytics dashboard and do not map its sample cards onto Kokonut tables by
name. For Kokonut reporting, define first-party measures and reviewed
published-view contracts, then build Kokonut-specific cards and compare their
outputs with agreed reference fixtures. Metabase may remain an optional
analytics product, but the sample dashboard is not a capability or parity
artifact. The evidence is
[metabase-content-inventory.json](builds/2026-10-11-recovery/metabase-content-inventory.json).

The structural inventory recognizes physical-table and saved-question
references; a small number of references remain unresolved by this bounded
parser. This does not change the source classification: the metadata database
links all cards to H2, while the fixture deliberately did not evaluate the
underlying H2 data or queries.

## Recovery and rollback

The inventory ran in project
`kokonut-kernel-metabase-inventory-20261011` on the recorded PostgreSQL/PostGIS
image. The network was internal, no ports were published, and only the isolated
database plus the one-off inventory container ran. Both encrypted archives
were streamed directly into the database; no decrypted dump was written to
disk. The project containers and network were removed after inspection while
the named PostgreSQL volume was retained. The candidate remained healthy and
legacy services remained stopped.

For another attempt, use a new Compose project and volume. Keep the retained
volume as evidence; do not attach it to candidate, standard, portability, or
legacy deployments. Rollback is stopping/removing only the temporary project;
the encrypted archives and retained volume remain unchanged.

The content review used the separate project
`kokonut-kernel-metabase-content-20261011`, restoring only the encrypted
Metabase metadata archive. Its network was internal, no ports were published,
and the metadata archive was streamed through `age` into `pg_restore` without
creating a plaintext dump. The unused `kokonut_intelligence` database was left
empty in the retained volume. An exploratory attempt to restore the separate
application archive encountered a PostGIS duplicate-extension catalog error;
that database was reset empty and is not part of the content evidence. No
candidate or legacy database was touched. The retained isolated volume is
`kokonut-kernel-metabase-content-20261011_consumer-role-postgres-data`.

## Fresh candidate profile startup — 11 October 2026

The optional candidate Metabase profile reached healthy status on the
loopback-only host port. A sanitized, read-only inventory of its metadata
database found one source, Metabase's built-in H2 sample source (`is_sample`,
not a stub), with host and database unset and no password field. Its 39 saved
cards and 22 dashboard placements all reference that H2 source; the database
contains one dashboard and one user record. No Kokonut PostgreSQL source or
Kokonut-specific card exists. Connection values and saved SQL were not read or
printed. Treat this fresh sample content as demo material, matching the
classification of the legacy archive; it is not analytics parity evidence.

The inventory reused
[`kernel-metabase-source-inventory.py`](../../scripts/fixtures/kernel-metabase-source-inventory.py)
against `kokonut_metabase` over the internal candidate network. The parser now
handles empty/non-JSON `details` values without exposing them. The candidate
Metabase password and `MB_ENCRYPTION_SECRET_KEY` are encrypted in `.env.sops`;
startup logs confirmed saved-credential encryption before any Kokonut source
was registered. See [sanitized profile evidence](builds/2026-10-11-recovery/candidate-metabase-profile.json).
