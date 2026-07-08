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
  prepareAgentActionLog,
} from './agent-safety.js';

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

export default defineHook(({ filter, action, schedule }, { database }) => {
  setDb(database);

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
      console.error(`[Kokonut] Failed to log workflow transition for ${collection}:`, error);
    }
  }

  async function applyWorkflow(
    collection: string,
    payload: Record<string, any>,
    meta: Record<string, any>
  ) {
    const userRoles = await resolveUserRoles(database, meta);
    const accountability = meta?.accountability;
    return await handleWorkflowTransition(
      collection, payload, meta.keys || {}, userRoles, database, accountability
    );
  }

  // Register workflow-only filter hooks
  for (const collection of WORKFLOW_ONLY_COLLECTIONS) {
    filter(`${collection}.update`, async (payload: Record<string, any>, meta: Record<string, any>) => {
      return await applyWorkflow(collection, payload, meta);
    });
  }

  // ============================================================
  // Filter hooks (blocking - run before DB write)
  // ============================================================

  filter('expense_event.create', (payload: Record<string, any>) => {
    autoCategorizeExpense(payload);

    if (payload.amount !== undefined) {
      const errors = validateExpenseAmount(payload.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    if (payload.expense_date) {
      const dateError = validateExpenseDate(payload.expense_date);
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

  filter('expense_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    // Re-run auto-categorization if category was cleared
    if (!payload.category || payload.category === '') {
      autoCategorizeExpense(payload);
    }

    if (payload.amount !== undefined) {
      const errors = validateExpenseAmount(payload.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    return await applyWorkflow('expense_event', payload, meta);
  });

  filter('sales_event.create', (payload: Record<string, any>) => {
    if (payload.total_amount !== undefined) {
      payload.net_amount = calculateNetAmount(
        payload.total_amount || 0,
        payload.return_amount || 0,
        payload.discount_amount || 0
      );
    }

    if (payload.total_amount !== undefined) {
      const errors = validateSalesAmount(payload.total_amount);
      if (errors.length > 0) {
        throw new Error(`Sales validation: ${errors.join('; ')}`);
      }
    }

    if (payload.sale_date) {
      const dateError = validateNotFutureDate(payload.sale_date);
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

  filter('sales_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    if (payload.total_amount !== undefined || payload.return_amount !== undefined || payload.discount_amount !== undefined) {
      const current = await database('sales_event')
        .where('id', meta.keys?.[0] || payload.id)
        .first();

      const total = payload.total_amount ?? current?.total_amount ?? 0;
      const returns = payload.return_amount ?? current?.return_amount ?? 0;
      const discount = payload.discount_amount ?? current?.discount_amount ?? 0;
      payload.net_amount = calculateNetAmount(total, returns, discount);
    }

    return await applyWorkflow('sales_event', payload, meta);
  });

  filter('harvest_event.create', (payload: Record<string, any>) => {
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

  filter('harvest_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('harvest_event', payload, meta);
  });

  filter('farm_activity.create', (payload: Record<string, any>) => {
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

  filter('farm_activity.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('farm_activity', payload, meta);
  });

  filter('loss_event.create', (payload: Record<string, any>) => {
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

  filter('loss_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('loss_event', payload, meta);
  });

  filter('labor_event.create', (payload: Record<string, any>) => {
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

  filter('labor_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('labor_event', payload, meta);
  });

  filter('field_note.create', (payload: Record<string, any>) => {
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

  filter('field_note.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('field_note', payload, meta);
  });

  filter('stakeholder_feedback.create', (payload: Record<string, any>) => {
    normalizeFeedbackPayload(payload);
    validateStakeholderFeedback(payload);
    return payload;
  });

  filter('stakeholder_feedback.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const current = recordId ? await database('stakeholder_feedback').where('id', recordId).first() : {};
    validateStakeholderFeedback({ ...(current || {}), ...payload });
    return await applyWorkflow('stakeholder_feedback', payload, meta);
  });

  filter('metric_proposal.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    const accountability = meta?.accountability || meta?.payload?._accountability;
    return await handleMetricProposalUpdate(payload, meta, database, accountability);
  });

  filter('impact_claim.create', (payload: Record<string, any>) => {
    normalizeImpactClaimPayload(payload);
    validateImpactClaim(payload);
    return payload;
  });

  filter('impact_claim.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const current = recordId ? await database('impact_claim').where('id', recordId).first() : {};
    validateImpactClaim({ ...(current || {}), ...payload });
    const accountability = meta?.accountability || meta?.payload?._accountability;
    await stampImpactClaimReview(payload, accountability);
    return await applyWorkflow('impact_claim', payload, meta);
  });

  filter('agent_task.create', (payload: Record<string, any>) => enforceAgentTaskSafety(payload));
  filter('agent_task.update', (payload: Record<string, any>) => enforceAgentTaskSafety(payload));
  filter('ai_summary.create', (payload: Record<string, any>) => enforceAiSummarySafety(payload));
  filter('ai_summary.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    enforceAiSummarySafety(payload);
    return await applyWorkflow('ai_summary', payload, meta);
  });
  filter('agent_action_log.create', (payload: Record<string, any>) => prepareAgentActionLog(payload));

  // ============================================================
  // Action hooks (non-blocking - run after DB write)
  // ============================================================

  for (const collection of LIFECYCLE_COLLECTIONS) {
    action(`${collection}.update`, async (meta: Record<string, any>) => {
      const newStatus = meta?.payload?.status;
      const recordId = meta.keys?.[0] ?? meta.keys?.id;
      if (newStatus && recordId) {
        const userId = getUserId(meta);
        await logTransition(collection, recordId, newStatus, userId, meta);
      }
    });
  }

  action('stakeholder_feedback.update', async (meta: Record<string, any>) => {
    const recordId = meta.keys?.[0] ?? meta.keys?.id;
    const status = meta?.payload?.status;
    if (!recordId || !status) return;

    const userId = getUserId(meta);
    if (status === 'published') {
      await recordFeedbackReview(database, recordId, 'published_summary', userId, 'Public summary published.');
    } else if (status === 'rejected') {
      await recordFeedbackReview(database, recordId, 'dismissed', userId, meta?.payload?.rejection_reason);
    }
  });

  action('metric_proposal.update', async (meta: Record<string, any>) => {
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

  action('harvest_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('sales_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
    await writeFinancialEvent('sales', payload);
  });

  action('expense_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    if (payload.crop_cycle_id) {
      await recalculateNoi(payload.crop_cycle_id);
    }
    await writeFinancialEvent('expense', payload);
  });

  // ============================================================
  // Scheduled hooks
  // ============================================================

  schedule('0 2 * * *', async () => {
    console.log('[Kokonut] Running daily NOI reconciliation...');
    try {
      const results = await batchCalculateNoi();
      console.log(`[Kokonut] NOI reconciled for ${results.length} crop cycles`);
    } catch (error) {
      console.error('[Kokonut] NOI reconciliation failed:', error);
    }
  });

  schedule('0 3 * * 0', async () => {
    console.log('[Kokonut] Running weekly metric snapshots...');
    try {
      const activities = await database('farm_activity')
        .where('status', 'verified')
        .select(
          database.raw('DATE_TRUNC(\'week\', activity_date) as week'),
          'location_id',
          database.raw('COUNT(*) as activity_count'),
          database.raw('SUM(labor_hours) as total_labor_hours'),
          database.raw('SUM(labor_cost) as total_labor_cost')
        )
        .groupBy('week', 'location_id');

      console.log(`[Kokonut] Weekly snapshots created for ${activities.length} locations`);
    } catch (error) {
      console.error('[Kokonut] Weekly snapshots failed:', error);
    }
  });
});

async function recalculateNoi(cropCycleId: string | undefined) {
  if (!cropCycleId) return;
  try {
    const calc = await calculateNoi(cropCycleId);
    await storeNoiSnapshot(calc);
    console.log(`[Kokonut] NOI recalculated for crop cycle: ${cropCycleId}`);
  } catch (error) {
    console.error(`[Kokonut] Failed to recalulate NOI for ${cropCycleId}:`, error);
  }
}

async function writeFinancialEvent(type: string, payload: Record<string, any>) {
  try {
    const amount = payload.total_amount || payload.amount || 0;
    if (amount === 0) return;

    const chHost = process.env.CH_HOST || 'clickhouse';
    const chPort = process.env.CH_PORT || '8123';
    const chUser = process.env.CH_USER || 'kokonut';
    const chPass = process.env.CH_PASSWORD || '';

    // Validate all values before ClickHouse interpolation
    const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const STR_RE = /^[a-zA-Z0-9_\- ]+$/;
    const CAT_RE = /^[a-zA-Z0-9_\-]+$/;
    const CUR_RE = /^[A-Z]{3}$/;

    const txId = (payload.id && UUID_RE.test(payload.id)) ? payload.id : crypto.randomUUID();
    const locId = (payload.location_id && UUID_RE.test(payload.location_id)) ? payload.location_id : '00000000-0000-0000-0000-000000000000';
    const cat = payload.category && CAT_RE.test(payload.category) ? payload.category.substring(0, 50) : (type || 'other');
    const cur = currency && CUR_RE.test(currency) ? currency : 'USD';
    const amt = typeof amount === 'number' && isFinite(amount) ? amount : 0;
    const ts = new Date().toISOString().replace('T', ' ').replace('Z', '');
    const safeType = STR_RE.test(type) ? type : 'other';

    const query = `INSERT INTO financial_events
      (timestamp, transaction_id, location_id, transaction_type, category,
       amount, currency, amount_usd, chain, token, metadata)
      VALUES (
        '${ts}', '${txId}', '${locId}', '${safeType}', '${cat}',
        ${amt}, '${cur}', ${amt}, '', '', map()
      )`;

    const auth = Buffer.from(`${chUser}:${chPass}`).toString('base64');
    await fetch(`http://${chHost}:${chPort}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'text/plain',
        'Authorization': `Basic ${auth}`,
      },
      body: query,
    });
  } catch (error) {
    console.error(`[Kokonut] Failed to write financial event to ClickHouse:`, error);
  }
}
