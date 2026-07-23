# Data Stream

The data stream is a chronological evidence layer for environmental and
community project tracking. It records field updates, monitoring reports,
photos, sensor readings, analysis results, and other time-stamped posts linked
to a location. Posts can be reviewed through the governed lifecycle and can
create a pending EAS attestation request for later human or operator execution.

The PostgreSQL tables are canonical. Public views apply additional lifecycle,
visibility, privacy, location, and farm-registry gates. The local
`is_anchored` flag means that an attestation request was created; it does not,
by itself, prove that an on-chain EAS attestation was submitted or confirmed.

## Architecture

```text
data_stream_post
├── data_stream_file       evidence files and spatial metadata
├── data_stream_post_comment  comments and discussion metadata
└── attestation_request    pending EAS request metadata

create/update → draft → submitted → verified → published
                              └────→ rejected → draft

verified/published post → pending attestation request
public view             → published/verified + public + public_summary
                           + active location + verified farm registry
```

Implementation files:

| File | Responsibility |
|------|----------------|
| `services/data_stream/post.py` | Post validation and CRUD |
| `services/data_stream/stream.py` | Chronological and filtered feeds |
| `services/data_stream/files.py` | Evidence-file CRUD and geometry |
| `services/data_stream/anchor.py` | Attestation request creation and lookup |
| `services/data_stream/cli.py` | Command-line interface |
| `schemas/postgres/100_data_stream.sql` | Core tables, indexes, trigger, views |
| `schemas/postgres/113_arkiv_parity.sql` | Post expiration field and index |
| `schemas/postgres/114_geonode_parity.sql` | File CRS and hash fields |
| `schemas/postgres/179_lifecycle_transition.sql` | Lifecycle transition audit trigger |
| `schemas/postgres/298_consent_privacy_p0.sql` | Current public-view privacy gates |

## Post Types

`post_type` is constrained to the following values:

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
| `training_record` | Training or education activity | Photos, PDF |
| `intervention_record` | Agricultural intervention record | Photos, PDF |
| `compliance_record` | Compliance or audit record | PDF |

The service validates post types before creation. The database also constrains
the accepted values.

## Visibility And Privacy

`visibility` controls the intended audience:

| Value | Meaning |
|-------|---------|
| `public` | Eligible for public-view evaluation, subject to all public gates |
| `internal` | Authenticated internal users |
| `private` | Creator and administrators |

Public visibility is not sufficient for public publication. The current public
views additionally require:

```text
status IN ('verified', 'published')
visibility = 'public'
metadata->>'privacy' = 'public_summary'
location is active
location has a farm_registry_record with status verified or published
```

The `metadata.privacy` requirement was added by migration 298. Existing pilot
posts without `metadata.privacy = 'public_summary'` will not appear in the
current public views, even when their visibility is `public`.

## Lifecycle

```text
draft → submitted → verified → published
                      ↓
                   rejected → draft
```

| Status | Meaning |
|--------|---------|
| `draft` | Created or returned for rework; not submitted for review |
| `submitted` | Awaiting review |
| `verified` | Reviewed and verified by an authorized reviewer |
| `published` | Eligible for public-view evaluation when all public gates pass |
| `rejected` | Returned for rework; Directus permits transition back to `draft` |

The Directus workflow permits these transitions:

| From | To |
|------|----|
| `draft` | `submitted` |
| `submitted` | `verified`, `rejected` |
| `verified` | `published` |
| `rejected` | `draft` |
| `published` | terminal |

Directus validates the current database status and reviewer role before an
update. It adds workflow timestamps and records a lifecycle transition. The
database trigger from migration 179 records status changes in
`lifecycle_transition` using the session actor settings when available.

The Python service accepts direct status values in `update_post`; callers using
the service directly must enforce the same governance boundary themselves.
Rejection reasons are not currently required by the database or Directus hook,
and `delete_post` changes status to `rejected` without recording a deletion
reason.

