# Schema.org Alignment

## Overview

All LinkML schemas in the Kokonut Intelligence platform are aligned with schema.org V30.0 standards via `slot_uri` mappings.

## Core Types

| Type | schema.org Mapping | Purpose |
|------|-------------------|---------|
| `Link` | `schema:Link` | Web links with name, URL, description |
| `PropertyValue` | `schema:PropertyValue` | Flexible key-value pairs |
| `QuantitativeValue` | `qudt:QuantityValue` | Numeric values with units |
| `GeoShape` | `geo:Geometry` | GeoSPARQL-aligned geometries |
| `Feature` | `geo:Feature` | Spatial features with geometry |
| `Duration` | `xsd:duration` | ISO 8601 duration format |

## Slot URI Mappings

All core properties use schema.org URIs:

| Property | URI | Used By |
|----------|-----|---------|
| `name` | `schema:name` | CreditClass, Project, all entities |
| `description` | `schema:description` | CreditClass, Project, all entities |
| `url` | `schema:url` | CreditClass, Project, all entities |
| `sameAs` | `schema:sameAs` | External identifier links |
| `mainEntityOfPage` | `schema:mainEntityOfPage` | Primary web page |
| `startDate` | `schema:startDate` | Project start date |
| `endDate` | `schema:endDate` | Project end date |

## JSON-LD Context Generation

```python
from services.linkml.jsonld import generate_context, to_jsonld_document

# Generate context
context = generate_context("CreditClass")

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

## Schema Files

| File | Purpose |
|------|---------|
| `services/linkml/schemas/core.linkml.yaml` | Core types and properties |
| `services/linkml/schemas/credit_class.linkml.yaml` | Credit class schema |
| `services/linkml/schemas/project.linkml.yaml` | Project schema |
| `services/linkml/schemas/impact_claim.linkml.yaml` | Impact claim schema |
