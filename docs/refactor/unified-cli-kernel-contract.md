# Unified CLI Kernel contract

**Status:** the command tree is deployed; common registration/help/forwarding
checks pass. Full module-level legacy CLI parity remains open.

## Entry points

`python3 -m services.cli` is the unified entry point. Native Typer groups such
as `kernel`, `dao`, and `treasury` stay native. The legacy argparse commands in
`services.cli._MOUNTED` are registered through the shared `mount_argparse`
adapter, which forwards trailing arguments to each legacy `main()` and restores
the caller's `sys.argv`, including when parsing raises `SystemExit`.

The outer Typer command owns `--help`; use an argument separator to invoke the
legacy parser's own help, for example:

```sh
python3 -m services.cli agents -- --help
```

The registered agent task catalogue supports a database-free list command:

```sh
python3 -m services.cli agents list
```

## Verification

`tests/test_cli.py` checks that all mounted command names appear in root help,
every mounted wrapper displays help, and each registered adapter forwards a
synthetic unknown option and positional value to its own legacy `main()` while
restoring `sys.argv`. It also executes the offline agent catalogue list and
legacy argparse help through the unified command tree. A subprocess sweep
invokes actual parser help for all 37 mounted argparse groups with an
intentionally unavailable SOPS key; every parser exits successfully without
attempting secret decryption.

A second subprocess sweep sends an invalid non-help option through all 37
mounted parsers with an unavailable SOPS key and a closed loopback PostgreSQL
port. Every group rejects it with argparse usage/error output and exit code 2
before secret decryption or database connection. The ingestion wrapper now
rejects unknown top-level arguments instead of printing help and returning
success; no-argument help and `--list` remain available. See the
[preflight evidence](builds/2026-10-19-recovery/cap-039-invalid-argument-preflight.json).

The legacy module imports are intentionally lazy. CAP-038 moved agent audit
database imports behind the explicit audit-write call so task listing does not
decrypt secrets. `services.common.db` also skips secret loading when an explicit
`-h` / `--help` token is present; help exits before any database operation.
This source slice does not invoke databases or providers.

## Successful offline command parity sample

The first success-path parity group compares standalone module output with its
mounted unified command using the same arguments. It covers:

