# CAP-006 landscape and pollinator Kernel read contract

Updated: 25 October 2026

## Routes and authorization

- `GET /operator/api/landscape/{location_id}/summary` requires the exact
  location grant `landscape_conservation:read`.
- `GET /operator/api/pollinators/{location_id}/summary` requires the exact
  location grant `pollinator_health:read`.
- `POST /operator/api/pollinators/{location_id}/hives` requires the exact
  location grant `pollinator_health:create`.
- `POST /operator/api/pollinators/{location_id}/hives/inspections` requires
  that same exact location create grant.
- `GET /operator/api/pollinators/{location_id}/habitats` requires the exact
  location grant `pollinator_health:read_detail`. It returns bounded operational
  habitat details, not the aggregate summary.
- `PATCH /operator/api/pollinators/{location_id}/habitats/{habitat_id}` requires
  the exact location grant `pollinator_health:edit`; it updates only reported
  status, condition, and maintenance date.
- `GET /operator/api/pollinators/{location_id}/hives` requires the exact
  location grant `pollinator_health:read_detail`; its paginated projection omits
  private notes and metadata.
- `PATCH /operator/api/pollinators/{location_id}/hives/{hive_record_id}`
  requires the exact location grant `pollinator_health:edit`; it updates only
  operational status and last-maintenance date.
- These endpoints are private, same-origin operator routes. Responses use
  `Cache-Control: no-store` and `Vary: Cookie`; invalid identifiers fail before
  opening a database connection.
- Each read uses a single repeatable-read, read-only PostgreSQL transaction,
  installs signed operator/location/resource/action context on that connection,
  and repeats the location predicate in every source query. The handler rolls
  back and closes the connection on success and failure.

## Source and lifecycle semantics

The reads follow the source definitions in
`schemas/postgres/154_landscape_conservation.sql` and
`schemas/postgres/155_pollinator_health.sql`. Migration 602 additively aligns
the existing pollinator analytics service with migration 155: it restores the
structured source/temperature and habitat fields used by its established
commands, adds pesticide application measurements and distinct numeric hive
strength scores, and introduces location-bound inspection history. Observations
may link to a hive only within the same location. No existing records are
rewritten by this migration.

Migration 603 applies the same location boundary to landscape habitat
references. Composite foreign keys bind corridor source/target and buffer-check
habitats to their parent location. They remain `NOT VALID` to preserve
historical rows, while rejecting cross-location writes going forward. The
legacy habitat-summary, corridor-status, and buffer-compliance views now use
location-qualified joins/counts so historical mismatches do not expose a
foreign habitat name or inflate its local inventory. Those historical links
remain for an operator-reviewed reconciliation before the constraints can be
validated.

Landscape inventories group habitat zones, wildlife corridors, and hedgerows
by their fixed type/condition/status dimensions and retain the source units
(hectares and metres). These records are descriptive and their lifecycle state
is returned. Buffer checks are limited to `verified`; biodiversity summaries
include only `verified` and `published` assessments and report means across the
selected records, not a latest-value or compliance determination.

The landscape response also preserves the legacy dashboard's active-habitat
count/area and critical/high-value counts, plus active-corridor count,
good/excellent count, length, and a mean width weighted by non-null widths.
Buffer calculations intentionally use verified checks only; their percentage
is not the legacy all-status rate and must not be presented as legal or
regulatory compliance. Empty groups return zero counts and zero-valued
summaries. The historical `connectivity_ratio_pct` is exposed as
`legacy_connectivity_ratio_pct`, calculated as healthy active corridors divided
by active habitat zones. It is a compatibility formula, not a graph/network
measure or ecological outcome, and is labeled accordingly in the console.

Pollinator observations and pesticide-impact records include only `verified`
or `reviewed` rows. Pollinator habitats are descriptive inventories grouped by
type, condition, and source status. Active-hive summaries retain kg for honey
yield and counts for varroa observations; they are not a health certification.
The reference species catalog is network-wide and is not joined into a
location response.

Migration 623 adds hive inspections through a separate security-definer
function. It resolves one active hive identifier within the granted location,
appends the source `recorded` inspection and updates the hive snapshot fields
in the same transaction. A private digest receipt supports exact retries. The
route does not verify the inspection; runtime and Directus cannot directly
change inspection rows or those snapshot fields, and the legacy inspection CLI
fails before opening a database connection.

