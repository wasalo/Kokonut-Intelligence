# Schema.org Alignment

## Overview

Kokonut's LinkML schemas use schema.org V30.0-style conventions for common properties, but they are not exclusively schema.org schemas. Domain-specific properties use the Regen Framework (`rfs:`), QUDT, GeoSPARQL, CIDS, and Kokonut namespaces. `slot_uri` mappings are declarative schema metadata; the runtime JSON-LD helper does not automatically load or expand them.

The LinkML YAML files declare `schema: http://schema.org/`. The JSON-LD helper's default context uses `https://schema.org`. Consumers should treat these as the schema.org namespace and should not assume byte-for-byte URI identity between YAML prefixes and generated context values.

## Namespaces

| Prefix | Runtime context URI | Use |
|---|---|---|
| `schema` | `https://schema.org` | Common web/entity properties and `schema:Link`/`schema:PropertyValue` |
| `kokonut` | `https://kokonut.network/ontology#` | Kokonut entity vocabulary and JSON-LD types |
| `rfs` | `https://framework.regen.network/schema/` | Regen Framework project and credit-class properties |
| `qudt` | `http://qudt.org/schema/qudt/` | Quantitative values and units |
| `geo` | `http://www.opengis.net/ont/geosparql/` | Runtime GeoSPARQL context mappings |

The core YAML schema uses `http://www.opengis.net/ont/geosparql#` for its `geo` prefix, so GeoSPARQL consumers should account for the hash-versus-slash difference when integrating generated JSON-LD.

## Core Types

| Type | schema.org Mapping | Purpose |
|------|-------------------|---------|
| `Link` | `schema:Link` | Web links with name, URL, description |
| `PropertyValue` | `schema:PropertyValue` | Flexible key-value pairs |
| `QuantitativeValue` | `qudt:QuantityValue` | Numeric values with units |
| `GeoShape` | `geo:Geometry` | GeoSPARQL-aligned geometries |
| `Feature` | `geo:Feature` | Spatial features with geometry |
| `Duration` | `xsd:duration` | ISO 8601 duration format |

In `core.linkml.yaml`, `Link` maps to `schema:Link`, `PropertyValue` to `schema:PropertyValue`, `QuantitativeValue` to `qudt:QuantityValue`, `GeoShape` to `geo:Geometry`, and `Feature` to `geo:Feature`. `Duration` uses `xsd:duration` and declares `schema:Duration` as an exact mapping.

## Slot URI Mappings

The common core slots use schema.org URIs:

| Property | URI | Used By |
|----------|-----|---------|
| `name` | `schema:name` | Core, CreditClass, Project |
| `description` | `schema:description` | Core, CreditClass, Project |
| `url` | `schema:url` | Core, CreditClass, Project |
| `same_as` | `schema:sameAs` | External identifier links |
| `main_entity_of_page` | `schema:mainEntityOfPage` | Primary web page |
| `potential_action` | `schema:potentialAction` | Potential action metadata |
| `alternate_name` | `schema:alternateName` | Alternate name |
| `projectStartDate` | `schema:startDate` | Project start date |
| `projectEndDate` | `schema:endDate` | Project end date |

Project and CreditClass also use Regen Framework mappings such as `rfs:hasFeature`, `rfs:hasPrimaryImpact`, `rfs:hasCoBenefits`, `rfs:hasProjectDeveloper`, `rfs:usesMethodology`, `rfs:hasSourceRegistry`, and `rfs:hasCreditProtocol`. `CreditBatch` and `ImpactClaim` currently define the schema.org prefix but their attributes do not carry schema.org `slot_uri` mappings.

Schema field naming is not globally uniform: core slots include snake_case names such as `same_as`, while project and credit schemas contain camelCase attributes such as `hasFeature` and `projectStartDate`. The JSON-LD helper preserves the keys supplied by the caller; it does not rename them.

## Schema Versions

| Schema | Version | Scope |
|---|---:|---|
| Core | `2.0.0` | Shared slots and core spatial/value types |
| Project | `3.0.0` | ProjectInfo-style farm/project metadata |
| CreditClass | `3.0.0` | Credit class and Regen crediting metadata |
| CreditBatch | `1.0.0` | Issuance batch metadata |
| ImpactClaim | `1.0.0` | Impact claim and evidence metadata |

## JSON-LD Context Generation

```python
from services.linkml.jsonld import generate_context, to_jsonld_document

# Generate context
context = generate_context("CreditClass")
# The schema name is currently informational; the helper returns the
# static default context unless caller-supplied slot_uris are provided.

# Create JSON-LD document
doc = to_jsonld_document(
    "CreditClass",
    {"name": "Kokonut Carbon", "methodology": "IPCC 2006"},
    iri="kokonut:credit_class:UUID:v1"
)
# Returns: {"@context": {...}, "@type": "kokonut:CreditClass", "@id": "kokonut:credit_class:UUID:v1", ...}

# Multi-entity @graph
from services.linkml.jsonld import to_jsonld_with_graph
doc = to_jsonld_with_graph([
    {"@type": "kokonut:CreditClass", "name": "Class A"},
    {"@type": "kokonut:Project", "name": "Project 1"},
])
# Returns: {"@context": {...}, "@graph": [...]}
```

`generate_context()` returns the default `schema`, `kokonut`, `rfs`, `qudt`, and `geo` mappings, then overlays any `slot_uris` passed by the caller. It does not parse the YAML files or emit per-slot term definitions.

`to_jsonld_document()` adds `@context`, a `kokonut:{entity_type}` `@type`, and an optional `@id`. It copies supplied entity fields as-is, excluding `id`, `created_at`, `updated_at`, `created_by`, `updated_by`, and `metadata`. It does not validate required fields, expand prefixed terms, infer `slot_uri` values, or publish the document.

`to_jsonld_with_graph()` copies the supplied entity dictionaries into `@graph`, preserving each supplied `@type` and field name. It does not create IDs, validate entity types, or resolve relationships.

For URI utility operations, `expand_prefixed_term()` expands a prefix using the active context and `compact_uri()` performs the inverse when a matching namespace is found.

## Validation Boundary

`services/linkml/validator.py` stores registered YAML schemas in `linkml_schema` and validation results in `linkml_schema_instance`. Its current `validate_instance()` implementation checks extracted required fields and records the result; it is not a complete LinkML validator for ranges, enums, URI expansion, slot mappings, or nested classes. JSON-LD generation and schema validation are separate operations.

## Schema Files

| File | Purpose |
|------|---------|
| `services/linkml/schemas/core.linkml.yaml` | Core types and properties |
| `services/linkml/schemas/credit_class.linkml.yaml` | Credit class schema |
| `services/linkml/schemas/project.linkml.yaml` | Project schema |
| `services/linkml/schemas/credit_batch.linkml.yaml` | Credit batch issuance metadata |
| `services/linkml/schemas/impact_claim.linkml.yaml` | Impact claim schema |

## Tests And Related Systems

- Schema and JSON-LD coverage: `tests/test_linked_data.py` (`TestSchemaOrgAlignment`)
- Schema registration/required-field validation: `services/linkml/validator.py`
- IRI generation and resolution: `services/iri/`
- RDF graph construction and evidence chains: `services/rdf/`
- Metadata graph resolution: `services/metadata_api/`

Schema.org alignment does not make a record public, verified, attested, or registry-eligible. Lifecycle, evidence, consent, and publication controls remain authoritative in PostgreSQL/Directus.