| Mounted group | Successful invocation | Dependency classification | Output boundary |
| --- | --- | --- | --- |
| `agents` | `list` | Local task catalogue; no database or provider | Newline-delimited registered task keys |
| `ingestion` | `--list` | Local static registry; no database or provider | Sorted tool names and descriptions |
| `ingestion` | `status log --source openweathermap`; `status indexers`; `status summary` | Synthetic PostgreSQL reads; no provider is contacted | Matching standalone/unified text/JSON; source/status/limit filters are bound, errors are redacted, and connections/cursors close |
| `ingestion` | `device_manager --list --location-id <synthetic-location-uuid>`; `device_manager --health --device-id <synthetic-device> --location-id <synthetic-location-uuid>` | PostgreSQL device reads through the mounted module; connection and cursor are synthetic | JSON location-scoped device inventory or health record |
| `ingestion` | `device_manager --register --device-id <synthetic-device> --sensor-type <synthetic-type> --location-id <synthetic-location-uuid>` | PostgreSQL registration transaction is mocked | JSON registered-device receipt; device and initial health row commit atomically |
| `ingestion` | `sensor_ingester --list --location-id <synthetic-location-uuid>` | Location-scoped PostgreSQL read through the ingestion module; cursor and connection are synthetic | Logged active-sensor inventory rows |
| `ingestion` | `sensor_ingester --calibration --location-id <synthetic-location-uuid>` | Location-scoped PostgreSQL read through the ingestion module; cursor and connection are synthetic | Logged calibration status; no sensor values are changed |
| `ingestion` | `sensor_ingester --sensor <synthetic-device> --value 12.5 --location-id <synthetic-location-uuid>` | Writer function is stubbed; database and event-bus effects are not run | No stdout; exact standalone/unified argument forwarding |
| `ingestion` | `sensor_ingester --file <synthetic-csv-path> --location-id <synthetic-location-uuid>` | Parity test stubs the writer; separate temporary-CSV checks exercise rejects/success with a fake connection | Matching argument forwarding; row audits preserve the exact location and caller connection, with sensitive values redacted |
| `ingestion` | `sensor_ingester --driver-instance-id <synthetic-instance-uuid> --location-id <synthetic-location-uuid>` | Scheduled driver function is stubbed; provider and database effects are not run | No stdout; exact standalone/unified argument forwarding |
| `ingestion` | `climate_data --worldclim`, `--ncep`, `--modis`, `--smap`, `--sentinel1`, or `--all`, each with `--location-id <synthetic-location-uuid>` | Dataset functions are stubbed; PostgreSQL connections are synthetic | Matching standalone/unified JSON receipts; conflicting selectors fail before DB setup |
| `ingestion` | `remote_sensing --file <synthetic-csv> --location-id <synthetic-location-uuid>` or `--all-locations` | Plot mapping is synthetic; canonical/ClickHouse writes are stubbed | Matching logged import summary; aggregate scope requires the explicit flag |
| `ingestion` | `remote_sensing_fetcher --list-jobs --location-id <synthetic-location-uuid>` | PostgreSQL job inventory read through the mounted module; cursor and connection are synthetic | JSON location-scoped job rows; missing/malformed location rejected before DB setup |
| `ingestion` | `remote_sensing_fetcher --location-id <synthetic-location-uuid> --provider copernicus --cadence-days 14` | PostgreSQL insert is synthetic | JSON job receipt; invalid cadence rejected before DB setup; insert rollback and cursor cleanup covered |
| `ingestion` | `remote_sensing_fetcher --job-id <synthetic-job-uuid> --location-id <synthetic-location-uuid>` | Location-qualified PostgreSQL lookup is synthetic; provider execution is stubbed | Matching standalone/unified JSON result; empty or malformed job UUID rejected before DB setup |
| `ingestion` | `weather --location-id <synthetic-location-uuid>` or explicit `--all-locations` | PostgreSQL location query returns synthetic empty results; no provider is contacted | Matching standalone/unified logs and scope; invalid location rejected before DB setup |
| `ingestion` | `weather_forecast --location-id <synthetic-location-uuid>` or explicit `--all-locations` | PostgreSQL location query returns synthetic empty results; no provider is contacted | Matching standalone/unified logs and scope; invalid location rejected before DB setup |
| `ingestion` | `data_freshness --summary` | PostgreSQL summary-view rows are synthetic | Matching standalone/unified JSON; cursor/connection close on execute or fetch failure; global operator boundary remains unverified |
| `ingestion` | `data_freshness --check --source weather` | Freshness checker is stubbed; no query or write runs | Matching standalone/unified JSON dispatch; `--source` requires `--check` |
| `ingestion` | `anomaly_detector --list-rules` | PostgreSQL rule rows are synthetic | Matching standalone/unified log output; query is global, location selectors rejected; operator authorization remains open |
| `ingestion` | `market_data --source world_bank --commodity COFFEE --month 6 --year 2026` or `--source seed --commodity COFFEE` | Ingestion `run()` is stubbed; no provider or database is accessed | Exact argument forwarding and standalone/unified help output match; invalid source/date filters fail before ingestion |
| `ingestion` | `price_attestation --commodity coffee --price 2.5 --source world_bank`; `--run-daily`; incomplete/help invocation | Connection and attestation operations are synthetic; malformed inputs fail before PostgreSQL | Matching standalone/unified arguments and help; non-positive/non-finite prices and conflicting modes reject before setup; manual/daily paths close connections |
| `ingestion` | `gis_import --file <synthetic-geojson> --target plot` | Import `run()` is stubbed; file parsing and database effects do not run | Exact standalone/unified argument forwarding and help output match; missing file/invalid target reject before import |
| `ingestion` | `http_sensor_receiver --host 127.0.0.1 --port 18056` | Server `run()` is stubbed; no listener or database is started | Matching host/port forwarding and help; non-integer and out-of-range ports reject before startup |
| `ingestion` | `mqtt_subscriber --broker mqtt.synthetic --port 18883` | Subscriber `run()` is stubbed; no broker or database is contacted | Matching broker/port forwarding and help; non-integer/out-of-range ports reject before startup; malformed port env preserves help and fails operation preflight |
| `ingestion` | `eas_indexer --chain celo` | Indexer `run()` is stubbed; no chain or database is contacted | Matching chain argument and help; unsupported chain rejects before indexer dispatch |
| `ingestion` | `gnosis_indexer --from-block 350 --to-block 375` | Indexer `run()` is stubbed; no provider or database is contacted | Matching standalone/unified block interval; invalid numbers/ranges fail before provider/DB setup |
| `ingestion` | `baal_indexer --from-block 350 --to-block 375` | Provider/database setup is stubbed or rejected before access | Matching interval; negative/reversed ranges fail early, and explicit block zero remains zero |
| `ingestion` | `mock_sensors --setup`; `--generate --count 7 --anomalies`; `--cleanup` | Demo actions are stubbed; no mock data or alert is written/deleted | Matching action and argument dispatch; no-action invocation only displays help |
| `mobile-forms` | `validate --manifest <synthetic-file>` and `preview --manifest <synthetic-file>` | Local file and schema validation; no database or provider | JSON summary reports `database_write: false`; preview reports `publication: not applied` |
| `audit-spool` | `status --path <missing-private-path>` | Local SQLite capacity check; no PostgreSQL or provider; missing-file status does not create the journal | JSON capacity summary; no journal contents |
| `systems` | `--list-modules` | Local Python module registry; no database or provider | Sorted module names and descriptions |
| `attestation` | `schema list` | Local schema registry; no database, chain, or signer | Formatted registered schema definitions |
| `capability-map` | `list --status active` | PostgreSQL read through the capability-map service; the query is stubbed in this test | JSON capability rows |
| `stakeholders` | `list --party-type organization` | PostgreSQL read; connection and query are stubbed in this test | JSON party rows |
| `strategy-map` | `list --perspective financial` | PostgreSQL read through strategy-map service; query is stubbed in this test | JSON strategy rows |
| `value-stream-defs` | `list --stakeholder farmer` | PostgreSQL read through value-stream service; query is stubbed in this test | JSON value-stream rows |
| `vision-mission` | `current --entity-type organization` | PostgreSQL read through vision/mission service; query is stubbed in this test | JSON current statement rows |
| `technology-roadmap` | `list --entity-type location` | PostgreSQL read through roadmap service; query is stubbed in this test | JSON roadmap rows |
| `consent` | `list --party-id <synthetic-party> --status active` | PostgreSQL read; connection and query are stubbed | JSON effective consent rows |
| `coordination` | `list --status approved --type alliance` | PostgreSQL read through coordination service; query is stubbed | JSON alliance rows |
| `governance-proposals` | `list --circle-id <synthetic-circle> --status submitted` | PostgreSQL read; connection and query are stubbed | JSON proposal lineage rows |
| `stakeholder-decisions` | `list --status approved --scope-id <synthetic-scope>` | PostgreSQL read; connection and query are stubbed | JSON decision lineage rows |
| `stakeholder-engagement` | `list-plans --stakeholder-party-id <synthetic-party> --status active` | PostgreSQL read; connection and query are stubbed | JSON engagement plan rows |
| `governance` | `circle-list --status active --scope-type location` | PostgreSQL read; connection and query are stubbed | JSON governance circle rows |
| `governance-links` | `list --source-circle-id <synthetic-source> --status active` | PostgreSQL read; connection and query are stubbed | JSON cross-circle link rows |
| `governance-tactical` | `session-list --circle-id <synthetic-circle> --status active` | PostgreSQL read; connection and query are stubbed | JSON tactical session rows |
| `governance-tensions` | `list --circle-id <synthetic-circle> --status submitted --overdue-only` | PostgreSQL read; connection and query are stubbed | JSON tension health rows |
| `stakeholder-grievances` | `health --status submitted --overdue-only` | PostgreSQL read; connection and query are stubbed | JSON grievance health rows |
| `stakeholder-identity` | `queue` | PostgreSQL read; connection and query are stubbed | JSON identity-resolution queue rows |
| `stakeholder-representation` | `distribution-summary --scope-type location --scope-id <synthetic-location>` | PostgreSQL read; connection and query are stubbed | JSON distribution summary rows |
| `stakeholder-trust` | `timeline <synthetic-party>` | PostgreSQL read; connection and query are stubbed | JSON trust evidence rows |
| `metrics` | `--list --json` | PostgreSQL read; connection and cursor are stubbed | JSON metric-definition rows |
| `forecast` | `--list` | PostgreSQL read; connection and cursor are stubbed | Formatted scenario catalogue |
| `analytics` | `--emission-factors` | PostgreSQL read through a context-managed connection; query is stubbed | JSON GHG emission-factor rows |
| `crisp` | `--weights --location-id <synthetic-location>` | PostgreSQL read; connection and query are stubbed | JSON normalized location weights |
| `delphi` | `list-studies` | PostgreSQL read; connection and cursor are stubbed | One JSON study row per line |
| `threatcasting` | `list-threats --location-id <synthetic-location> --type climate` | PostgreSQL read; connection and cursor are stubbed | One JSON threat row per line |
| `export` | `--list --location-id <synthetic-location-uuid>` | PostgreSQL read through report-snapshot service; query is stubbed | Formatted report-snapshot table |
| `migration` | `validate --schemas-only` | Local migration-source files; no database or secrets | Validated migration-source file count |
| `mobile-tenant-preflight` | `--location-id <synthetic-location-uuid>` | PostgreSQL read through the dedicated tenant-preflight service; service is stubbed | Aggregate-only JSON inventory |
| `mobile-media-cleanup` | `--limit 17` | PostgreSQL eligibility-count read is stubbed; dry-run does not initialize object storage | JSON expiry preview |
| `mobile-media-reconcile` | `--older-than-hours 48 --limit 9` | Registered-key query and private object inventory are stubbed; dry-run does not delete | JSON orphan preview without object keys |
| `operator` | `farm-activity-role templates` | Local role-to-scope registry; no database or grant mutation | JSON role-to-scope catalogue |
| `operator` | `revoke-grant --grant-id <uuid> --revoked-by <actor> --reason <reason>` | PostgreSQL update is stubbed | JSON revoked-grant receipt with audit actor/reason |
| `operator` | `identity provision --issuer <https-url> --subject <subject> --display-name <name>` | PostgreSQL insert/update is stubbed | JSON identity receipt; active identity refresh cannot change enabled state |
| `operator` | `list` | Five PostgreSQL inventory queries return synthetic rows | JSON identities, grants, memberships, shares, and tenant transfers |
| `operator` | `identity disable --operator-id <uuid> --disabled-by <label> --reason <text>` | Identity update, active-session revocation, and append-only audit insert are stubbed in one transaction | JSON identity receipt plus audit receipt; actor label is caller-supplied, not authenticated |

