import { defineHook } from '@directus/extensions-sdk';
import { calculateNoi, batchCalculateNoi, storeNoiSnapshot, setDb } from './metrics-calculator.js';
import {
  handleWorkflowTransition,
  logWorkflowTransition,
  consumePendingTransition,
  LIFECYCLE_COLLECTIONS,
} from './workflow.js';
import { resolveUserRoles } from './roles.js';
import {
  autoCategorizeExpense,
  validateExpenseAmount,
  validateSalesAmount,
  validateHarvestQuantity,
  autoCalculateLossValue,
  calculateNetAmount,
  calculateLaborCost,
  validateNotFutureDate,
  validateExpenseDate,
  autoSummarizeFieldNote,
} from './ai-helpers.js';
import {
  validateEvidenceUrls,
  validateFieldNoteImages,
} from './evidence-helpers.js';
import {
  normalizeFeedbackPayload,
  validateStakeholderFeedback,
  recordFeedbackReview,
} from './feedback.js';
import {
  handleMetricProposalUpdate,
  logMetricProposalTransition,
} from './metric-proposal.js';
import {
  normalizeImpactClaimPayload,
  validateImpactClaim,
  stampImpactClaimReview,
} from './impact-claim.js';
import {
  enforceAgentTaskSafety,
  enforceAiSummarySafety,
  enforceStakeholderGovernanceSafety,
  prepareAgentActionLog,
  STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS,
} from './agent-safety.js';
import {
  validateTenantReferences,
  validateTenantReferencesForRows,
} from './tenant-validation.js';
import { errorClass } from './error-safety.js';
import {
  authorizeDirectusCreate,
  authorizeDirectusFeedbackReviewCreate,
  authorizeDirectusRead,
  authorizeDirectusReadResult,
  authorizeDirectusRows,
  createDirectusTenantStore,
  requireDirectusRequestDatabase,
  TENANT_SCOPED_COLLECTIONS,
} from './directus-authorization.js';
import { z } from 'zod';
import {
  validateAgentTaskCreate,
  validateAgentTaskUpdate,
  validateAiSummaryCreate,
  validateAiSummaryUpdate,
  validateAgentActionLogCreate,
  validateImpactClaimCreate,
  validateImpactClaimUpdate,
  validateStakeholderFeedbackCreate,
  validateStakeholderFeedbackUpdate,
  validateExpenseEventCreate,
  validateExpenseEventUpdate,
  validateSalesEventCreate,
  validateSalesEventUpdate,
  validateRevenueEventCreate,
  validateRevenueEventUpdate,
  formatZodError,
} from './schemas/index.js';

/** Run Zod validation and rethrow as a sanitized hook error. */
function parseOrThrow(validate: (p: Record<string, any>) => Record<string, any>, payload: Record<string, any>): Record<string, any> {
  try {
    return validate(payload);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new Error(formatZodError(error));
    }
    throw error;
  }
}

/** Tenant-scoped hook queries must use Directus's request transaction. */
export function resolveHookDatabase(
  collection: string,
  context: Record<string, any> | null | undefined,
  extensionDatabase: any,
): any {
  if ((TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection)) {
    return requireDirectusRequestDatabase(context?.database);
  }
  return context?.database || extensionDatabase;
}

/** Collections with only workflow enforcement (no create-time validation). */
const WORKFLOW_ONLY_COLLECTIONS = LIFECYCLE_COLLECTIONS.filter(
  (c) =>
    ![
      'farm_activity',
      'harvest_event',
      'expense_event',
      'sales_event',
      'loss_event',
      'labor_event',
      'field_note',
      'ai_summary',
      'stakeholder_feedback',
      'impact_claim',
    ].includes(c)
);

function isExplicitlyEnabled(value: unknown): boolean {
  return value === true || (typeof value === 'string' && value.trim().toLowerCase() === 'true');
}

