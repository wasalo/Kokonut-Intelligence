/**
 * Crop NOI Calculator
 *
 * Calculates Net Operating Income for a crop cycle:
 * NOI = Net Revenue - Direct Crop Costs - Allocated Shared Costs
 *
 * Net Revenue = Gross Sales - Returns - Discounts
 *
 * Also calculates loss rate and operating margin.
 */

// Database client set by the hook initialization
let db: any;

export function setDb(databaseClient: any) {
  db = databaseClient;
}

interface NoiCalculation {
  cropCycleId: string;
  locationId: string;
  periodStart: Date;
  periodEnd: Date;
  grossRevenue: number;
  returnsAndDiscounts: number;
  netRevenue: number;
  directCropCosts: number;
  allocatedSharedCosts: number;
  totalCosts: number;
  noi: number;
  operatingMarginPct: number;
  lossRatePct: number;
  inputs: Record<string, unknown>;
}

/**
 * Main NOI calculation function with actual database queries
 */
export async function calculateNoi(cropCycleId: string): Promise<NoiCalculation> {
  const calculation: NoiCalculation = {
    cropCycleId,
    locationId: '',
    periodStart: new Date(),
    periodEnd: new Date(),
    grossRevenue: 0,
    returnsAndDiscounts: 0,
    netRevenue: 0,
    directCropCosts: 0,
    allocatedSharedCosts: 0,
    totalCosts: 0,
    noi: 0,
    operatingMarginPct: 0,
    lossRatePct: 0,
    inputs: {},
  };

  // Get crop cycle info
  const cropCycle = await db('crop_cycle')
    .where('id', cropCycleId)
    .first();

  if (cropCycle) {
    calculation.locationId = cropCycle.location_id || '';
    calculation.periodStart = cropCycle.planting_date || new Date();
    calculation.periodEnd = cropCycle.actual_harvest_date || cropCycle.expected_harvest_date || new Date();
  }

  // Step 1: Get all sales for this crop cycle
  const salesResult = await db('sales_event')
    .where('crop_cycle_id', cropCycleId)
    .whereNot('status', 'rejected')
    .select(
      db.raw('COALESCE(SUM(total_amount), 0) as gross'),
      db.raw('COALESCE(SUM(return_amount), 0) as returns'),
      db.raw('COALESCE(SUM(discount_amount), 0) as discounts')
    )
    .first();

  calculation.grossRevenue = parseFloat(salesResult?.gross || '0');
  calculation.returnsAndDiscounts =
    parseFloat(salesResult?.returns || '0') +
    parseFloat(salesResult?.discounts || '0');

  // Step 2: Get all direct expenses for this crop cycle
  const expenseResult = await db('expense_event')
    .where('crop_cycle_id', cropCycleId)
    .whereIn('status', ['verified', 'published'])
    .select(db.raw('COALESCE(SUM(amount), 0) as total'))
    .first();

  calculation.directCropCosts = parseFloat(expenseResult?.total || '0');

  // Step 3: Get allocated shared expenses
  const allocationResult = await db('crop_cost_allocation')
    .where('crop_cycle_id', cropCycleId)
    .select(db.raw('COALESCE(SUM(allocated_amount), 0) as total'))
    .first();

  calculation.allocatedSharedCosts = parseFloat(allocationResult?.total || '0');

  // Step 4: Get harvest data for loss rate
  const harvestResult = await db('harvest_event')
    .where('crop_cycle_id', cropCycleId)
    .whereNot('status', 'rejected')
    .select(
      db.raw('COALESCE(SUM(quantity), 0) as total_harvest'),
      db.raw('COALESCE(SUM(loss_amount), 0) as total_loss')
    )
    .first();

  const totalHarvest = parseFloat(harvestResult?.total_harvest || '0');
  const totalLoss = parseFloat(harvestResult?.total_loss || '0');
  calculation.lossRatePct = totalHarvest > 0
    ? (totalLoss / totalHarvest) * 100
    : 0;

  // Calculate outputs
  calculation.netRevenue = calculation.grossRevenue - calculation.returnsAndDiscounts;
  calculation.totalCosts = calculation.directCropCosts + calculation.allocatedSharedCosts;
  calculation.noi = calculation.netRevenue - calculation.totalCosts;
  calculation.operatingMarginPct = calculation.netRevenue > 0
    ? (calculation.noi / calculation.netRevenue) * 100
    : 0;

  return calculation;
}

