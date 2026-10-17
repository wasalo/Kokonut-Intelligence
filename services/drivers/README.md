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
- `registry` — Driver registry — dynamic discovery, registration, and loading of data source drivers.

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