## Post Schema

Table: `data_stream_post` in `schemas/postgres/100_data_stream.sql`.

| Column | Purpose |
|--------|---------|
| `id` | UUID primary key |
| `location_id` | Required location reference |
| `plot_id` | Optional plot reference |
| `crop_cycle_id` | Optional crop-cycle reference |
| `post_type` | One of the 15 supported types |
| `title` | Required title, maximum 255 characters |
| `content` | Free-text post content |
| `content_hash` | SHA-256 hash of content when content exists |
| `content_search` | English `tsvector` for title/content search |
| `evidence_urls` | Text array of evidence URLs |
| `evidence_hashes` | Text array of evidence hashes |
| `file_ids` | Referenced evidence-file UUIDs |
| `media_type` | Media classification supplied by caller |
| `is_anchored` | Local flag indicating request-level anchoring state |
| `attestation_uid` | EAS attestation UID when populated externally |
| `chain` | Chain label, default `celo` |
| `anchored_at` | Local anchoring timestamp |
| `visibility` | `public`, `internal`, or `private` |
| `status` | Governed lifecycle status |
| `schema_version` | Data-stream schema version, default `data-stream-v1` |
| `expires_at` | Optional expiration timestamp |
| `source_system` | Source-system lineage label |
| `source_id` | Source-system identifier |
| `source_raw` | Original source payload |
| `metadata` | Structured metadata and privacy declaration |
| `file_count` | Maintained count of attached files |
| `created_at` / `updated_at` | Audit timestamps |
| `created_by` / `updated_by` | Audit actors |

Constraints enforce supported post types, visibility values, and lifecycle
statuses. Indexes cover location, status, type, creation time, visibility,
evidence URLs, file IDs, and the full-text search vector.

### Content Hashing And Search

`create_post` computes a SHA-256 hash of `content` when content is present. A
database trigger maintains `content_search` using English text search weights:

- title receives weight `A`
- content receives weight `B`

Search therefore covers title and content only. It does not search evidence
URLs, metadata, comments, file names, or file descriptions.

## Comments

`data_stream_post_comment` stores comments associated with a post.

| Column | Purpose |
|--------|---------|
| `id` | Comment UUID |
| `post_id` | Parent post reference with cascade delete |
| `author_id` | Comment author |
| `content` | Required comment text |
| `is_anchored` | Local comment anchoring flag |
| `attestation_uid` | Optional attestation reference |
| `status` | Draft-first lifecycle: `draft`, `submitted`, `verified`, `published`, or `rejected` |
| `visibility` | Public, internal, or private visibility |
| `metadata` | Privacy declaration and moderation metadata |
| `created_at` / `updated_at` | Audit timestamps |

Migration `331_data_stream_public_governance.sql` adds status and visibility
constraints, a draft-first default, and database publication gates. Public post
views count only published comments with `visibility=public` and
`metadata.privacy=public_summary`. Comment moderation is governed by the
standard Directus lifecycle; there is still no dedicated comment CLI or comment
anchoring implementation.

Python agent safety classifies `data_stream_post_comment` as governed, but the
Directus human-review collection list does not currently provide equivalent
comment-specific enforcement.

## Evidence Files

`data_stream_file` stores files and optional spatial metadata attached to a
post.

| Column | Purpose |
|--------|---------|
| `id` | File record UUID |
| `post_id` | Parent post reference with cascade delete |
| `file_iri` | Linked-data identifier |
| `file_name` | Display filename |
| `file_description` | Description of evidence |
| `file_credit` | Attribution or credit |
| `file_url` | External or Directus URL |
| `directus_file_id` | Directus file reference |
| `media_type` | Image, video, document, sensor data, satellite, audio, or other |
| `file_size_bytes` | File size metadata |
| `mime_type` | MIME type metadata |
| `latitude` / `longitude` | Optional coordinate metadata |
| `geometry` | PostGIS point geometry, SRID 4326 |
| `crs` | Coordinate reference system, default `EPSG:4326` |
| `file_hash` | Optional file-content hash |
| `sort_order` | Display ordering |
| `created_at` | Creation timestamp |