/**
 * Store NOI snapshot in the noi_snapshot table
 */
export async function storeNoiSnapshot(calc: NoiCalculation): Promise<void> {
  const snapshotData = {
    crop_cycle_id: calc.cropCycleId,
    location_id: calc.locationId,
    period_start: calc.periodStart,
    period_end: calc.periodEnd,
    gross_revenue: calc.grossRevenue,
    net_revenue: calc.netRevenue,
    direct_crop_costs: calc.directCropCosts,
    allocated_shared_costs: calc.allocatedSharedCosts,
    total_costs: calc.totalCosts,
    noi: calc.noi,
    operating_margin_pct: calc.operatingMarginPct,
    loss_rate_pct: calc.lossRatePct,
    calculation_version: '1.0',
    calculated_at: new Date(),
    inputs: JSON.stringify(calc.inputs),
  };

  // Check if snapshot exists for this crop_cycle_id
  const existing = await db('noi_snapshot')
    .where('crop_cycle_id', snapshotData.crop_cycle_id)
    .first();

  if (existing) {
    // Update existing snapshot
    await db('noi_snapshot')
      .where('crop_cycle_id', snapshotData.crop_cycle_id)
      .update({
        gross_revenue: snapshotData.gross_revenue,
        net_revenue: snapshotData.net_revenue,
        direct_crop_costs: snapshotData.direct_crop_costs,
        allocated_shared_costs: snapshotData.allocated_shared_costs,
        total_costs: snapshotData.total_costs,
        noi: snapshotData.noi,
        operating_margin_pct: snapshotData.operating_margin_pct,
        loss_rate_pct: snapshotData.loss_rate_pct,
        calculation_version: snapshotData.calculation_version,
        calculated_at: snapshotData.calculated_at,
        inputs: snapshotData.inputs,
      });
  } else {
    // Insert new snapshot
    await db('noi_snapshot').insert(snapshotData);
  }
}

/**
 * Batch calculate NOI for all active crop cycles
 */
export async function batchCalculateNoi(locationId?: string): Promise<NoiCalculation[]> {
  let query = db('crop_cycle').whereIn('status', [
    'active', 'flowering', 'harvesting', 'harvested', 'completed',
  ]);

  if (locationId) {
    query = query.where('location_id', locationId);
  }

  const cropCycles = await query.select('id');
  const results: NoiCalculation[] = [];

  for (const cc of cropCycles) {
    try {
      const result = await calculateNoi(cc.id);
      await storeNoiSnapshot(result);
      results.push(result);
    } catch (error) {
      console.error(`[Kokonut] Failed to calculate NOI for crop cycle ${cc.id}:`, error);
    }
  }

  return results;
}

/**
 * Calculate loss rate for a single crop cycle
 */
export async function calculateLossRate(cropCycleId: string): Promise<number> {
  const harvestResult = await db('harvest_event')
    .where('crop_cycle_id', cropCycleId)
    .whereNot('status', 'rejected')
    .select(
      db.raw('COALESCE(SUM(quantity), 0) as total_harvest'),
      db.raw('COALESCE(SUM(loss_amount), 0) as total_loss')
    )
    .first();

  const totalHarvest = parseFloat(harvestResult?.total_harvest || '0');
  const totalLoss = parseFloat(harvestResult?.total_loss || '0');

  return totalHarvest > 0 ? (totalLoss / totalHarvest) * 100 : 0;
}

/**
 * Calculate operating margin for a single crop cycle
 */
export async function calculateOperatingMargin(cropCycleId: string): Promise<number> {
  const calc = await calculateNoi(cropCycleId);
  return calc.operatingMarginPct;
}
