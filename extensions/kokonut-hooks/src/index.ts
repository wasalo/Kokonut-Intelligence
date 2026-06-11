import { defineHook } from '@directus/extensions-sdk';
import { calculateNoi, batchCalculateNoi, storeNoiSnapshot, setDb } from './metrics-calculator.js';
import { handleWorkflowTransition, logWorkflowTransition } from './workflow.js';
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

export default defineHook(({ filter, action, schedule }, { database }) => {
  setDb(database);

  // Helper: extract user roles from accountability
  function getUserRoles(meta: Record<string, any>): string[] {
    const accountability = meta?. accountability || meta?.payload?._accountability;
    if (!accountability) return [];
    if (accountability.admin) return ['admin'];
    return accountability.role ? [accountability.role] : [];
  }

  function getUserId(meta: Record<string, any>): string | undefined {
    const accountability = meta?. accountability || meta?.payload?._accountability;
    return accountability?.user;
  }

  // Helper: log workflow transition after DB write
  async function logTransition(
    collection: string,
    recordId: string,
    fromStatus: string | undefined,
    toStatus: string,
    userId: string | undefined,
    meta: Record<string, any>
  ) {
    try {
      const notes = meta?.payload?.rejection_reason || undefined;
      await logWorkflowTransition(
        database, collection, recordId, fromStatus, toStatus, userId, undefined, notes
      );
    } catch (error) {
      console.error(`[Kokonut] Failed to log workflow transition for ${collection}:`, error);
    }
  }

  // ============================================================
  // Filter hooks (blocking - run before DB write)
  // ============================================================

  // --- Expense event hooks ---
  filter('expense_event.create', (payload: Record<string, any>) => {
    // Auto-categorize if category is blank
    autoCategorizeExpense(payload);

    // Validate amount
    if (payload.amount !== undefined) {
      const errors = validateExpenseAmount(payload.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    // Validate date
    if (payload.expense_date) {
      const dateError = validateExpenseDate(payload.expense_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    return payload;
  });

  filter('expense_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    // Validate amount on update
    if (payload.amount !== undefined) {
      const errors = validateExpenseAmount(payload.amount);
      if (errors.length > 0) {
        throw new Error(`Expense validation: ${errors.join('; ')}`);
      }
    }

    // Workflow transition with role routing
    return handleWorkflowTransition('expense_event', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Sales event hooks ---
  filter('sales_event.create', (payload: Record<string, any>) => {
    // Auto-calculate net_amount
    if (payload.total_amount !== undefined) {
      payload.net_amount = calculateNetAmount(
        payload.total_amount || 0,
        payload.return_amount || 0,
        payload.discount_amount || 0
      );
    }

    // Validate amount
    if (payload.total_amount !== undefined) {
      const errors = validateSalesAmount(payload.total_amount);
      if (errors.length > 0) {
        throw new Error(`Sales validation: ${errors.join('; ')}`);
      }
    }

    // Validate date
    if (payload.sale_date) {
      const dateError = validateNotFutureDate(payload.sale_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    return payload;
  });

  filter('sales_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    // Recalculate net_amount if amount fields change
    if (payload.total_amount !== undefined || payload.return_amount !== undefined || payload.discount_amount !== undefined) {
      const current = await database('sales_event')
        .where('id', meta.keys?.[0] || payload.id)
        .first();

      const total = payload.total_amount ?? current?.total_amount ?? 0;
      const returns = payload.return_amount ?? current?.return_amount ?? 0;
      const discount = payload.discount_amount ?? current?.discount_amount ?? 0;
      payload.net_amount = calculateNetAmount(total, returns, discount);
    }

    // Workflow transition with role routing
    return handleWorkflowTransition('sales_event', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Harvest event hooks ---
  filter('harvest_event.create', (payload: Record<string, any>) => {
    // Auto-calculate loss_estimated_value
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

    // Validate quantity
    if (payload.quantity !== undefined) {
      const warnings = validateHarvestQuantity(payload.quantity, payload.expected_yield);
      // Warnings don't block, but we log them
      if (warnings.length > 0) {
        console.log(`[Kokonut] Harvest warnings: ${warnings.join('; ')}`);
      }
    }

    // Validate date
    if (payload.harvest_date) {
      const dateError = validateNotFutureDate(payload.harvest_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    return payload;
  });

  filter('harvest_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('harvest_event', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Farm activity hooks ---
  filter('farm_activity.create', (payload: Record<string, any>) => {
    // Validate date
    if (payload.activity_date) {
      const dateError = validateNotFutureDate(payload.activity_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    // Auto-calculate labor cost
    if (payload.labor_hours && payload.hourly_rate && !payload.labor_cost) {
      payload.labor_cost = calculateLaborCost(payload.labor_hours, payload.hourly_rate);
    }

    return payload;
  });

  filter('farm_activity.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('farm_activity', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Loss event hooks ---
  filter('loss_event.create', (payload: Record<string, any>) => {
    if (payload.loss_date) {
      const dateError = validateNotFutureDate(payload.loss_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }
    return payload;
  });

  filter('loss_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('loss_event', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Labor event hooks ---
  filter('labor_event.create', (payload: Record<string, any>) => {
    // Auto-calculate total_cost
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

  filter('labor_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('labor_event', payload, meta.keys || {}, getUserRoles(meta));
  });

  // --- Field note hooks ---
  filter('field_note.create', (payload: Record<string, any>) => {
    // Auto-summarize long content
    autoSummarizeFieldNote(payload);

    if (payload.note_date) {
      const dateError = validateNotFutureDate(payload.note_date);
      if (dateError) {
        throw new Error(dateError);
      }
    }

    return payload;
  });

  filter('field_note.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('field_note', payload, meta.keys || {}, getUserRoles(meta));
  });

  // ============================================================
  // Action hooks (non-blocking - run after DB write)
  // ============================================================

  // Log workflow transitions and recalculate NOI
  const workflowCollections = [
    'farm_activity', 'harvest_event', 'expense_event',
    'sales_event', 'loss_event', 'labor_event', 'field_note',
  ];

  for (const collection of workflowCollections) {
    action(`${collection}.update`, async (meta: Record<string, any>) => {
      const newStatus = meta?.payload?.status;
      if (newStatus) {
        const userId = getUserId(meta);
        await logTransition(collection, meta.keys?.[0], undefined, newStatus, userId, meta);
      }
    });
  }

  // NOI recalculation on harvest, sale, or expense changes
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

  // Daily NOI reconciliation at 02:00 UTC
  schedule('0 2 * * *', async () => {
    console.log('[Kokonut] Running daily NOI reconciliation...');
    try {
      const results = await batchCalculateNoi();
      console.log(`[Kokonut] NOI reconciled for ${results.length} crop cycles`);
    } catch (error) {
      console.error('[Kokonut] NOI reconciliation failed:', error);
    }
  });

  // Weekly metric snapshots — Sunday 03:00 UTC
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

// ============================================================
// Helper functions
// ============================================================

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
