import { defineHook } from '@directus/extensions-sdk';
import { calculateNoi } from './metrics-calculator';
import { handleWorkflowTransition } from './workflow';

export default defineHook(({ filter, action, schedule }) => {

  // ============================================================
  // Filter hooks (blocking - run before DB write)
  // ============================================================

  // Auto-calculate net_amount on sales_event
  filter('sales_event.create', (payload) => {
    if (payload.total_amount && payload.return_amount !== undefined && payload.discount_amount !== undefined) {
      payload.net_amount = payload.total_amount - (payload.return_amount || 0) - (payload.discount_amount || 0);
    }
    return payload;
  });

  filter('sales_event.update', (payload) => {
    if (payload.total_amount || payload.return_amount !== undefined || payload.discount_amount !== undefined) {
      // Recalculate if any component changed
      const total = payload.total_amount;
      const returns = payload.return_amount || 0;
      const discount = payload.discount_amount || 0;
      if (total !== undefined) {
        payload.net_amount = total - returns - discount;
      }
    }
    return payload;
  });

  // Validate status transitions
  filter('farm_activity.update', (payload, { keys }) => {
    return handleWorkflowTransition('farm_activity', payload, keys);
  });

  filter('harvest_event.update', (payload, { keys }) => {
    return handleWorkflowTransition('harvest_event', payload, keys);
  });

  filter('expense_event.update', (payload, { keys }) => {
    return handleWorkflowTransition('expense_event', payload, keys);
  });

  filter('sales_event.update', (payload, { keys }) => {
    return handleWorkflowTransition('sales_event', payload, keys);
  });

  // ============================================================
  // Action hooks (non-blocking - run after DB write)
  // ============================================================

  // Recalculate NOI snapshot when harvest, sale, or expense changes
  action('harvest_event.create', async ({ payload }) => {
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('sales_event.create', async ({ payload }) => {
    await recalculateNoi(payload.crop_cycle_id);
  });

  action('expense_event.create', async ({ payload }) => {
    if (payload.crop_cycle_id) {
      await recalculateNoi(payload.crop_cycle_id);
    }
  });

  // Update location last_active_date for wallet events
  action('wallet_activity_event.create', async ({ payload }) => {
    // Could update related location's last activity timestamp
  });

  // ============================================================
  // Scheduled hooks
  // ============================================================

  // Run daily NOI reconciliation
  schedule('0 2 * * *', async () => {
    console.log('[Kokonut] Running daily NOI reconciliation...');
    // TODO: Reconcile all active crop cycles
  });

  // Run weekly metric snapshots
  schedule('0 3 * * 0', async () => {
    console.log('[Kokonut] Running weekly metric snapshots...');
    // TODO: Generate weekly snapshots for all locations
  });
});

// ============================================================
// Helper functions
// ============================================================

async function recalculateNoi(cropCycleId: string | undefined) {
  if (!cropCycleId) return;
  try {
    await calculateNoi(cropCycleId);
    console.log(`[Kokonut] NOI recalculated for crop cycle: ${cropCycleId}`);
  } catch (error) {
    console.error(`[Kokonut] Failed to recalculate NOI for ${cropCycleId}:`, error);
  }
}