For each row, the regression invokes both `python -m <legacy-module>` and
`python -m services.cli <group> -- ...`, then compares exit status and output.
The form fixture is synthetic, and the spool path is a fresh temporary path.
The test environment sets an unavailable SOPS identity and a closed loopback
PostgreSQL URL so accidental secret/database setup fails instead of reaching a
real service. Nine successful offline invocations, forty-four other
PostgreSQL-backed read invocations with stubbed query functions (including
ingestion status and location-scoped device reads), one operator inventory
read, one tenant-preflight invocation with a synthetic aggregate service
report, two synthetic report-generation paths (single and automatic
batch), three operator write invocations, one device registration write, one
remote-sensing scheduled-job creation write,
three sensor write/driver argument-forwarding invocations, six climate
operation-selection variants, and two remote-sensing CSV scope modes with
stubbed persistence functions match
standalone output across all 37 mounted groups (157 tests including
operator identity/revocation safety, Delphi, and media service suites,
error-path cleanup, and the native Typer command-tree
comparison below). See [the test](../../tests/test_unified_cli_success_contract.py)
and [the recorded evidence](builds/2026-10-20-recovery/cap-039-offline-success-parity.json).

The native Typer command tree is also compared between standalone and unified
registration for `kernel`, `dao`, and `treasury`, including child command
names, help text, argument types, required flags, and option names. The unified
root deliberately disables shell completion, so the standalone groups'
`--install-completion` and `--show-completion` root options are excluded from
the comparison. The check inspects command metadata only; it does not invoke a
database or chain/provider command. These checks run with the offline output
parity cases in a 157-test selection ([tests](../../tests/test_cli.py) and
[evidence](builds/2026-10-20-recovery/cap-039-offline-success-parity.json)).

