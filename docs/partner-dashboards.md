# Partner Dashboard Flexibility Guide

Kokonut Intelligence supports three approaches for building and embedding partner dashboards. Choose based on your use case, technical requirements, and maintenance capacity.

## Approaches at a Glance

| Approach | Flexibility | Complexity | Maintenance | Best For |
|----------|------------|------------|-------------|----------|
| Directus Dashboard Module | Medium | Low | Low | Internal ops, quick dashboards |
| Metabase Embedded | High | Medium | Medium | BI analytics, parameterized reports |
| Custom React App | Full | High | High | White-label, complex UX |

## 1. Directus Dashboard Module

Built into Directus. Configure dashboards entirely through the admin UI with no external dependencies.

### Setup

1. Open Directus at `https://localhost/admin` in base Compose, or at your organization's Directus URL
2. Navigate to **Dashboards** → **Create Dashboard**
3. Add panels using the visual editor:
   - **Metric panel**: Single value (e.g., total harvest this month)
   - **Chart panel**: Bar, line, pie charts from collections
   - **Table panel**: Filtered list of records
   - **Markdown panel**: Custom notes or links
4. Set **Sharing** to generate a shareable link or embed code

### Role-Based Access

Directus permissions control who sees what:

```sql
-- Grant dashboard access to Supervisor role only
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
VALUES (
    (SELECT id FROM directus_role WHERE name = 'Supervisor'),
    'harvest_event',
    'read',
    '{"_and": [{"location_id": {"_eq": "$CURRENT_USER.location_id"}}]}',
    'id,harvest_date,quantity,unit,status'
);
```

### Embedding

Use the Directus embed URL. Base Compose routes Directus through Caddy; direct `http://localhost:8055` URLs only work when a local override exposes that port.

```html
<iframe
  src="https://localhost/directus/dashboards/DASHBOARD_ID"
  width="100%"
  height="600"
  frameborder="0"
></iframe>
```

## 2. Metabase Embedded

Metabase provides full BI capabilities with signed embedding for secure partner access.

### Setup

1. Open Metabase at `https://localhost/metabase` in base Compose, or at your organization's Metabase URL
2. Connect to the `kokonut_intelligence` PostgreSQL database
3. Create questions and dashboards in Metabase
4. Enable embedding in **Admin → Embedding**
5. Generate signed embedding URLs

### Signed Embedding

Metabase uses JWT tokens to secure embedded dashboards:

```python
import jwt
import time

METABASE_SECRET = os.environ["METABASE_EMBEDDING_SECRET_KEY"]

def get_metabase_embed_url(resource_id, params=None):
    """Generate a signed Metabase embed URL."""
    payload = {
        "resource": {"dashboard": resource_id},
        "params": params or {},
        "exp": int(time.time()) + 300,  # 5 min expiry
    }
    token = jwt.encode(payload, METABASE_SECRET, algorithm="HS256")
    metabase_url = os.environ.get("METABASE_URL", "https://localhost/metabase")
    return f"{metabase_url}/embed/dashboard/{token}"
```

### Parameterized Filters

Pass filter values to embedded dashboards:

```html
<iframe
  src="https://localhost/metabase/embed/dashboard/TOKEN?location=costa-rica&crop=coffee"
  width="100%"
  height="600"
  frameborder="0"
></iframe>
```

### Iframe Embedding Example

```python
# In a Flask/FastAPI route
@app.get("/partner/{partner_id}/dashboard")
def partner_dashboard(partner_id):
    # Fetch partner's allowed location IDs
    locations = get_partner_locations(partner_id)

    embed_url = get_metabase_embed_url(
        resource_id=DASHBOARD_ID,
        params={"location_id": [str(lid) for lid in locations]}
    )
    return f'<iframe src="{embed_url}" width="100%" height="800"></iframe>'
```

## 3. Custom React App

Full control over the UI. Query Directus REST/GraphQL directly and build any interface.

### Setup

```bash
# Create a React app
npx create-react-app partner-portal --template typescript

# Install Directus SDK
npm install @directus/sdk
```

### Connecting to Directus

```typescript
import { createDirectus, rest, authentication } from "@directus/sdk";

const directus = createDirectus(process.env.DIRECTUS_URL ?? "https://localhost/directus")
  .with(rest())
  .with(authentication());

// Login
await directus.login({ email: "partner@example.com", password: "..." });

// Fetch farm data
const farms = await directus.request(
  readItems("farm", {
    fields: ["id", "name", "total_area", "location_id.name"],
    filter: { location_id: { _in: partnerLocationIds } },
  })
);
```

### Row-Level Security Pattern

Create a Directus role per partner with filter rules:

```sql
-- Partner role with location-scoped access
INSERT INTO directus_permissions (role, collection, action, permissions, fields)
SELECT
    (SELECT id FROM directus_role WHERE name = 'partner-acme'),
    collection,
    'read',
    '{"_and": [{"location_id": {"_in": $CURRENT_USER.app_metadata.locations}}]}',
    '*'
FROM (VALUES
    ('farm'), ('plot'), ('crop_cycle'),
    ('harvest_event'), ('sales_event'), ('expense_event')
) AS t(collection);
```

### Row-Level Security Patterns

| Pattern | SQL Filter | Use Case |
|---------|------------|----------|
| Location-scoped | `{"location_id": {"_in": "$CURRENT_USER.locations"}}` | Partner sees only their farms |
| Role-scoped | `{"created_by": {"_eq": "$CURRENT_USER.id"}}` | User sees own records |
| Status-scoped | `{"status": {"_eq": "published"}}` | Public data only |
| Date-scoped | `{"harvest_date": {"_gte": "$CURRENT_USER.onboarding_date"}}` | Post-onboarding data |

## Recommended Approach by Partner Type

| Partner Type | Recommended | Why |
|-------------|-------------|-----|
| Internal operations | Directus Module | Quick setup, same admin UI |
| Investor / funder | Metabase Embedded | Rich BI, parameterized reports |
| NGO / auditor | Directus Module or Metabase | Depends on data complexity |
| White-label reseller | Custom React App | Full branding control |
| Research partner | Custom React App | Custom visualizations |

## Security Notes

- Never expose raw database credentials to partners
- Use signed Metabase tokens with short expiry
- Directus API keys should be scoped to specific collections
- All partner API access is logged to `audit_log`
- Review partner permissions quarterly
