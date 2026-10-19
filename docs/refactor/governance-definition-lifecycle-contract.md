# Governance definition lifecycle contract

**Status:** Prepared implementation, not an accepted capability. This contract
covers status transitions for existing location-scoped governance circles and
role definitions. It does not create or edit their descriptive fields, manage
role assignments, or provide console controls.

## Authorization and request shape

Every route requires an authenticated OIDC operator, CSRF validation, signed
tenant context for the requested location, an active operator-to-person
binding, and a current exact `governance_roles:<action>` grant for that
location. The request body has exactly two fields:

```json
{
  "request_id": "UUID",
  "reason": "Human-readable transition rationale"
}
```

Each accepted transition and its append-only actor/reason ledger row commit in
one transaction. The same operator may retry the same request ID with
identical content to receive the original result. Reusing the request ID with
different location, entity, action, or reason is rejected.

## Supported transitions

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
actions and is append-only; runtime and Directus roles cannot read or mutate
it. Status triggers reject direct runtime/Directus status writes, including
installations that still grant broad DML. Database superusers remain an
administrative/bootstrap boundary and can bypass the trigger; production must
use least-privilege service logins and restrict migration/seed credentials.

## Routes

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
missing grants or active person bindings return 403, and an unavailable state
transition returns 409. Unknown route/action combinations remain protected.

## Rollout and rollback

Disposable PostgreSQL 16 replay applies migrations 437–442 twice and checks the
full circle/role lifecycle, independent review, request replay and collision,
direct runtime/Directus status-write denial, and private append-only history.
The local candidate remains at migration 437 and still runs its application
with administrative `kokonut`; do not apply migration 442 there until the
candidate uses its least-privilege runtime identity. Before rollout, revert the
Gateway module and route registration if required. After applying migration
442, retain the additive audit ledger and status triggers; do not edit or
reverse the ordered migration. Console lifecycle actions, circle/role
creation/edit parity, populated production records, live OIDC, and MAN-CAP-024
acceptance remain open.
