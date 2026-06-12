/**
 * Verification State Machine
 *
 * Manages status transitions for operational records.
 * Enforces valid state transitions, role-based approval routing,
 * and audit trail via workflow_history table.
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
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  sales_event: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  loss_event: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  labor_event: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  field_note: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  ai_summary: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  mrv_claim: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
  attestation_record: {
    draft: ['submitted'],
    submitted: ['verified', 'rejected'],
    verified: ['published'],
    rejected: ['draft'],
    published: [],
  },
};

// Role-based approval routing: which roles can perform which transitions
// Key = "collection:action", Value = array of allowed Directus role names
const ROLE_ROUTING: Record<string, string[]> = {
  'expense_event:verified': ['finance', 'admin'],
  'expense_event:rejected': ['finance', 'admin'],
  'expense_event:published': ['finance', 'admin'],
  'sales_event:verified': ['finance', 'admin'],
  'sales_event:rejected': ['finance', 'admin'],
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
};

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
  db?: any
): Promise<Record<string, unknown>> {
  const newStatus = payload.status as string | undefined;
  if (!newStatus) return payload;

  // Get current status from database if db is available, otherwise fall back to keys
  let currentStatus: string | undefined;
  if (db && keys.id) {
    try {
      const record = await db(collection).where('id', keys.id).first('status');
      currentStatus = record?.status as string | undefined;
    } catch (e) {
      // Fallback if query fails
      currentStatus = keys.status as string | undefined;
    }
  } else {
    currentStatus = keys.status as string | undefined;
  }

  if (!currentStatus) return payload;

  if (!isValidTransition(collection, currentStatus, newStatus)) {
    throw new Error(
      `Invalid status transition for ${collection}: ${currentStatus} → ${newStatus}. ` +
      `Valid transitions: ${VALID_TRANSITIONS[collection]?.[currentStatus]?.join(', ') || 'none'}`
    );
  }

  if (!isRoleAuthorized(collection, newStatus, userRoles)) {
    const key = `${collection}:${newStatus}`;
    const allowedRoles = ROLE_ROUTING[key]?.join(', ') || 'unknown';
    throw new Error(
      `Role not authorized for ${collection} → ${newStatus}. ` +
      `Required roles: ${allowedRoles}. Your roles: ${userRoles.join(', ') || 'none'}`
    );
  }

  const now = new Date().toISOString();

  // Auto-set timestamp fields
  const tsField = TIMESTAMP_FIELDS[newStatus];
  if (tsField) {
    payload[tsField] = now;
  }

  // Auto-set user fields from accountability (if provided via payload)
  const userField = USER_FIELDS[newStatus];
  const accountability = payload._accountability as Record<string, any> | undefined;
  if (userField && accountability?.user) {
    payload[userField] = accountability.user;
  }

  // Set rejection reason if provided
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
  ];

  const results: any[] = [];

  for (const collection of collections) {
    // Find records in submitted status
    let query = db(collection).where('status', 'submitted');

    if (locationId) {
      query = query.where('location_id', locationId);
    }

    const records = await query.select('id', 'location_id', 'created_at', 'status');

    for (const record of records) {
      // Check if any role can approve this
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
