/**
 * Verification State Machine
 *
 * Manages status transitions for operational records.
 * Enforces valid state transitions, role-based approval routing,
 * and audit trail via workflow_history table.
 */

/** Standard governed lifecycle transitions. */
export const STANDARD_TRANSITIONS: Record<string, string[]> = {
  draft: ['submitted'],
  submitted: ['verified', 'rejected'],
  verified: ['published'],
  rejected: ['draft'],
  published: [],
};

/** All collections governed by lifecycle_status. */
export const LIFECYCLE_COLLECTIONS = [
  'farm_activity',
  'harvest_event',
  'expense_event',
  'sales_event',
  'loss_event',
  'labor_event',
  'field_note',
  'ai_summary',
  'mrv_claim',
  'attestation_record',
  'forecast_scenario',
  'report_snapshot',
  'dashboard_dataset',
  'farm_registry_record',
  'inventory_event',
  'maintenance_event',
  'revenue_event',
  'mrv_event',
  'attestation_request',
  'stakeholder_feedback',
  'stakeholder_outcome',
  'impact_claim',
] as const;

export type LifecycleCollection = (typeof LIFECYCLE_COLLECTIONS)[number];

// Valid status transitions per collection
const VALID_TRANSITIONS: Record<string, Record<string, string[]>> =
  Object.fromEntries(
    LIFECYCLE_COLLECTIONS.map((c) => [c, { ...STANDARD_TRANSITIONS }])
  );

// Role-based approval routing: which role slugs can perform which transitions
// Slugs are normalized from directus_roles.name (e.g. "Finance" → "finance")
const ROLE_ROUTING: Record<string, string[]> = {
  'expense_event:verified': ['finance', 'admin'],
  'expense_event:rejected': ['finance', 'admin'],
  'expense_event:published': ['finance', 'admin'],
  'sales_event:verified': ['finance', 'admin'],
  'sales_event:rejected': ['finance', 'admin'],
  'sales_event:published': ['finance', 'admin'],
  'revenue_event:verified': ['finance', 'admin'],
  'revenue_event:rejected': ['finance', 'admin'],
  'revenue_event:published': ['finance', 'admin'],
  'farm_activity:verified': ['manager', 'supervisor', 'admin'],
  'farm_activity:rejected': ['manager', 'supervisor', 'admin'],
  'harvest_event:verified': ['manager', 'supervisor', 'admin'],
  'harvest_event:rejected': ['manager', 'supervisor', 'admin'],
  'loss_event:verified': ['manager', 'supervisor', 'admin'],
  'loss_event:rejected': ['manager', 'supervisor', 'admin'],
  'labor_event:verified': ['manager', 'supervisor', 'admin'],
  'labor_event:rejected': ['manager', 'supervisor', 'admin'],
  'field_note:verified': ['manager', 'supervisor', 'admin'],
  'field_note:rejected': ['manager', 'supervisor', 'admin'],
  'mrv_claim:verified': ['manager', 'supervisor', 'admin'],
  'mrv_claim:rejected': ['manager', 'supervisor', 'admin'],
  'mrv_claim:published': ['manager', 'admin'],
  'mrv_event:verified': ['manager', 'supervisor', 'admin'],
  'mrv_event:rejected': ['manager', 'supervisor', 'admin'],
  'mrv_event:published': ['manager', 'admin'],
  'attestation_record:verified': ['manager', 'admin'],
  'attestation_record:rejected': ['manager', 'admin'],
  'attestation_record:published': ['admin'],
  'attestation_request:verified': ['manager', 'admin'],
  'attestation_request:rejected': ['manager', 'admin'],
  'attestation_request:published': ['admin'],
  'ai_summary:verified': ['manager', 'supervisor', 'admin'],
  'ai_summary:rejected': ['manager', 'supervisor', 'admin'],
  'forecast_scenario:verified': ['manager', 'analyst', 'admin'],
  'forecast_scenario:published': ['manager', 'admin'],
  'report_snapshot:verified': ['analyst', 'manager', 'admin'],
  'report_snapshot:published': ['manager', 'admin'],
  'farm_registry_record:verified': ['manager', 'admin'],
  'farm_registry_record:published': ['admin'],
  'inventory_event:verified': ['manager', 'supervisor', 'admin'],
  'inventory_event:rejected': ['manager', 'supervisor', 'admin'],
  'inventory_event:published': ['manager', 'admin'],
  'maintenance_event:verified': ['manager', 'supervisor', 'admin'],
  'maintenance_event:rejected': ['manager', 'supervisor', 'admin'],
  'maintenance_event:published': ['manager', 'admin'],
  'dashboard_dataset:verified': ['analyst', 'manager', 'admin'],
  'dashboard_dataset:published': ['manager', 'admin'],
  'stakeholder_feedback:verified': ['manager', 'supervisor', 'admin'],
  'stakeholder_feedback:rejected': ['manager', 'supervisor', 'admin'],
  'stakeholder_feedback:published': ['manager', 'admin'],
  'stakeholder_outcome:verified': ['manager', 'analyst', 'admin'],
  'stakeholder_outcome:rejected': ['manager', 'analyst', 'admin'],
  'stakeholder_outcome:published': ['manager', 'admin'],
  'impact_claim:verified': ['analyst', 'manager', 'admin'],
  'impact_claim:rejected': ['analyst', 'manager', 'admin'],
  'impact_claim:published': ['manager', 'admin'],
};

