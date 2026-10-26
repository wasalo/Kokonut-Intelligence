# drivers

`services.drivers` — Driver plugin system — dynamic data source registration and loading.

## CLI Usage

```bash
python3 -m services.drivers.cli --help
```

## Modules

- `base` — Base driver class with common patterns (retry, logging, hashing).
- `cli` — CLI for the driver registry.
- `protocol` — DataSourceDriver protocol — the contract all data source drivers must implement.
- `registry` — Driver registry — built-in and installed entry-point data source drivers.

## Installing driver adapters

Built-in drivers resolve through the source-owned `BUILTIN_DRIVER_TARGETS`
map. A PostgreSQL `driver_registry.module_path` value cannot select Python code.
Third-party adapters remain supported through the `kokonut.drivers` Python
entry-point group: install the adapter package into the runtime image, then
register its entry-point name in `driver_registry`. The persisted `module_path`
and `class_name` must match that installed entry point; registration checks
this metadata before writing and does not import plugin code. Loading then
checks that the class implements the `DataSourceDriver` contract. For example,
a package can declare:

```toml
[project.entry-points."kokonut.drivers"]
weather_example = "weather_example.driver:Driver"
```

Installing an instance requires the registered driver to be enabled and its
`validate_config` method to accept a JSON-object configuration. Invalid or
non-JSON configuration fails before persistence; the database rechecks and
locks the enabled driver row while inserting the instance. Validation runs
inside the application process, so installed third-party packages remain
trusted executable code rather than sandboxed plugins.

Package installation is the trust boundary for third-party code. Database
registration alone never imports a module. Scheduled sensor execution remains
narrower: it accepts only targets explicitly listed in
`SCHEDULED_SENSOR_DRIVER_TARGETS`.

Sensor drivers are not schedulable by default. A pull driver must explicitly
set `supports_scheduled_pull = True`; the native sensor job then receives only
the driver-instance UUID and location UUID. It resolves configuration from an
enabled `sensor` instance bound to that exact location, caps one run at 100
sources and 10,000 records, validates every sensor against that location, and
commits sensor rows, projection outbox entries, ingestion audit, and reading
events atomically. Event-driven transports such as MQTT keep their own worker
and do not become polling jobs by appearing in the driver registry.

## Files

4 Python modules