Migration 624 adds a separate paginated habitat detail route and a constrained
status/condition/maintenance update. Detail reads use a repeatable-read,
read-only transaction, the exact `read_detail` grant, and a location predicate;
they return habitat identity, name/type/area, reported status/condition, last
maintenance, and update time while omitting ecological observations and freeform
details. Updates require an expected `updated_at` and bounded reason, reject
stale writes, and use an isolated no-login function owner to update the row and
append an immutable actor-attributed before/after audit event atomically.
Runtime and Directus cannot directly mutate habitat rows or read the private
event ledger. The operation records self-reported operational state; it does not
verify ecological condition or outcomes.

Migration 625 provides a paginated managed-hive detail route and a separate
status/maintenance operation. Detail uses repeatable-read/read-only semantics,
the exact `read_detail` grant, and a repeated location predicate; it returns
identifier, type, operational status, recorded strength/queen/frame fields,
inspection date, last-maintenance date, and update timestamp. It omits private
notes and metadata. Updates require the latest `updated_at` and a bounded reason,
reject stale writes, and append an immutable operator-attributed before/after
event atomically with the status/maintenance change. Runtime and Directus cannot
directly alter hive rows or read the private ledger. This is operational
self-reporting and does not verify colony health. Inspection capture remains a
separate recorded observation under migration 623.

Migration 622 adds managed-hive registration through a security-definer
function under signed exact-location create authorization. It stores the legacy
`active` inventory state, the creator, and a private digest-only retry receipt;
it does not make health or strength verified. Runtime and Directus cannot insert
hive rows or read receipts. Migration 623 owns inspection history and its
snapshot updates; migration 625 owns operational status and last-maintenance
updates through a separate audited function.

The scoped pollinator response also preserves three legacy calculations using
aggregates only. Observation trends use the last 30 days and compare equal
15-day windows; the existing increasing/decreasing thresholds remain above
10% and below -10%. The 90-day pesticide advisory counts only verified or
reviewed rows: any reported mortality or at least three high/very-high toxicity
reports is `critical`, one or more high/very-high reports is `elevated`, and
otherwise it is `low`. Recorded rows are intentionally excluded from this
governed read even though the legacy CLI advisory includes them. The active-hive
summary reports the count and mean non-null numeric `colony_strength_score`
(0–10), separately from the categorical colony-strength inventory. These are
advisory indicators; they do not determine ecological condition, pesticide
safety, or regulatory compliance.

The legacy analytics service now uses the canonical observation, habitat,
`pesticide_impact_log`, and `hive_record` tables. Its writes begin in the
`recorded` review state; the summary includes only verified/reviewed
observations and pesticide records. Hive inspections append a distinct record
and update the selected location-bound hive snapshot in one transaction. The
historic numeric colony-strength input is retained as a 0–10 score, separate
from the schema's categorical strength. Pesticide risk is an advisory
toxicity/mortality heuristic, not a safety or compliance determination. Detail
lists are bounded to 500 rows and report when more applications match.

These legacy analytics queries and CLI writes remain a repository-level
compatibility surface. They do not establish signed operator context or tenant
RLS. The Gateway is the scoped operator path; direct CLI/database use must stay
behind a trusted operator boundary until its runtime identity is narrowed.

Aggregate landscape and pollinator summary responses omit names, geometry, plot
IDs, species names, products, active ingredients, hive identifiers, narratives,
notes, assessor identities, weather JSON, and arbitrary metadata. The separate
habitat detail route exposes only the bounded fields documented above and omits
species, nesting features, and freeform notes. Fixed-schema groupings are small
and have an 8-second statement timeout. No client-supplied query or group
dimensions are accepted.

## Console behavior

The hidden-by-default console panel has independent subsections and selectors
for each grant. Aggregate sections require their exact read scope; habitat detail
and edit controls separately require `read_detail` and `edit`. Reads are
same-origin and no-store, validate response location and fixed categories,
discard stale responses, and render values through `textContent`. Habitat edits
use CSRF protection, stable request IDs, a required reason, and the detail
response timestamp as the optimistic concurrency token; successful edits refresh
the detail view without implying ecological verification.
The managed-hive panel follows the same hidden-by-default, paginated,
grant-separated pattern and labels status/maintenance as operational
self-reporting.

## Verification and rollback

### Historical location-reference preflight

Run `LANDSCAPE_REFERENCE_PREFLIGHT_DSN=... python3
scripts/landscape-reference-preflight.py` only after explicitly selecting the
intended database target. The script makes no connection when the variable is
unset and never prints the DSN. Its first statement makes the transaction
repeatable-read and read-only; lock waits are capped at two seconds and the
query at 30 seconds. The result contains global counts for the fixed
`corridor_source`, `corridor_target`, and `buffer_habitat` categories only; it
does not expose row, location, habitat, or descriptive values. A nonzero count
is a reconciliation queue size, not authorization to rewrite a row. Run it
against a reviewed source copy first; only after every mismatch is reconciled
should an operator separately validate migration 603's three composite
constraints.

