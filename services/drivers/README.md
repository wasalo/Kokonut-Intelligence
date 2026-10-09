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

## Files

4 Python modules
