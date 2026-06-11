import { defineHook } from '@directus/extensions-sdk';
import { calculateNoi, batchCalculateNoi, setDb } from './metrics-calculator.js';
import { handleWorkflowTransition } from './workflow.js';

export default defineHook(({ filter, action, schedule }, { database }) => {
  // Set the database client for the metrics calculator
  setDb(database);

  // ============================================================
  // Filter hooks (blocking - run before DB write)
  // ============================================================

  // Auto-calculate net_amount on sales_event
  filter('sales_event.create', (payload: Record<string, any>) => {
    if (payload.total_amount !== undefined) {
      const total = payload.total_amount || 0;
      const returns = payload.return_amount || 0;
      const discount = payload.discount_amount || 0;
      payload.net_amount = total - returns - discount;
    }
    return payload;
  });

  filter('sales_event.update', async (payload: Record<string, any>, meta: Record<string, any>) => {
    // If any amount field is being updated, recalculate net_amount
    if (payload.total_amount !== undefined || payload.return_amount !== undefined || payload.discount_amount !== undefined) {
      // For updates, we need to get the current values from DB if not in payload
      const current = await database('sales_event')
        .where('id', meta.keys?.[0] || payload.id)
        .first();
      
      const total = payload.total_amount ?? current?.total_amount ?? 0;
      const returns = payload.return_amount ?? current?.return_amount ?? 0;
      const discount = payload.discount_amount ?? current?.discount_amount ?? 0;
      payload.net_amount = total - returns - discount;
    }
    return payload;
  });

  // Validate status transitions
  filter('farm_activity.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('farm_activity', payload, meta.keys || {});
  });

  filter('harvest_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('harvest_event', payload, meta.keys || {});
  });

  filter('expense_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('expense_event', payload, meta.keys || {});
  });

  filter('sales_event.update', (payload: Record<string, any>, meta: Record<string, any>) => {
    return handleWorkflowTransition('sales_event', payload, meta.keys || {});
  });

  // ============================================================
  // Action hooks (non-blocking - run after DB write)
  // ============================================================

  // Recalculate NOI snapshot when harvest, sale, or expense changes
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

  // Update location last_active_date for wallet events
  action('wallet_activity_event.create', async (_meta: Record<string, any>) => {
    // Could update related location's last activity timestamp
  });

  // ============================================================
  // Scheduled hooks
  // ============================================================

  // Run daily NOI reconciliation
  schedule('0 2 * * *', async () => {
    console.log('[Kokonut] Running daily NOI reconciliation...');
    try {
      const results = await batchCalculateNoi();
      console.log(`[Kokonut] NOI reconciled for ${results.length} crop cycles`);
      
      // Store NOI snapshots
      for (const calc of results) {
        await database('noi_snapshot').insert({
          crop_cycle_id: calc.cropCycleId,
          location_id: calc.locationId,
          period_start: calc.periodStart,
          period_end: calc.periodEnd,
          gross_revenue: calc.grossRevenue,
          returns_and_discounts: calc.returnsAndDiscounts,
          net_revenue: calc.netRevenue,
          direct_crop_costs: calc.directCropCosts,
          allocated_shared_costs: calc.allocatedSharedCosts,
          total_costs: calc.totalCosts,
          noi: calc.noi,
          operating_margin_pct: calc.operatingMarginPct,
          loss_rate_pct: calc.lossRatePct,
          snapshot_date: new Date(),
          source_system: 'daily_reconciliation'
        }).onConflict('crop_cycle_id').merge();
      }
    } catch (error) {
      console.error('[Kokonut] NOI reconciliation failed:', error);
    }
  });

  // Run weekly metric snapshots
  schedule('0 3 * * 0', async () => {
    console.log('[Kokonut] Running weekly metric snapshots...');
    try {
      // Snapshot farm activity metrics
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

      for (const activity of activities) {
        await database('activity_metric').insert({
          name: `Weekly Activity Summary - ${activity.week}`,
          value: activity.activity_count,
          unit: 'activities',
          location_id: activity.location_id,
          metadata: {
            week: activity.week,
            total_labor_hours: activity.total_labor_hours,
            total_labor_cost: activity.total_labor_cost
          },
          source_system: 'weekly_snapshot'
        });
      }

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
    await calculateNoi(cropCycleId);
    console.log(`[Kokonut] NOI recalculated for crop cycle: ${cropCycleId}`);
  } catch (error) {
    console.error(`[Kokonut] Failed to recalculate NOI for ${cropCycleId}:`, error);
  }
}