The focused migration, landscape-domain, Gateway, route-policy, console,
JavaScript syntax, and pollinator service selection passes 71 tests; Ruff and
Python compilation pass. The aggregate preflight adds four unit tests. A
disposable PostgreSQL 16 check applies migrations 154/603 and passes eight
grouped checks for historical link privacy, new-write scope, sanitized
aggregate mismatch counts, and read-only write denial; a separate check applies
155/602 and passes six service/schema assertions.
Evidence is in
`builds/2026-10-23-recovery/cap-006-pollinator-health-disposable.json` and the
`builds/2026-10-23-recovery/cap-006-landscape-reference-location-disposable.json`;
the earlier Gateway/console evidence remains in
`builds/2026-10-23-recovery/cap-006-landscape-pollinator-kernel-read.json`.
No candidate/legacy database, provider, or Raspberry Pi was used. If deployed,
rollback should revert the application only after stopping use of the new
fields; the additive migration and inspection history should be retained.

The 23 October source-parity slice adds the three aggregate calculations above
to the scoped pollinator Gateway and renders them with fixed category/number
checks in the console. Its focused Gateway, console, and domain selection passes
40 tests; Ruff, Python compilation, and the console's Node syntax check pass.
Synthetic cases pin the trend threshold, both pesticide critical-risk branches,
and active-hive score aggregation. No database was accessed. Evidence:
`builds/2026-10-23-recovery/cap-006-pollinator-calculation-parity.json`.

The landscape calculation slice restores those source-defined active habitat
and corridor summaries, adds a verified-only buffer rate, and labels the legacy
ratio as a compatibility formula. Gateway and console checks cover grouped
inputs, inactive-row exclusion, weighted width, rounding, empty denominators,
and fixed labels. No populated archive or database was used, so output parity
against an owner-reviewed reference fixture remains open; rollback is a source
revert.

This is a prepared read path, not proof of populated output parity,
deployment-role least privilege,
forced-RLS coverage, live ZITADEL behavior, browser acceptance, historical
reference reconciliation, candidate rollout, or MAN-CAP-006 acceptance.
Migrations 602 and 603 have not been applied to the candidate. The existing
shared-identity CLI must not be treated as a tenant-safe writer until the
worker/runtime identity gates close.


## Tenant-scoped capture and review boundaries

`POST /operator/api/pollinators/{location_id}/observations` (migration 619),
`POST /operator/api/pollinators/{location_id}/pesticide-impacts` (migration
620), habitat registration (621), hive registration (622), and hive inspection
capture (623) require the exact location `pollinator_health:create` grant.
Each operation installs signed operator/location context on one PostgreSQL
connection, which the bounded security-definer function independently checks.
Payloads are capped and validated before database access; private receipts store
only request identity, location, record reference, and SHA-256 input digest.
Shared runtime and Directus roles cannot write these tables directly or read
receipts. Same-input retries return the original record; changed-input reuse is
rejected. Migrations 624 and 625 add audited habitat and hive
status/maintenance changes with exact detail/edit grants and immutable event
history.

Migration 626 adds a private paginated review queue and independent review of
recorded observations and pesticide-impact reports under exact
`pollinator_health:review`. Reviewers cannot decide on their own submissions;
decisions require a reason and the current source timestamp, and the source
status change plus immutable operator-attributed decision event commit
atomically. Identical request retries replay; altered reuse and stale decisions
fail closed. Only `reviewed` records appear in the existing reviewed summaries;
`dismissed` records remain excluded. Reviewing a pesticide report does not
approve pesticide use or certify safety. Habitat and hive operational values
remain self-reported; hive inspections are recorded observations without an
independent review route. The legacy observation, pesticide, habitat, hive,
and inspection CLI write commands fail before database access. Candidate and
legacy database rollout is separate and has not occurred.

Migration 626's focused Gateway, console, route-policy, and migration selection
passes 88 tests. Disposable PostgreSQL 16 applies/replays the pollinator chain
through migration 626 and passes 11 assertion groups on native x86_64 and
ARM64/QEMU ([native evidence](builds/2026-10-25-recovery/cap-006-pollinator-independent-review-disposable.json);
[ARM64/QEMU evidence](builds/2026-10-25-recovery/cap-006-pollinator-independent-review-arm64-disposable.json)).
QEMU is software portability evidence only, not physical Raspberry Pi
acceptance. Populated-data parity, live OIDC/browser, broader ACL/RLS, Directus
parity, and MAN-CAP-006 acceptance remain open.
