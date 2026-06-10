/**
 * Verification State Machine
 *
 * Manages status transitions for operational records.
 * Enforces valid state transitions and audit trail.
 */

// Valid status transitions per collection
const VALID_TRANSITIONS: Record<string, Record<string, string[]>> = {
  farm_activity: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  harvest_event: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  expense_event: {
    draft: ['submitted'],
    submitted: ['approved', 'rejected'],
    approved: ['paid'],
    rejected: ['draft'],
    paid: [],
  },
  sales_event: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  mrv_claim: {
    draft: ['submitted'],
    submitted: ['under_review'],
    under_review: ['approved', 'rejected'],
    approved: ['attested'],
    rejected: ['draft'],
    attested: [],
  },
  attestation_record: {
    draft: ['submitted'],
    submitted: ['approved', 'rejected'],
    approved: ['attested'],
    rejected: ['draft'],
    attested: [],
    revoked: [],
  },
};

/**
 * Validates that a status transition is allowed
 */
export function isValidTransition(
  collection: string,
  currentStatus: string,
  newStatus: string
): boolean {
  const transitions = VALID_TRANSITIONS[collection];
  if (!transitions) return true; // No transition rules defined, allow all

  const allowed = transitions[currentStatus];
  if (!allowed) return false;

  return allowed.includes(newStatus);
}

/**
 * Handles workflow transition validation
 * Called from filter hooks to block invalid transitions
 */
export function handleWorkflowTransition(
  collection: string,
  payload: Record<string, unknown>,
  keys: Record<string, unknown>
): Record<string, unknown> {
  const newStatus = payload.status as string | undefined;
  if (!newStatus) return payload;

  const currentStatus = keys.status as string | undefined;
  if (!currentStatus) return payload;

  if (!isValidTransition(collection, currentStatus, newStatus)) {
    throw new Error(
      `Invalid status transition for ${collection}: ${currentStatus} → ${newStatus}. ` +
      `Valid transitions: ${VALID_TRANSITIONS[collection]?.[currentStatus]?.join(', ') || 'none'}`
    );
  }

  // Set timestamp based on transition
  const now = new Date().toISOString();
  if (newStatus === 'verified' || newStatus === 'approved') {
    payload.verified_at = now;
  }
  if (newStatus === 'submitted') {
    payload.submitted_at = now;
  }

  return payload;
}

/**
 * Get all valid next statuses for a given collection and current status
 */
export function getValidNextStatuses(
  collection: string,
  currentStatus: string
): string[] {
  const transitions = VALID_TRANSITIONS[collection];
  if (!transitions) return [];

  return transitions[currentStatus] || [];
}