The service supports add, list, metadata update, and remove operations. Migration
`331_data_stream_public_governance.sql` adds lifecycle, visibility, privacy,
audit, and soft-delete fields. Published files require a public-eligible parent
post and cannot be mutated. Coordinates are stored as `NULL` when omitted and
validated when supplied. `VALID_MEDIA_TYPES` is enforced by the service.

`data_stream_file` is included in the Python `GOVERNED_COLLECTIONS` list and in
the Directus lifecycle collection list. Public consumers should use
`v_data_stream_public_file`, not the base table.

## Service API

### Post Operations

`services.data_stream.post` provides:

| Function | Behavior |
|----------|----------|
| `create_post` | Validates type, visibility, and title; creates a draft and hashes content |
| `update_post` | Updates supplied fields, including status when called directly |
| `get_post` | Fetches one post |
| `list_posts_by_project` | Lists posts by location with status/type/visibility filters and pagination |
| `search_posts` | Full-text search with optional location and type filters |
| `delete_post` | Sets status to `rejected`; does not record a deletion reason |

Supported service-level creation fields include `plot_id`, `crop_cycle_id`,
`source_system`, `source_id`, `source_raw`, and structured `metadata`. The CLI
exposes only a subset of these fields.

### Stream Operations

| Function | Behavior |
|----------|----------|
| `get_project_stream` | Reads the public project view for one location |
| `get_chronological_feed` | Reads a chronological feed across optional locations and types |
| `get_filtered_stream` | Filters one location by type, date range, visibility, and limit |

`get_project_stream` accepts a `visibility` argument but currently does not use
it; it always queries `v_project_data_stream`, which is public-only.

### File Operations

| Function | Behavior |
|----------|----------|
| `add_file_to_post` | Creates file metadata and optional point geometry |
| `list_post_files` | Lists files for a post |
| `get_file` | Fetches one file record |
| `update_file_metadata` | Updates description, credit, IRI, and ordering metadata |
| `remove_file_from_post` | Hard-deletes a file and updates parent count |

## CLI Usage

Entry point: `python3 -m services.data_stream.cli`.

### Create And Read Posts

```bash
python3 -m services.data_stream.cli post \
  --location-id UUID \
  --type photo \
  --title "Soil sampling site A" \
  --content "Collected samples at 30cm depth" \
  --evidence-url "https://example.invalid/evidence" \
  --visibility public

python3 -m services.data_stream.cli stream \
  --location-id UUID --limit 50

python3 -m services.data_stream.cli search \
  --query "soil moisture" --location-id UUID --limit 20

python3 -m services.data_stream.cli list \
  --location-id UUID \
  --status verified \
  --type monitoring_report \
  --limit 50
```

`post` requires `--location-id` and `--title`. It accepts `--type`,
`--content`, `--visibility`, `--evidence-url`, `--file-id`, and `--media-type`.
The service accepts additional lineage and domain fields not exposed by this
CLI.

### Attestation Commands

```bash
python3 -m services.data_stream.cli anchor \
  --post-id UUID --chain celo

python3 -m services.data_stream.cli verify --post-id UUID
```

`anchor` requires a post in `verified` or `published` status. It creates a
pending `attestation_request` and sets local anchor fields. It does not submit
the EAS transaction itself.

### File Commands

```bash
python3 -m services.data_stream.cli file add \
  --post-id UUID \
  --name "soil-site-a.jpg" \
  --description "Sampling location" \
  --credit "Kokonut field team" \
  --url "https://example.invalid/file" \
  --media-type image \
  --latitude 18.5000000 \
  --longitude -69.9000000

python3 -m services.data_stream.cli file list --post-id UUID
python3 -m services.data_stream.cli file remove --file-id UUID
```