The forty-five query-backed success paths (including the operator inventory),
one aggregate-service-stubbed tenant-preflight path, two synthetic report-
generation paths (single and automatic batch), and three fake-connection
operator writes exercise their real parsers, forwarding, and JSON or text output
paths from both entry points with synthetic results. The grant-revocation case confirms the required
actor and reason reach the UPDATE; it does not test database authorization. The
identity-provision case confirms an existing enabled identity can be refreshed
without changing its enabled state; the separate focused source check verifies
that a disabled identity is rejected and cannot be re-enabled through this
command. The identity-disable case verifies the identity update and session
revocation share one transaction and that a session-update failure rolls back;
it does not add actor/reason audit or establish database authorization.

The automatic report-batch parity case asserts run/item creation and success
transitions, exact location scope, the read-only calculation wrapper, snapshot
ordering, and connection cleanup using fake cursors. The single-report case
asserts the calculation/persistence ordering too. The synthetic auto-failure
case verifies per-report redaction, continuation to the next report, a persisted
`partial` run, failure exit status, and connection cleanup in both entry points.
The connection-taking commands use fake connections and prove they close them.
The governance proposal, role, link, tactical, and tension read CLIs close their
connections after both successful and failing service calls. The stakeholder
grievance, identity, representation, and trust read paths also close their
connections on success. The forecast catalogue closes its connection after
both successful and failing reads. CRISP weights likewise closes after success
and failure; Delphi study listing and Threatcasting threat listing close their
cursors and connections on both paths. Export snapshot listing closes its connection on success. Connection creation,
list/verify queries, connection-close failures, and automatic report-run setup
failures emit only the exception class; injected standalone/unified regressions
cover each failure boundary and confirm cleanup whenever a connection opened. The media-cleanup dry-run does not initialize the
provider; media reconciliation uses only a stubbed inventory and confirms no
deletion. The cases confirm parsed filters reach expected
service calls; they do not claim database query behavior or authorization.

