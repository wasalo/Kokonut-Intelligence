# Phase 5 Source Of Truth

`kokonut-adelphi` is the canonical pilot identity: Kokonut Adelphi in Sabana
Grande de Boya, Monte Plata, Dominican Republic. The old Kisumu demo labels are
not valid pilot source data.

`raster_metadata` is owned by `059_drone_raster_integration.sql`. The similarly
named block in `115_geospatial_enhancement.sql` is an intentional compatibility
no-op for databases where the canonical table already exists. Migration `304`
asserts the canonical shape and preserves the existing raster ingestion API.

The legacy organization names in `024_adelphi_alignment.sql` are compatibility
aliases used only to reconcile old source labels. Seed `111_pilot_source_of_truth_cleanup.sql`
rewrites those labels on canonical Adelphi expense rows and is idempotent.

Public spatial views retain their established names, but migration `304` applies
the verified/published farm registry gate used by other public projections.
Directus metadata and permission field lists are also reconciled against actual
PostgreSQL columns when Directus is installed.