The file CLI also accepts `--iri`. It does not expose file size, MIME type, or
sort order.

## Search Semantics

There are two distinct search paths.

### Service Search

`search_posts` queries the base table's full-text vector. It can return posts in
`verified` or `published` status and does not enforce public visibility,
public-summary metadata, farm-registry status, or the public-view gates.

### Public Search View

`v_data_stream_search` is the public-oriented database view. The current
definition requires published or verified status, active locations, public
visibility, `metadata.privacy = 'public_summary'`, and a verified or published
farm registry record. Consumers needing public-safe search should use this view
or an API policy that reproduces its filters.

## Public Views

### `v_project_data_stream`

Chronological public stream for a project. The current definition exposes post
metadata, location and farm names, and comment count. It requires:

- post status `verified` or `published`
- `visibility = 'public'`
- `metadata->>'privacy' = 'public_summary'`
- active location
- verified or published `farm_registry_record`

### `v_data_stream_search`

Full-text public search over eligible posts. It applies the public lifecycle,
location, visibility, privacy, and registry gates. It is not equivalent to the
service-level `search_posts` query.

## Blockchain Anchoring

The application defines the `kokonut-data-post` EAS schema with these fields:

```text
string locationId,
string postType,
string title,
string contentHash,
string mediaType,
uint256 timestamp,
string visibility,
string evidenceHash,
string payloadCid
```

The helper `prepare_data_post_attestation_data` can encode all nine fields.
However, the current data-stream anchor service does not use that helper. Its
actual flow is:

1. Require status `verified` or `published`.
2. Return the existing record if `is_anchored` is already true.
3. Build a local JSON payload hash.
4. Look up the active database `attestation_schema` named `kokonut-data-post`.
5. Insert a `pending` `attestation_request`.
6. Set `is_anchored`, `chain`, and `anchored_at` locally.

The service does not submit an EAS transaction, set `attestation_uid`, use the
post's original `created_at` as the attestation timestamp, or populate the
schema's `evidenceHash` and `payloadCid` fields. `verify_post_anchoring` joins
through `attestation_uid`, so verification requires an external process to
complete the request and populate the UID.

### Seeded Schema State

The Celo seed entry for `Kokonut Data Post` currently has:

- chain `celo`
- resolver `0x6E1502c7a14b45aba5FC420dC92C1E3b38BD79Ad`
- an all-zero placeholder schema UID
- `active = FALSE`

Therefore anchoring is not ready on a fresh database unless an operator
registers and activates the schema separately. Do not describe the local anchor
command as proof of a completed on-chain attestation.

## Report Integration

`services/export/report_generator.py` registers `data_stream_summary`.

```bash
python3 -m services.export.report_generator \
  --type data_stream_summary --location-id UUID
```

The report includes:

| Field | Meaning |
|-------|---------|
| `report_type` | `data_stream_summary` |
| `location_id` | Location being summarized |
| `period_start` / `period_end` | Requested reporting window |
| `total_posts` | Number of matching base-table posts |
| `anchored_posts` | Posts with local `is_anchored = TRUE` |
| `unanchored_posts` | Posts with local `is_anchored = FALSE` |
| `by_type` | Counts by post type |
| `by_status` | Counts by lifecycle status |
| `by_visibility` | Counts by visibility |
| `generated_at` | Report generation timestamp |

The report reads location posts without applying public-view, privacy,
registry, or lifecycle restrictions beyond its own query. It can therefore
include private, draft, rejected, and non-public-summary records. Its anchored
count reflects the local boolean, not confirmed EAS attestations.

## AI Summary Integration

The current AI summary service does **not** query `data_stream_post`, comments,
files, or either data-stream view. Its implemented source domains are harvest,
sales, crop cycles, sensor readings, financial data, soil carbon, biodiversity,
remote sensing, and weather.

