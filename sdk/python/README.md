# kokonut-intelligence

Python SDK for the Kokonut Intelligence Platform. Typed REST client wrapping Directus collections for farm, crop, harvest, sales, expenses, sensors, attestations, and reports.

> This SDK covers Directus REST operations only. For gRPC services (IRI, content hash, ecocredit classes/batches/balances, marketplace, bridge), use the generated stubs in `sdk/python/generated/`.

## Install

```bash
pip install kokonut-intelligence
```

With optional dependencies:

```bash
pip install kokonut-intelligence[clickhouse]  # ClickHouse support
pip install kokonut-intelligence[web3]        # Web3 support
pip install kokonut-intelligence[all]         # Everything
```

## Usage

```python
from kokonut import KokonutClient

client = KokonutClient("http://localhost:8055", token="your-token")

# List locations
locations = client.locations.list()

# Get a farm by ID
farm = client.farms.get("farm-uuid")

# List crop cycles for a plot
cycles = client.crop_cycles.list_by_plot("plot-uuid")

# Create a harvest event
harvest = client.harvest_events.create({
    "crop_cycle_id": "cycle-uuid",
    "plot_id": "plot-uuid",
    "location_id": "location-uuid",
    "harvest_date": "2026-07-15",
    "quantity": 500,
    "unit": "kg",
    "status": "draft",
})

# Query unpaid sales
unpaid = client.sales_events.list_unpaid()

# Aggregate query
count = client.aggregate("harvest_event", aggregate="count", groupBy="location_id")
```

## Authentication

```python
# Login with email/password
client.login("user@example.com", "password")

# Logout
client.logout()
```

## Error Handling

```python
from kokonut import KokonutError, AuthenticationError, NotFoundError, ForbiddenError, ValidationError

try:
    client.locations.get("nonexistent")
except NotFoundError:
    print("Location not found")
except AuthenticationError:
    print("Please log in")
except ForbiddenError:
    print("Permission denied")
except ValidationError as e:
    print(f"Invalid input: {e}")
except KokonutError as e:
    print(f"API error {e.status_code}: {e}")
```

## Method Groups

| Group | Collection | Extra Methods |
|-------|-----------|---------------|
| `locations` | `location` | — |
| `farms` | `farm` | `list_by_location` |
| `plots` | `plot` | `list_by_farm` |
| `crop_cycles` | `crop_cycle` | `list_by_plot`, `list_active` |
| `harvest_events` | `harvest_event` | `list_by_crop_cycle` |
| `sales_events` | `sales_event` | `list_by_crop_cycle`, `list_unpaid` |
| `expense_events` | `expense_event` | `list_by_crop_cycle`, `list_pending_approval` |
| `sensor_readings` | `sensor_reading` | `list_by_device`, `list_by_plot`, `list_anomalies` |
| `wallet_profiles` | `wallet_profile` | `find_by_address` |
| `attestations` | `attestation_record` | `list_pending`, `list_by_entity` |
| `reports` | `report_snapshot` | `list_by_type` |
| `exports` | `export_log` | `create_export` |
| `noi` | `noi_snapshot` | `list_by_crop_cycle` |

All groups inherit `GenericMethods`: `list`, `get`, `create`, `create_many`, `update`, `delete`.

## Examples

See `examples/` for runnable scripts:

```bash
python examples/create_farm.py
python examples/query_noi.py
python examples/batch_upload.py
python examples/pagination_and_errors.py
python examples/workflow.py
```