// Stash from_status between filter (pre-write) and action (post-write) hooks
const pendingTransitions = new Map<string, { fromStatus: string; expiresAt: number }>();

const PENDING_TRANSITION_TTL_MS = 30 * 60 * 1000; // 30 minutes
const PENDING_TRANSITION_MAX_SIZE = 1000;

function evictExpiredTransitions(): void {
  const now = Date.now();
  for (const [key, entry] of pendingTransitions) {
    if (now > entry.expiresAt) {
      pendingTransitions.delete(key);
    }
  }
  // If still over max size, delete oldest entries (Map preserves insertion order)
  if (pendingTransitions.size > PENDING_TRANSITION_MAX_SIZE) {
    const excess = pendingTransitions.size - PENDING_TRANSITION_MAX_SIZE;
    let deleted = 0;
    for (const key of pendingTransitions.keys()) {
      if (deleted >= excess) break;
      pendingTransitions.delete(key);
      deleted++;
    }
  }
}

// Fields to auto-set based on transition
const TIMESTAMP_FIELDS: Record<string, string> = {
  submitted: 'submitted_at',
  verified: 'verified_at',
};

const USER_FIELDS: Record<string, string> = {
  verified: 'verified_by',
  rejected: 'rejected_by',
  submitted: 'submitted_by',
};

function transitionKey(collection: string, recordId: string): string {
  return `${collection}:${recordId}`;
}

/** Stash the pre-update status for action-hook audit logging. */
export function stashPendingTransition(
  collection: string,
  recordId: string,
  fromStatus: string | undefined
): void {
  if (fromStatus) {
    evictExpiredTransitions();
    pendingTransitions.set(transitionKey(collection, recordId), {
      fromStatus,
      expiresAt: Date.now() + PENDING_TRANSITION_TTL_MS,
    });
  }
}

/** Consume the stashed from_status (returns undefined if none). */
export function consumePendingTransition(
  collection: string,
  recordId: string
): string | undefined {
  const key = transitionKey(collection, recordId);
  const entry = pendingTransitions.get(key);
  pendingTransitions.delete(key);
  return entry?.fromStatus;
}

/**
 * Validates that a status transition is allowed
 */
export function isValidTransition(
  collection: string,
  currentStatus: string,
  newStatus: string
): boolean {
  const transitions = VALID_TRANSITIONS[collection];
  if (!transitions) return true;

  const allowed = transitions[currentStatus];
  if (!allowed) return false;

  return allowed.includes(newStatus);
}

/**
 * Checks if the user's role is allowed to perform this transition
 */
export function isRoleAuthorized(
  collection: string,
  newStatus: string,
  userRoles: string[]
): boolean {
  const key = `${collection}:${newStatus}`;
  const allowedRoles = ROLE_ROUTING[key];
  if (!allowedRoles) return true; // No role restriction

  return userRoles.some((role) => allowedRoles.includes(role));
}

/**
 * Handles workflow transition validation
 * Called from filter hooks to block invalid transitions
 */
