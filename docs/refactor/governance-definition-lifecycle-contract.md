# Governance circle and role definition contract

**Status:** Prepared implementation, not an accepted capability. This contract
covers location-scoped circle and role creation, draft-only descriptive edits,
and separate governed lifecycle transitions. Accountabilities, authority
domains, policies, and role assignments remain separate capabilities.

## Authorization and mutation shape

Every mutation requires an authenticated OIDC operator, CSRF validation, signed
tenant context for the requested location, an active operator-to-person
binding, and a current exact `governance_roles:<action>` grant for that
location. Creation uses `:create`; editing uses `:update`.

Creation always creates a location-scoped `draft`. The caller cannot supply
lifecycle state, creator identity, metadata, or effective dates. Circle
parents and role circles must belong to the same location and be draft or
active. Circle hierarchy cycles are rejected. Existing circle/role definitions
can be edited only while their status is `draft`.

The allowed entity fields are deliberately narrow:

| Operation | Fields |
|---|---|
| Create circle | `circle_key`, `name`, `purpose`, optional `description`, optional `parent_circle_id` |
| Edit draft circle | `circle_key`, `name`, `purpose`, `description`, `parent_circle_id` |
| Create role | `circle_id`, `role_key`, `name`, `purpose` |
| Edit draft role | `role_key`, `name`, `purpose` |

Every create/edit body also requires `request_id` and a human-readable `reason`.
Unknown fields, lifecycle values, empty content, malformed identifiers, and
no-op edits are rejected. Same-operator retries with identical location,
entity, action, request content, and reason return the original result. Reusing
the request ID with different content is rejected.

## Lifecycle transitions

| Entity | Current status | Action and exact grant | Result |
|---|---|---|---|
| Circle | `draft` | `submit` | `submitted` |
| Circle | `draft`, `submitted` | `reject` | `rejected` |
| Circle | `submitted` | `activate` | `active` |
| Circle | `active` | `suspend` | `suspended` |
| Circle | `active`, `suspended` | `retire` | `retired` |
| Role | `draft` | `submit` | `submitted` |
| Role | `draft`, `submitted` | `reject` | `rejected` |
| Role | `submitted` | `approve` | `approved` |
| Role | `approved` | `activate` | `active` |
| Role | `active` | `suspend` | `suspended` |
| Role | `active`, `suspended` | `retire` | `retired` |

The reviewer or activator must be a different bound person from the definition
creator when a creator identity exists. A role can activate only in an active
circle. Proposed, active, or suspended assignments block role suspension and
retirement. Active or suspended circles can retire only after child roles are
retired or rejected. Assignment rows remain a separate lifecycle and are never
changed by these actions.

## Database boundary

Migration 442 adds `kokonut_security.transition_governance_definition` as the
only runtime path that may change definition status. It validates scope,
action, current state, identity, review separation, and linked authority
before changing the row. `governance_definition_action_event` records accepted
actions and is append-only. Status triggers reject direct runtime/Directus
status writes, including installations that still grant broad DML.

Migration 443 adds `kokonut_security.mutate_governance_definition` as the only
runtime path for creation and draft edits. It checks exact signed location
scope and the active person binding, validates same-location circle hierarchy,
forces new definitions to `draft`, and writes immutable request, actor,
before/after, and reason history in the same transaction. Runtime and Directus
roles lose direct insert/update/delete privileges on circle and role
definitions; mutation triggers reject bypass writes if legacy DML grants are
restored. Both private history tables are unreadable and immutable to runtime
and Directus roles.

Database superusers remain an administrative/bootstrap boundary and can bypass
the triggers. Production must use least-privilege service logins and restrict
migration/seed credentials.

## Routes

Creation and draft edits:

- `GET /operator/api/governance/{location_id}/circles/{circle_id}` (requires
  both exact `:read` and `:update`; reads one location-scoped circle's draft
  fields before editing, not an aggregate list)
- `POST /operator/api/governance/{location_id}/circles`
- `PATCH /operator/api/governance/{location_id}/circles/{circle_id}`
- `POST /operator/api/governance/{location_id}/roles`
- `PATCH /operator/api/governance/{location_id}/roles/{role_id}`

Lifecycle actions:

- `POST /operator/api/governance/{location_id}/circles/{circle_id}/submit`
- `POST /operator/api/governance/{location_id}/circles/{circle_id}/reject`
- `POST /operator/api/governance/{location_id}/circles/{circle_id}/activate`
- `POST /operator/api/governance/{location_id}/circles/{circle_id}/suspend`
- `POST /operator/api/governance/{location_id}/circles/{circle_id}/retire`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/submit`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/approve`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/reject`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/activate`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/suspend`
- `POST /operator/api/governance/{location_id}/roles/{role_id}/retire`

Malformed content returns 400, missing or out-of-scope definitions return 404,
missing grants or active person bindings return 403, and a non-draft edit or
unavailable lifecycle transition returns 409. Unknown route/action
combinations remain protected.

## Rollout and rollback

Disposable PostgreSQL 16 replay applies migrations 437–443 twice and checks
circle/role lifecycle actions, create/edit scope, draft-only state, parent and
circle location matching, request replay/collision, direct runtime/Directus
write denial, trigger protections, private append-only history, and ACLs.
The local candidate remains at migration 437 and still runs its application
with administrative `kokonut`; do not apply migrations 442–443 there until the
candidate uses its least-privilege runtime identity. Before rollout, revert the
Gateway and console mutation wiring if required. After applying migrations
442–443, retain the additive audit ledgers and guards; do not edit or reverse
ordered migrations. Populated production records, live OIDC, domain-table RLS,
and MAN-CAP-024 acceptance remain open.
