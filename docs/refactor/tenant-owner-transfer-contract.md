# Tenant owner transfer contract

Updated: 14 October 2026.

This workflow changes Kokonut's verified organization tenant for one location.
It is an access and data-governance action. It does not establish or transfer
land title, a lease, an asset, a financial obligation, or an on-chain right.

## Approval and state

- An active tenant administrator of the currently verified owner requests a
  transfer to a different active organization. The request records a unique
  reference and a reason. A location with missing, stale, or conflicting
  ownership evidence cannot enter this workflow.
- A distinct, enabled tenant administrator of the target organization accepts
  with a separate decision reference. The original requester's source-side
  administrator membership must still be active when accepted.
- A pending request changes no ownership or access. The current owner can
  cancel it with a reason. Only one pending request may exist per location.
- Acceptance fails if the owner verification or owned-primary relationship set
  changed after the request. The owner must submit a new request after resolving
  the changed evidence.
- The database performs acceptance in one transaction. It closes the former
  owner relationship rows, creates corresponding active target-owner rows,
  changes the location's organization, revokes the previous owner verification,
  and creates a new verification linked to the transfer decision.
- Acceptance revokes every active location share and operator scope grant,
  including legacy NULL-tenant grants. The transfer record captures the IDs and
  independent acceptance actor. Access must be explicitly granted again under
  the new owner after review.
- Transfer request evidence is immutable. A transfer has one terminal state;
  accepted and cancelled records cannot be edited or deleted.
- Before acceptance, rollback is cancellation by a source-owner administrator.
  After acceptance, there is no automatic reversal: returning the location to
  the prior organization requires a new, independently approved transfer.

## Local operator commands

```text
python3 -m services.gateway.operator_cli tenant-transfer request \
  --location-id LOCATION_UUID \
  --target-organization-id ORGANIZATION_UUID \
  --requested-by-operator-id SOURCE_ADMIN_UUID \
  --request-reference CHANGE_OR_CASE_REFERENCE \
  --reason "Reviewed ownership transfer"

python3 -m services.gateway.operator_cli tenant-transfer accept \
  --transfer-id TRANSFER_UUID \
  --accepting-operator-id TARGET_ADMIN_UUID \
  --acceptance-reference APPROVAL_REFERENCE

python3 -m services.gateway.operator_cli tenant-transfer cancel \
  --transfer-id TRANSFER_UUID \
  --cancelling-operator-id SOURCE_ADMIN_UUID \
  --reason "Transfer request withdrawn"
```

`list` includes the request, acceptance/cancellation details, resulting owner
verification, and revoked grant/share IDs. The command records identifiers and
references, not attached evidence or private documents.

## Limits and rollout

Migration 390 is deployed to the local candidate after an encrypted database
checkpoint. The rollout applied migrations 387–390 in order; the ledger has
zero pending schemas and 120 pending seed files. The app alone was recreated;
the app and database are healthy, and anonymous protected routes return 401.
The candidate has no location records, so migration 387 created the canonical
Kokonut Network organization but no location ownership evidence. Five
mobile-form rows and ten revisions exist without applied seed history and must
be reconciled before any seed rollout.
See the [rollout evidence](builds/2026-10-14-recovery/candidate-tenant-transfer-rollout.json).

The workflow does not resolve unassigned/conflicted locations, determine who
may lawfully transfer land or farms, or change location-bound Field Collector
device enrollment. Old grants are revoked so pending mobile work cannot gain
new-owner authority implicitly; any subsequent access requires fresh grants.
RLS remains disabled until owner mappings, operator affiliations,
transaction-local context integration, worker scope, and downstream lineage
are resolved.