Consequently, data-stream posts are not currently incorporated into generated
AI summaries. Any future integration must preserve the AI summary requirement
for a verified or published farm registry and must store generated summaries as
drafts until human review.

## Governance And Safety

### Directus Workflow

`data_stream_post` is a lifecycle-managed Directus collection. Directus:

- reads the current database status before transition
- validates the allowed transition
- checks the accountable user's role
- writes workflow timestamps and actor fields where applicable
- records a workflow transition after update

Authorized roles include manager, supervisor, and admin for verification or
rejection, and manager or admin for publication. The broad submitted transition
also permits nonempty roles according to the current hook configuration.

There are no equivalent data-stream-specific Directus workflow hooks for
`data_stream_post_comment` or `data_stream_file`.

### Python Agent Safety

Python agent safety includes:

- `data_stream_post`
- `data_stream_post_comment`

Agents may create or update permitted draft, submitted, or rejected records but
cannot verify or publish them. `data_stream_file` is not currently included in
the governed-collection list.

The Python safety layer and Directus hook layer are therefore not identical;
both must be considered when reviewing an automated or API-originated write.

## Pilot Data

`schemas/seeds/101_pilot_data_stream_posts.sql` seeds 15 Adelphi posts and
three comments using idempotent `ON CONFLICT (id) DO UPDATE` behavior. The pilot
uses field updates, photos, monitoring reports, sensor readings, and community
updates, with mixed lifecycle and visibility states.

The seed does not populate content hashes, evidence hashes, privacy metadata,
attestation UIDs, or file records. As a result, public pilot posts without
`metadata.privacy = 'public_summary'` are excluded by the current public views.

## Tests And Known Gaps

Relevant tests include:

- `tests/test_data_stream.py` — CRUD, hashes, streams, anchoring mocks, files,
  constants, public-view SQL assertions, report registration, and EAS schema
  definition
- `tests/test_gateway_auth.py` — gateway authorization and API-key scope
- `tests/test_process_health.py` — process-health use of data-stream posts
- `tests/test_process_architecture.py` — process-model registration
- `tests/test_workflow_spec_conformance.py` — workflow specification registration
- `tests/test_linked_data.py` — linked-data entity coverage

Important remaining gaps:

- No test confirms actual EAS submission or UID population.
- No integration test validates the PostgreSQL public-view privacy gate against
  pilot data.
- No comment anchoring test exists; local comment anchoring fields remain
  intentionally separate from confirmed EAS state.
- No end-to-end Directus test covers comment/file publication against a live
  database.
- No test validates all public service paths against the public views.
- No test validates the new soft-delete behavior against a live database.
- No test validates the inactive or zero-UID seeded EAS schema.
- Workflow specification and Directus behavior differ on rejected-state
  terminality and rejection reasons.

## Schema And Service References

- `schemas/postgres/100_data_stream.sql` — core post, comment, file, trigger,
  indexes, and initial views
- `schemas/postgres/113_arkiv_parity.sql` — `expires_at`
- `schemas/postgres/114_geonode_parity.sql` — file CRS and hash fields
- `schemas/postgres/179_lifecycle_transition.sql` — lifecycle audit trigger
- `schemas/postgres/298_consent_privacy_p0.sql` — current public-view privacy
  and registry gates
- `schemas/postgres/331_data_stream_public_governance.sql` — publication,
  immutability, comment/file governance, and public attachment view
- `schemas/seeds/101_pilot_data_stream_posts.sql` — Adelphi pilot records
- `schemas/seeds/014_pilot_celo_eas.sql` — Celo data-post schema seed state
- `services/attestation/schemas.py` — EAS schema text and encoding helper
- `services/workflow_specs/data_stream_post.py` — workflow specification
- `extensions/kokonut-hooks/src/workflow.ts` — Directus lifecycle enforcement
- `services/agents/safety.py` — Python governed-collection enforcement
