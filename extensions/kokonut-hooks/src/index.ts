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
    const accountability = meta?.accountability || meta?.payload?._accountability;
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

    return payload;
  });

  filter('field_note.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    return await applyWorkflow('field_note', payload, meta);
  });

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

  action('harvest_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('sales_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('expense_event.create', async (meta: Record<string, any>) => {
    const payload = meta.payload || meta;
    if (payload.crop_cycle_id) {
      await recalculateNoi(payload.crop_cycle_id);
    }
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
    console.error(`[Kokonut] Failed to recalculate NOI for ${cropCycleId}:`, error);
  }
}
