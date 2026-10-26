# Governance role assignment review contract

**Status:** implementation contract, not an approval of any individual
nomination. The candidate and production roles receive no grants from this
document.

## Lifecycle and authority

The existing `governance_role_assignment` lifecycle is `proposed → active` or
`proposed → rejected`. Creation remains nomination-only. A decision is a
separate human action by a signed-in OIDC operator with an active, explicit
operator-to-person binding. The reviewer must differ from the person who
submitted the nomination.

Location-scoped grants stay separate:

- `governance_roles:review` reads the pending queue, including the nominee and
  proposer identities and any delegate mandate needed for review.
- `governance_roles:approve` permits only an approval action.
- `governance_roles:reject` permits only a rejection action.

The grant is explicitly provisioned by an administrator; role authority is not
inferred from display names, role labels, profile fields, or a nominator's
proposal. Approval activates an assignment only when its role and circle are
active, the nominee is an active person, and the primary-assignment uniqueness
constraint remains satisfied. Rejection records a required reason but does not
set an approver or effective date. Both decisions append an immutable actor and
request record in the same transaction as the assignment state change.

## HTTP contract

- `GET /operator/api/governance/{location_id}/assignment-review-queue` requires
  `governance_roles:review`, signed tenant context, and bounded keyset paging.
- `POST /operator/api/governance/{location_id}/roles/{role_id}/assignments/{assignment_id}/approve`
  requires `governance_roles:approve` and exactly `decision_request_id` plus
  `reason` in its JSON body.
- The corresponding `/reject` route requires `governance_roles:reject` and the
  same body shape.

Both decision routes use OIDC session authentication, CSRF, no-store responses,
an active person binding, same-transaction signed location context, and an
idempotency UUID. The database function verifies that the proposal belongs to
the requested active location, remains proposed, was made by a different
person, and matches the authorized action. A repeated key with the same content
replays the recorded result; changing content or deciding an already-resolved
proposal conflicts. Direct table mutation remains denied to Gateway and
Directus runtime roles.

The review queue intentionally returns party identifiers, display names,
assignment type, mandate, role identifiers/labels, proposal request ID, and
creation time only to the separate review grant. It omits unrelated party data,
policy text, evidence payloads, and arbitrary metadata. The queue itself does
not mutate lifecycle state.

## Rollout boundary

Implement and verify with synthetic fixtures and disposable PostgreSQL. Do not
apply migrations to the candidate until the candidate stops using the
administrative `kokonut` connection and is configured with the least-privilege
runtime login. Do not provision operator bindings, grants, or approve/reject
real nominations as part of code acceptance. Capability status remains
prepared pending live OIDC, populated tenant parity, and explicit MAN-CAP-024
review.
