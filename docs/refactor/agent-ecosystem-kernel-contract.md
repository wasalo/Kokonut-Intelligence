# Agent ecosystem Kernel contract

**Status:** first code-level safety slice prepared; MAN-CAP-038 remains open.

## Boundary

The Kernel agent boundary treats each registered task's `writes` declaration as
an executable capability contract. A task may declare only `collection:draft`
or `collection:submitted`; a task marked `high_risk` or a malformed, rejected,
verified, or published write target fails closed. Task definitions returned to
callers are deep copies, so mutating a CLI/API description cannot mutate the
in-process policy registry.

The shared synthesis runner, read-only runner, CIDS task, AI summary task, EBF
draft tasks, and Delphi facilitator validate this contract before any database
connection or task work begins. The catalogue validator also asks the common
agent safety policy whether each write is allowed.

Before processing, those same task entry points validate declared top-level
inputs from the task catalogue: required fields, primitive types, UUID formats,
and exact `YYYY-MM-DD` dates. Malformed IDs and dates fail before the shared or
standalone runner opens a database connection or initializes the Delphi
facilitator. This validates shape only; it does not authenticate the caller,
prove location membership, or authorize access to the referenced object.

The policy denies execution actions in `HIGH_RISK_ACTIONS`, including
`verify`, `publish`, `attest`, `onchain_submit`, `delete`, `bulk_update`, and
`financial_write`. `requires_human_approval` remains audit metadata; it does not
authorize an agent operation. Human review must happen through an independently
authorized workflow. No model/provider call or human-approval endpoint is added
by this slice.

Policy-only task listing and validation do not import the database-backed
action logger. Audit persistence is imported only when a caller explicitly
records an action, so the task catalogue and unified `agents list` command can
run without decrypting `.env.sops`.

## Existing safety behavior retained

- Draft creation continues for the write targets declared by the task catalogue.
- Shared synthesis runners validate the generated output before inserting a
  draft. The validator checks declared top-level presence, types, and UUID
  formats. Invalid output now fails before `INSERT`/`COMMIT`, and the connection
  still closes. Nested content is not schema-validated, and this does not
  replace the human review lifecycle.
- Shared synthesis, read-only, AI summary, CIDS, EBF, and Delphi entry points
  validate declared top-level task inputs before work begins. The validator
  checks required fields, primitive types, UUIDs, and exact ISO dates; it does
  not validate nested payloads or replace authentication and tenant grants.
- Existing output validation, EBF maturity limits, human-governed collection
  restrictions, and read behavior remain in place.
- Optional Directus hooks keep their role and lifecycle checks. The action-log
  hook marks `verify` as high risk so the audit surface remains aligned with
  Python.
- Migration 350 remains unchanged. Its trigger blocks selected status updates
  only when `app.agent_id` is set; that setting is not a database-authenticated
  identity, and inserts are not covered. It is not treated as a least-privilege
  agent boundary.

## Verification and limits

Focused source tests cover all current catalogue write declarations, defensive
copy behavior, denied high-risk actions, malformed policy input, and preflight
before database access. These checks do not establish Directus runtime-role
parity, authenticated agent identity, database table isolation, provider/model
behavior, populated task parity, or human approval workflow acceptance. Those
remain open gates for MAN-CAP-038.
