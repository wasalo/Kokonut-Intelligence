# Kokonut Network location owner mapping

The repository owner confirmed that Kokonut Genesis, Kokonut Seeds, Kokonut
Adelphi, Kokonut Terra Viva, and Kokonut V1 use Kokonut Network as their
operating tenant. This is an organization/location access assignment; it does
not assert legal land title. No shared organization access was named, so the
reconciliation does not create shares or operator memberships.

## Source behavior

[`122_kokonut_network_operating_tenant_map.sql`](../../schemas/seeds/122_kokonut_network_operating_tenant_map.sql)
matches the five exact names and slugs. For a matching existing location, it
sets `location.organization_id`, establishes one active `owned` organization
relationship if none exists, and records the owner verification if no current
verification exists. It preserves already-confirmed Adelphi and Genesis rows.

The seed skips a named location until its source record exists. It does not
create placeholder farms, invent location UUIDs or geospatial values, or alter
unknown locations. It aborts transactionally if a name/slug conflicts, an
existing organization assignment differs, an active owner relationship
conflicts, or an old owner confirmation was revoked. Ownership transfers remain
on the audited transfer path.

## Applying after future imports

The pilot seed flow runs this reconciliation after migration 387, the pilot
location seeds, and owner verification. After later imports create any of the
three currently absent locations, rerun only this source through the ordered
checksummed seed runner:

```sh
python3 -m services.migration migrate \
  --only-migration seed:122_kokonut_network_operating_tenant_map.sql
```

No candidate or production database was changed for this implementation. The
disposable PostgreSQL acceptance covers absent locations, all five mapped
locations, idempotent replay, unknown-location preservation, identity mismatch
rollback, and conflicting-organization rollback
([evidence](builds/2026-10-16-recovery/network-location-owner-map-disposable.json)).