export default defineHook(({ filter, action, schedule }, { database, env }) => {
  setDb(database);

  for (const collection of TENANT_SCOPED_COLLECTIONS) {
    filter(`${collection}.items.query`, async (
      query: Record<string, any>,
      _meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      const requestDatabase = requireDirectusRequestDatabase(context?.database);
      return await authorizeDirectusRead(
        createDirectusTenantStore(requestDatabase),
        context?.accountability,
        env.KOKONUT_OPERATOR_OIDC_ISSUER,
        collection,
        query,
      );
    });

    filter(`${collection}.items.read`, async (
      items: unknown,
      _meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      return await authorizeDirectusReadResult(
        createDirectusTenantStore(requireDirectusRequestDatabase(context?.database)),
        context?.accountability,
        env.KOKONUT_OPERATOR_OIDC_ISSUER,
        collection,
        items,
      );
    });

    filter(`${collection}.items.create`, async (
      payload: Record<string, any>,
      _meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      const requestDatabase = requireDirectusRequestDatabase(context?.database);
      const tenantStore = createDirectusTenantStore(requestDatabase);
      await authorizeDirectusCreate(
        tenantStore,
        context?.accountability,
        env.KOKONUT_OPERATOR_OIDC_ISSUER,
        collection,
        payload,
      );
      return await validateTenantReferences(requestDatabase, collection, payload);
    });

    filter(`${collection}.items.update`, async (
      payload: Record<string, any>,
      meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      const requestDatabase = requireDirectusRequestDatabase(context?.database);
      const authorizedRows = await authorizeDirectusRows(
        createDirectusTenantStore(requestDatabase),
        context?.accountability,
        env.KOKONUT_OPERATOR_OIDC_ISSUER,
        collection,
        'update',
        meta?.keys,
        payload,
      );
      await validateTenantReferencesForRows(
        requestDatabase,
        collection,
        payload,
        authorizedRows,
      );
      return payload;
    });

    filter(`${collection}.items.delete`, async (
      keys: string[] | string,
      _meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      await authorizeDirectusRows(
        createDirectusTenantStore(requireDirectusRequestDatabase(context?.database)),
        context?.accountability,
        env.KOKONUT_OPERATOR_OIDC_ISSUER,
        collection,
        'delete',
        keys,
      );
      return keys;
    });
  }

  // Review rows have no location_id; bind their create action to the exact
  // parent feedback location and require the child collection's scoped grant.
  filter('stakeholder_feedback_review.items.create', async (
    payload: Record<string, any>,
    _meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const requestDatabase = requireDirectusRequestDatabase(context?.database);
    const locationId = await authorizeDirectusFeedbackReviewCreate(
      createDirectusTenantStore(requestDatabase),
      context?.accountability,
      env.KOKONUT_OPERATOR_OIDC_ISSUER,
      payload,
    );
    await validateTenantReferences(requestDatabase, 'stakeholder_feedback', {
      location_id: locationId,
      reviewer_id: payload.reviewer_id,
    });
    return payload;
  });

  function getUserId(meta: Record<string, any>): string | undefined {
    const accountability = meta?.accountability;
    return accountability?.user;
  }

  async function logTransition(
    collection: string,
    recordId: string,
    toStatus: string,
    userId: string | undefined,
    meta: Record<string, any>
  ) {
    try {
      const fromStatus = consumePendingTransition(collection, recordId);
      const notes = meta?.payload?.rejection_reason || undefined;
      await logWorkflowTransition(
        database, collection, recordId, fromStatus, toStatus, userId, undefined, notes
      );
    } catch (error) {
      console.error(`[Kokonut] Failed to log workflow transition for ${collection}: ${errorClass(error)}`);
    }
  }

  async function applyWorkflow(
    collection: string,
    payload: Record<string, any>,
    meta: Record<string, any>,
    requestDatabase: any = database,
  ) {
    const userRoles = await resolveUserRoles(requestDatabase, meta);
    const accountability = meta?.accountability;
    return await handleWorkflowTransition(
      collection,
      payload,
      meta.keys || {},
      userRoles,
      requestDatabase,
      accountability,
      (TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection) &&
        collection !== 'metric_proposal',
    );
  }

  // Register workflow-only filter hooks
  for (const collection of WORKFLOW_ONLY_COLLECTIONS) {
    filter(`${collection}.items.update`, async (
      payload: Record<string, any>,
      meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      return await applyWorkflow(collection, payload, meta, resolveHookDatabase(collection, context, database));
    });
  }

  // Data-stream records always enter the governed lifecycle as drafts. Their
  // status can only advance through the standard role-gated workflow.
  for (const collection of ['data_stream_post', 'data_stream_post_comment', 'data_stream_file']) {
    filter(`${collection}.items.create`, (payload: Record<string, any>) => {
      if (payload.status && payload.status !== 'draft') {
        delete payload.status;
      }
      return payload;
    });
    filter(`${collection}.items.update`, async (
      payload: Record<string, any>,
      meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      return await applyWorkflow(collection, payload, meta, resolveHookDatabase(collection, context, database));
    });
  }

  // ============================================================
  // Filter hooks (blocking - run before DB write)
  // ============================================================

  filter('expense_event.items.create', (payload: Record<string, any>) => {
    const validated = parseOrThrow(validateExpenseEventCreate, payload);
    autoCategorizeExpense(validated);

    if (validated.amount !== undefined) {
      const errors = validateExpenseAmount(validated.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    if (validated.expense_date) {
      const dateError = validateExpenseDate(validated.expense_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (validated.evidence_urls) {
      const errors = validateEvidenceUrls(validated.evidence_urls);
      if (errors.length > 0) {
        throw new Error(`Evidence validation: ${errors.join('; ')}`);
      }
    }

    return validated;
  });

  filter('expense_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateExpenseEventUpdate, payload);
    // Re-run auto-categorization if category was cleared
    if (!validated.category || validated.category === '') {
      autoCategorizeExpense(validated);
    }

    if (validated.amount !== undefined) {
      const errors = validateExpenseAmount(validated.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    return await applyWorkflow(
      'expense_event', validated, meta, resolveHookDatabase('expense_event', context, database),
    );
  });

  filter('sales_event.items.create', (payload: Record<string, any>) => {
    const validated = parseOrThrow(validateSalesEventCreate, payload);
    if (validated.total_amount !== undefined) {
      validated.net_amount = calculateNetAmount(
        validated.total_amount || 0,
        validated.return_amount || 0,
        validated.discount_amount || 0
      );
    }

    if (validated.total_amount !== undefined) {
      const errors = validateSalesAmount(validated.total_amount);
      if (errors.length > 0) {
        throw new Error(`Sales validation: ${errors.join('; ')}`);
      }
    }

    if (validated.sale_date) {
      const dateError = validateNotFutureDate(validated.sale_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (validated.evidence_urls) {
      const errors = validateEvidenceUrls(validated.evidence_urls);
      if (errors.length > 0) {
        throw new Error(`Evidence validation: ${errors.join('; ')}`);
      }
    }

    return validated;
  });

  filter('sales_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const requestDatabase = resolveHookDatabase('sales_event', context, database);
    const validated = parseOrThrow(validateSalesEventUpdate, payload);
    const recordId = meta.keys?.[0];
    if (recordId && (validated.total_amount !== undefined || validated.return_amount !== undefined || validated.discount_amount !== undefined)) {
      const current = await requestDatabase('sales_event')
        .where('id', recordId)
        .first();

      const total = validated.total_amount ?? current?.total_amount ?? 0;
      const returns = validated.return_amount ?? current?.return_amount ?? 0;
      const discount = validated.discount_amount ?? current?.discount_amount ?? 0;
      validated.net_amount = calculateNetAmount(total, returns, discount);
    }

    return await applyWorkflow('sales_event', validated, meta, requestDatabase);
  });

  filter('harvest_event.items.create', (payload: Record<string, any>) => {
    if (payload.loss_amount && !payload.loss_estimated_value) {
      const estimated = autoCalculateLossValue(
        payload.loss_amount,
        payload.loss_unit,
        payload.quantity,
        payload.total_amount
      );
      if (estimated !== undefined) {
        payload.loss_estimated_value = estimated;
      }
    }

    if (payload.quantity !== undefined) {
      const warnings = validateHarvestQuantity(payload.quantity, payload.expected_yield);
      if (warnings.length > 0) {
        console.log(`[Kokonut] Harvest warnings: ${warnings.join('; ')}`);
      }
    }

    if (payload.harvest_date) {
      const dateError = validateNotFutureDate(payload.harvest_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (payload.evidence_urls) {
      const errors = validateEvidenceUrls(payload.evidence_urls);
      if (errors.length > 0) {
        throw new Error(`Evidence validation: ${errors.join('; ')}`);
      }
    }

    return payload;
  });

  filter('harvest_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await applyWorkflow('harvest_event', payload, meta, resolveHookDatabase('harvest_event', context, database));
  });

  filter('farm_activity.items.create', (payload: Record<string, any>) => {
    if (payload.activity_date) {
      const dateError = validateNotFutureDate(payload.activity_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (payload.labor_hours && payload.hourly_rate && !payload.labor_cost) {
      payload.labor_cost = calculateLaborCost(payload.labor_hours, payload.hourly_rate);
    }

    return payload;
  });

  filter('farm_activity.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await applyWorkflow('farm_activity', payload, meta, resolveHookDatabase('farm_activity', context, database));
  });

  filter('loss_event.items.create', (payload: Record<string, any>) => {
    if (payload.loss_date) {
      const dateError = validateNotFutureDate(payload.loss_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (payload.evidence_urls) {
      const errors = validateEvidenceUrls(payload.evidence_urls);
      if (errors.length > 0) {
        throw new Error(`Evidence validation: ${errors.join('; ')}`);
      }
    }

    return payload;
  });

  filter('loss_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await applyWorkflow('loss_event', payload, meta, resolveHookDatabase('loss_event', context, database));
  });

  filter('labor_event.items.create', (payload: Record<string, any>) => {
    if (payload.hours_worked && payload.hourly_rate && !payload.total_cost) {
      payload.total_cost = calculateLaborCost(payload.hours_worked, payload.hourly_rate);
    }

    if (payload.work_date) {
      const dateError = validateNotFutureDate(payload.work_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    return payload;
  });

  filter('labor_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await applyWorkflow('labor_event', payload, meta, resolveHookDatabase('labor_event', context, database));
  });

  filter('field_note.items.create', (payload: Record<string, any>) => {
    autoSummarizeFieldNote(payload);

    if (payload.note_date) {
      const dateError = validateNotFutureDate(payload.note_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    if (payload.images) {
      const errors = validateFieldNoteImages(payload.images);
      if (errors.length > 0) {
        throw new Error(`Image validation: ${errors.join('; ')}`);
      }
    }

    return payload;
  });

  filter('field_note.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await applyWorkflow('field_note', payload, meta, resolveHookDatabase('field_note', context, database));
  });

  filter('stakeholder_feedback.items.create', (payload: Record<string, any>) => {
    normalizeFeedbackPayload(payload);
    validateStakeholderFeedback(payload);
    return parseOrThrow(validateStakeholderFeedbackCreate, payload);
  });

  filter('stakeholder_feedback.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const requestDatabase = resolveHookDatabase('stakeholder_feedback', context, database);
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const current = recordId
      ? await requestDatabase('stakeholder_feedback').where('id', recordId).first()
      : {};
    validateStakeholderFeedback({ ...(current || {}), ...payload });
    const validated = parseOrThrow(validateStakeholderFeedbackUpdate, payload);
    const workflowPayload = await applyWorkflow(
      'stakeholder_feedback', validated, meta, requestDatabase,
    );
    if (recordId && (validated.status === 'published' || validated.status === 'rejected')) {
      try {
        await recordFeedbackReview(requestDatabase, {
          feedbackId: recordId,
          action: validated.status === 'published' ? 'published_summary' : 'dismissed',
          responseText: validated.status === 'published'
            ? 'Public summary published.'
            : validated.rejection_reason,
          actorDirectusUserId: getUserId(meta),
        });
      } catch (error) {
        consumePendingTransition('stakeholder_feedback', recordId);
        throw error;
      }
    }
    return workflowPayload;
  });

  filter('metric_proposal.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    return await handleMetricProposalUpdate(payload, meta, resolveHookDatabase('metric_proposal', context, database));
  });

  filter('impact_claim.items.create', (payload: Record<string, any>) => {
    normalizeImpactClaimPayload(payload);
    validateImpactClaim(payload);
    return parseOrThrow(validateImpactClaimCreate, payload);
  });

  filter('impact_claim.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const requestDatabase = resolveHookDatabase('impact_claim', context, database);
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const current = recordId
      ? await requestDatabase('impact_claim').where('id', recordId).first()
      : {};
    validateImpactClaim({ ...(current || {}), ...payload });
    const validated = parseOrThrow(validateImpactClaimUpdate, payload);
    await stampImpactClaimReview(validated);
    return await applyWorkflow('impact_claim', validated, meta, requestDatabase);
  });

  filter('agent_task.items.create', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateAgentTaskCreate, payload);
    const roles = await resolveUserRoles(resolveHookDatabase('agent_task', context, database), meta);
    return enforceAgentTaskSafety(validated, roles);
  });
  filter('agent_task.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateAgentTaskUpdate, payload);
    const roles = await resolveUserRoles(resolveHookDatabase('agent_task', context, database), meta);
    return enforceAgentTaskSafety(validated, roles);
  });
  filter('ai_summary.items.create', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateAiSummaryCreate, payload);
    const roles = await resolveUserRoles(resolveHookDatabase('ai_summary', context, database), meta);
    return enforceAiSummarySafety(validated, roles);
  });
  filter('ai_summary.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateAiSummaryUpdate, payload);
    const requestDatabase = resolveHookDatabase('ai_summary', context, database);
    const roles = await resolveUserRoles(requestDatabase, meta);
    enforceAiSummarySafety(validated, roles);
    return await applyWorkflow('ai_summary', validated, meta, requestDatabase);
  });
  filter('agent_action_log.items.create', (payload: Record<string, any>) => prepareAgentActionLog(parseOrThrow(validateAgentActionLogCreate, payload)));

  filter('revenue_event.items.create', (payload: Record<string, any>) => {
    return parseOrThrow(validateRevenueEventCreate, payload);
  });
  filter('revenue_event.items.update', async (
    payload: Record<string, any>,
    meta: Record<string, any>,
    context: Record<string, any>,
  ) => {
    const validated = parseOrThrow(validateRevenueEventUpdate, payload);
    return await applyWorkflow(
      'revenue_event', validated, meta, resolveHookDatabase('revenue_event', context, database),
    );
  });

  for (const collection of STAKEHOLDER_HUMAN_REVIEW_COLLECTIONS) {
    filter(`${collection}.items.create`, async (
      payload: Record<string, any>,
      meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      const roles = await resolveUserRoles(resolveHookDatabase(collection, context, database), meta);
      return enforceStakeholderGovernanceSafety(collection, payload, roles);
    });
    filter(`${collection}.items.update`, async (
      payload: Record<string, any>,
      meta: Record<string, any>,
      context: Record<string, any>,
    ) => {
      const roles = await resolveUserRoles(resolveHookDatabase(collection, context, database), meta);
      return enforceStakeholderGovernanceSafety(collection, payload, roles);
    });
  }

  // ============================================================
  // Action hooks (non-blocking - run after DB write)
  // ============================================================

  for (const collection of LIFECYCLE_COLLECTIONS) {
    // Tenant-scoped lifecycle filters write workflow_history in the same
    // Directus request transaction as the item update. Do not write a second,
    // best-effort copy through the extension-global connection afterward.
    if ((TENANT_SCOPED_COLLECTIONS as readonly string[]).includes(collection)) {
      continue;
    }
    action(`${collection}.items.update`, async (meta: Record<string, any>) => {
      const newStatus = meta?.payload?.status;
      const recordId = meta.keys?.[0] ?? meta.keys?.id;
      if (newStatus && recordId) {
        const userId = getUserId(meta);
        await logTransition(collection, recordId, newStatus, userId, meta);
      }
    });
  }

  action('metric_proposal.items.update', async (meta: Record<string, any>) => {
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const status = meta?.payload?.status;
    if (!recordId || !status) return;
    await logMetricProposalTransition(
      database,
      recordId,
      status,
      getUserId(meta),
      meta?.payload?.discussion_notes ? JSON.stringify(meta.payload.discussion_notes) : undefined
    );
  });

  action('harvest_event.items.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
  });

  // sales_event and expense_event financial mirrors are captured atomically
  // by PostgreSQL migration 434 and delivered by the optional outbox worker.
  action('sales_event.items.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('expense_event.items.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    if (payload.crop_cycle_id) {
      await recalculateNoi(payload.crop_cycle_id);
    }
  });

  // ============================================================
  // Scheduled hooks
  // ============================================================

  if (isExplicitlyEnabled(env?.KOKONUT_DIRECTUS_SCHEDULE_NOI_RECONCILIATION)) {
    schedule('0 2 * * *', async () => {
      console.log('[Kokonut] Running daily NOI reconciliation...');
      try {
        const result = await batchCalculateNoi();
        if (result.failed > 0) {
          console.error(
            `[Kokonut] NOI reconciliation completed with partial failures: succeeded=${result.succeeded} failed=${result.failed}`
          );
        } else {
          console.log(
            `[Kokonut] NOI reconciliation completed: succeeded=${result.succeeded} failed=0`
          );
        }
      } catch (error) {
        console.error(`[Kokonut] NOI reconciliation failed: ${errorClass(error)}`);
      }
    });
  }

  if (isExplicitlyEnabled(env?.KOKONUT_DIRECTUS_SCHEDULE_WEEKLY_ACTIVITY_AGGREGATION)) {
    schedule('0 3 * * 0', async () => {
      console.log('[Kokonut] Running weekly verified farm activity aggregation...');
      try {
        const activities = await database('farm_activity')
          .where('status', 'verified')
          .whereRaw(
            'farm_activity_source_eligible_for_use(source_system, source_id, source_raw, location_id)'
          )
          .select(
            database.raw('DATE_TRUNC(\'week\', activity_date) as week'),
            'location_id',
            database.raw('COUNT(*) as activity_count'),
            database.raw('SUM(labor_hours) as total_labor_hours'),
            database.raw('SUM(labor_cost) as total_labor_cost')
          )
          .groupBy('week', 'location_id');

        console.log(
          `[Kokonut] Weekly verified farm activity query returned ${activities.length} location-week rows; no snapshot records were persisted`
        );
      } catch (error) {
        console.error(`[Kokonut] Weekly verified farm activity aggregation failed: ${errorClass(error)}`);
      }
    });
  }
});

async function recalculateNoi(cropCycleId: string | undefined) {
  if (!cropCycleId) return;
  try {
    const calc = await calculateNoi(cropCycleId);
    await storeNoiSnapshot(calc);
    console.log(`[Kokonut] NOI recalculated for crop cycle: ${cropCycleId}`);
  } catch (error) {
    console.error(`[Kokonut] Failed to recalulate NOI for ${cropCycleId}: ${errorClass(error)}`);
  }
}