export async function handleWorkflowTransition(
  collection: string,
  payload: Record<string, unknown>,
  keys: Record<string, unknown>,
  userRoles: string[] = [],
  db?: any,
  accountability?: Record<string, any>
): Promise<Record<string, unknown>> {
  const newStatus = payload.status as string | undefined;
  if (!newStatus) return payload;

  const recordId = (keys.id ?? keys[0]) as string | undefined;

  // Get current status from database if db is available, otherwise fall back to keys
  let currentStatus: string | undefined;
  if (db && recordId) {
    try {
      const record = await db(collection).where('id', recordId).first('status');
      currentStatus = record?.status as string | undefined;
    } catch (e) {
      currentStatus = keys.status as string | undefined;
    }
  } else {
    currentStatus = keys.status as string | undefined;
  }

  if (!currentStatus) return payload;

  if (recordId) {
    stashPendingTransition(collection, recordId, currentStatus);
  }

  if (!isValidTransition(collection, currentStatus, newStatus)) {
    if (recordId) pendingTransitions.delete(transitionKey(collection, recordId));
    throw new Error(
      `Invalid status transition for ${collection}: ${currentStatus} → ${newStatus}. ` +
      `Valid transitions: ${VALID_TRANSITIONS[collection]?.[currentStatus]?.join(', ') || 'none'}`
    );
  }

  if (!isRoleAuthorized(collection, newStatus, userRoles)) {
    if (recordId) pendingTransitions.delete(transitionKey(collection, recordId));
    const key = `${collection}:${newStatus}`;
    const allowedRoles = ROLE_ROUTING[key]?.join(', ') || 'unknown';
    throw new Error(
      `Role not authorized for ${collection} → ${newStatus}. ` +
      `Required roles: ${allowedRoles}. Your roles: ${userRoles.join(', ') || 'none'}`
    );
  }

  // Enforce 7-day review period for stakeholder feedback
  if (collection === 'stakeholder_feedback' && newStatus === 'verified' && db && recordId) {
    try {
      const record = await db(collection).where('id', recordId).first('submitted_at');
      if (record?.submitted_at) {
        const submittedAt = new Date(record.submitted_at);
        const nowDate = new Date();
        const diffDays = Math.floor((nowDate.getTime() - submittedAt.getTime()) / (1000 * 60 * 60 * 24));
        if (diffDays < 7) {
          pendingTransitions.delete(transitionKey(collection, recordId));
          throw new Error(
            `Stakeholder feedback must be in submitted status for at least 7 days before verification. ` +
            `Submitted: ${record.submitted_at}, days elapsed: ${diffDays}`
          );
        }
      }
    } catch (e) {
      if (e instanceof Error && e.message.includes('7 days')) {
        throw e;
      }
      // If we can't check, allow the transition (graceful degradation)
    }
  }

  const now = new Date().toISOString();

  const tsField = TIMESTAMP_FIELDS[newStatus];
  if (tsField) {
    payload[tsField] = now;
  }

  const userField = USER_FIELDS[newStatus];
  if (userField && accountability?.user) {
    payload[userField] = accountability.user;
  }

  if (newStatus === 'rejected' && payload.rejection_reason) {
    payload.rejection_reason = payload.rejection_reason;
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

/**
 * Get valid next statuses filtered by user role
 */
export function getValidNextStatusesForRole(
  collection: string,
  currentStatus: string,
  userRoles: string[]
): string[] {
  const all = getValidNextStatuses(collection, currentStatus);
  return all.filter((status) => isRoleAuthorized(collection, status, userRoles));
}

/**
 * Log a workflow transition to workflow_history table
 */
export async function logWorkflowTransition(
  db: any,
  collection: string,
  recordId: string,
  fromStatus: string | undefined,
  toStatus: string,
  userId: string | undefined,
  notes?: string,
  rejectionReason?: string
): Promise<void> {
  await db('workflow_history').insert({
    collection,
    record_id: recordId,
    from_status: fromStatus || null,
    to_status: toStatus,
    changed_by: userId || null,
    notes: notes || null,
    rejection_reason: rejectionReason || null,
  });
}

/**
 * Get pending approval queue for a given role
 */
export async function getApprovalQueue(
  db: any,
  userRoles: string[],
  locationId?: string
): Promise<any[]> {
  const collections = [
    'farm_activity', 'harvest_event', 'expense_event',
    'sales_event', 'loss_event', 'labor_event', 'field_note',
    'mrv_claim', 'attestation_record', 'attestation_request', 'mrv_event',
  ];

  const results: any[] = [];

  for (const collection of collections) {
    let query = db(collection).where('status', 'submitted');

    if (locationId) {
      query = query.where('location_id', locationId);
    }

    const records = await query.select('id', 'location_id', 'created_at', 'status');

    for (const record of records) {
      const canApprove = getValidNextStatusesForRole(collection, 'submitted', userRoles);
      if (canApprove.length > 0) {
        results.push({
          collection,
          record_id: record.id,
          location_id: record.location_id,
          submitted_at: record.created_at,
          status: 'submitted',
        });
      }
    }
  }

  return results;
}