Every mounted group now has at least one successful output-parity path. This
selection covers nine offline invocations across eight groups, forty-five
stubbed database-query paths (including the operator inventory), one
aggregate-service path, two synthetic report-generation paths, three
fake-connection operator writes, and the market-data, price-attestation,
GIS-import, HTTP sensor-receiver, MQTT subscriber, EAS/Gnosis indexer, and
mock-sensor parser/dispatch paths. Every registered ingestion module must
provide a callable `main()` entry point; the dispatcher fails closed if that
contract is missing and never executes module source through `runpy`. Mock
sensor generation selects only devices explicitly marked by setup, and cleanup
scopes alert/reading deletion to those devices while retaining registry rows.
Identity
provisioning no longer re-enables a disabled subject; the CLI exposes no
reactivation operation.
The global identity/access list is unfiltered and exposes issuer, subject,
email, and access history; its role boundary remains open. Grant, membership,
share, and tenant-transfer mutations still need
command-specific dependency and authorization-boundary review. Manual grant
revocation requires actor and reason, and membership/share cascades record that
attribution on associated grants. Real database/provider behavior and
MAN-CAP-039 owner acceptance remain open.

See the [operator CLI boundary inventory](operator-cli-boundary-inventory.md)
for the command-by-command caller, actor, database-principal, and owner-review
classification. `operator list` is parity-tested with synthetic rows but remains
global, unfiltered, and restricted to the trusted local DBA surface.

## Remaining parity gates

The invalid-option preflight proves rejection behavior only. It does not prove
successful module-specific non-help arguments, output parity, database/provider
operation, or operator authorization. Those remain to be exercised per command
in isolated groups. Module-specific commands should declare whether they
require a database, provider, or operator authorization. The unified CLI does
not itself grant authorization to a legacy command. MAN-CAP-039 remains open
until those checks and operator review are complete.
