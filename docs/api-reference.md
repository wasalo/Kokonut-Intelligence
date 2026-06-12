# API Reference

## Directus REST API

Base URL: `http://localhost:8055`

### Authentication

```bash
# Login
curl -X POST http://localhost:8055/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@kokonut.network", "password": "YOUR_PASSWORD"}'

# Use token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8055/items/location
```

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/items/{collection}` | GET | List items |
| `/items/{collection}/{id}` | GET | Get single item |
| `/items/{collection}` | POST | Create item(s) |
| `/items/{collection}/{id}` | PATCH | Update item |
| `/items/{collection}/{id}` | DELETE | Delete item |
| `/items/{collection}/aggregate` | GET | Aggregate queries |
| `/schema/snapshot` | GET | Export schema |
| `/schema/diff` | POST | Compute schema diff |
| `/schema/apply` | POST | Apply schema changes |

### Query Parameters

| Parameter | Example | Description |
|-----------|---------|-------------|
| `filter` | `filter={"status":{"_eq":"active"}}` | JSON filter |
| `sort` | `sort=-created_at` | Sort field (prefix `-` for desc) |
| `fields` | `fields=id,name,status` | Field selection |
| `limit` | `limit=50` | Results per page |
| `offset` | `offset=100` | Pagination offset |
| `search` | `search=kokonut` | Full-text search |
| `aggregate` | `aggregate=count` | Aggregate function |
| `group` | `group=category` | Group by field |

### Filter Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `_eq` | Equals | `{"status":{"_eq":"active"}}` |
| `_neq` | Not equals | `{"status":{"_neq":"deleted"}}` |
| `_gt` | Greater than | `{"amount":{"_gt":1000}}` |
| `_gte` | Greater or equal | `{"amount":{"_gte":1000}}` |
| `_lt` | Less than | `{"amount":{"_lt":500}}` |
| `_lte` | Less or equal | `{"amount":{"_lte":500}}` |
| `_in` | In list | `{"status":{"_in":["active","pending"]}}` |
| `_nin` | Not in list | `{"status":{"_nin":["deleted"]}}` |
| `_contains` | String contains | `{"name":{"_contains":"farm"}}` |
| `_starts_with` | Starts with | `{"name":{"_starts_with":"Kokonut"}}` |
| `_null` | Is null | `{"verified_at":{"_null":true}}` |
| `_nnull` | Is not null | `{"verified_at":{"_nnull":true}}` |

### Examples

```bash
# Get all active locations
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/location?filter={\"status\":{\"_eq\":\"active\"}}"

# Get crop cycles with related data
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/crop_cycle?fields=*,plot_id.name,crop_id.name"

# Create an expense event
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "location_id": "UUID",
    "expense_date": "2026-01-15",
    "category": "seeds",
    "description": "Maize seeds for Plot A",
    "amount": 250.00,
    "vendor": "AgroSupplies Co",
    "status": "draft"
  }' \
  "http://localhost:8055/items/expense_event"

# Aggregate: total expenses by category
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8055/items/expense_event/aggregate?groupBy=category&aggregate=sum:amount"
```

## GraphQL

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ location { id name slug farms { id name plots { id area } } } }"
  }' \
  http://localhost:8055/graphql
```

## ClickHouse HTTP API

Base URL: `http://localhost:8123`

```bash
# Query (with auth)
curl -u "kokonut:YOUR_PASSWORD" \
  "http://localhost:8123/?query=SELECT+count()+FROM+events_raw"

# Insert via POST body
curl -u "kokonut:YOUR_PASSWORD" \
  -X POST -d "INSERT INTO weather_events FORMAT JSONEachRow {...}" \
  "http://localhost:8123/"

# Native protocol (port 9000)
docker compose exec clickhouse \
  clickhouse-client --user kokonut --password YOUR_PASSWORD
```

## Directus MCP (AI Agent Access)

Directus has native MCP support for AI agents. Configure via Directus settings or environment variables.

```typescript
// Example: Using Directus SDK with MCP
import { createDirectus, rest } from '@directus/sdk';

const client = createDirectus('http://localhost:8055').with(rest());

// Agent reads location data
const locations = await client.request(
  readItems('location', {
    filter: { status: { _eq: 'active' } },
    fields: ['id', 'name', 'slug'],
  })
);
```
