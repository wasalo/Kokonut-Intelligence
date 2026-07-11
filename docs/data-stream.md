# Data Stream

Chronological data stream for environmental project tracking. Enables stakeholders to upload monitoring reports, photos, satellite imagery, and field updates as time-stamped posts that can be anchored on-chain via EAS.

## Post Types

| Type | Description | Typical Evidence |
|------|-------------|-----------------|
| `field_update` | General field activity update | Text, photos |
| `monitoring_report` | Structured monitoring report | PDF, images |
| `photo` | Photographic documentation | Images |
| `satellite_image` | Satellite imagery analysis | GeoTIFF, images |
| `sensor_reading` | Automated sensor data | CSV, sensor data |
| `soil_analysis` | Soil test results | PDF, CSV |
| `water_analysis` | Water quality test results | PDF, CSV |
| `biodiversity_survey` | Species observation records | Photos, PDF |
| `harvest_report` | Harvest activity report | PDF, images |
| `weather_report` | Weather data summary | CSV, images |
| `financial_report` | Financial activity report | PDF |
| `community_update` | Community engagement activity | Photos, PDF |
| `training_record` | Training/education activity | Photos, PDF |
| `intervention_record` | Agricultural intervention record | Photos, PDF |
| `compliance_record` | Compliance/audit record | PDF |

## Lifecycle

```
draft -> submitted -> verified -> published
                  \-> rejected -> draft
```

- **draft**: Post created, not yet submitted
- **submitted**: Awaiting review
- **verified**: Reviewed and verified by supervisor/manager
- **published**: Visible in public stream (requires verified/published farm registry)
- **rejected**: Returned for rework

## Visibility

| Visibility | Who Sees It |
|------------|-------------|
| `public` | Anyone (via public views) |
| `internal` | authenticated users only |
| `private` | Creator and admins only |

## Blockchain Anchoring

Posts can be anchored on Celo via EAS using the `kokonut-data-post` schema:

```bash
python3 -m services.data_stream.cli anchor --post-id <UUID> --chain celo
```

The anchoring creates an EAS attestation request with:
- `locationId`: Farm location
- `postType`: Type of data post
- `title`: Post title
- `contentHash`: SHA-256 hash of content
- `mediaType`: Type of media attached
- `timestamp`: Post creation time
- `visibility`: Public/internal/private
- `evidenceHash`: Hash of evidence files
- `payloadCid`: IPFS CID of full payload

## CLI Usage

```bash
# Create a new data post
python3 -m services.data_stream.cli post \
  --location-id <UUID> \
  --type photo \
  --title "Soil sampling site A" \
  --content "Collected samples at 30cm depth" \
  --evidence-url "https://..." \
  --visibility public

# View chronological stream for a project
python3 -m services.data_stream.cli stream --location-id <UUID> --limit 50

# Full-text search posts
python3 -m services.data_stream.cli search --query "soil moisture" --location-id <UUID>

# Anchor a post on-chain
python3 -m services.data_stream.cli anchor --post-id <UUID> --chain celo

# Verify post anchoring
python3 -m services.data_stream.cli verify --post-id <UUID>

# List posts by project
python3 -m services.data_stream.cli list --location-id <UUID> --type monitoring_report
```

## API (via Directus)

Data stream posts are accessible via the Directus REST/GraphQL API:

- `GET /items/data_stream_post` - List all posts
- `GET /items/data_stream_post/{id}` - Get a single post
- `POST /items/data_stream_post` - Create a new post
- `PATCH /items/data_stream_post/{id}` - Update a post
- `DELETE /items/data_stream_post/{id}` - Soft-delete a post

## Public Views

- `v_project_data_stream` - Chronological stream for each project (public, verified/published farms only)
- `v_data_stream_search` - Full-text search across all published posts

## Schema Files

- `schemas/postgres/100_data_stream.sql` - Core tables and views
- `schemas/seeds/101_pilot_data_stream_posts.sql` - Pilot data for Adelphi farm

## Service Files

- `services/data_stream/post.py` - Core CRUD operations
- `services/data_stream/stream.py` - Chronological stream queries
- `services/data_stream/anchor.py` - Blockchain anchoring via EAS
- `services/data_stream/cli.py` - CLI interface

## Integration with Existing Features

- **Attestation**: Posts can be anchored on-chain via EAS (requires `kokonut-data-post` schema registration)
- **Reports**: `data_stream_summary` report type available via report generator
- **AI Summaries**: AI summary service can incorporate data stream posts into project summaries
- **Safety**: `data_stream_post` and `data_stream_post_comment` are governed collections (agents cannot publish)
- **Workflow**: Standard lifecycle enforcement via Directus hooks
