/**
 * Crop NOI Calculator
 *
 * Calculates Net Operating Income for a crop cycle:
 * NOI = Net Revenue - Direct Crop Costs - Allocated Shared Costs
 *
 * Net Revenue = Gross Sales - Returns - Discounts
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
    calculation.periodEnd = cropCycle.expected_harvest_date || new Date();
  }

  // Step 1: Get all sales for this crop cycle
  const salesResult = await db('sales_event')
    .where('crop_cycle_id', cropCycleId)
    .where('status', '!=', 'rejected')
    .sum('total_amount as gross')
    .sum('return_amount as returns')
    .sum('discount_amount as discounts')
    .first();

  calculation.grossRevenue = parseFloat(salesResult?.gross || '0');
  calculation.returnsAndDiscounts = parseFloat(salesResult?.returns || '0') + parseFloat(salesResult?.discounts || '0');

  // Step 2: Get all direct expenses for this crop cycle
  const expenseResult = await db('expense_event')
    .where('crop_cycle_id', cropCycleId)
    .where('status', 'in', ['approved', 'paid'])
    .sum('amount as total')
    .first();

  calculation.directCropCosts = parseFloat(expenseResult?.total || '0');

  // Step 3: Get allocated shared expenses
  const allocationResult = await db('crop_cost_allocation')
    .where('crop_cycle_id', cropCycleId)
    .sum('allocated_amount as total')
    .first();

  calculation.allocatedSharedCosts = parseFloat(allocationResult?.total || '0');

  // Step 4: Get harvest data for loss rate
  const harvestResult = await db('harvest_event')
    .where('crop_cycle_id', cropCycleId)
    .where('status', '!=', 'rejected')
    .sum('quantity as total_harvest')
    .sum('loss_amount as total_loss')
    .first();

  const totalHarvest = parseFloat(harvestResult?.total_harvest || '0');
  const totalLoss = parseFloat(harvestResult?.total_loss || '0');
  calculation.lossRatePct = totalHarvest > 0 ? (totalLoss / totalHarvest) * 100 : 0;

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
 * Batch calculate NOI for all active crop cycles
 */
export async function batchCalculateNoi(locationId?: string): Promise<NoiCalculation[]> {
  let query = db('crop_cycle').where('status', 'active');
  
  if (locationId) {
    query = query.where('location_id', locationId);
  }

  const cropCycles = await query.select('id');
  const results: NoiCalculation[] = [];

  for (const cc of cropCycles) {
    const result = await calculateNoi(cc.id);
    results.push(result);
  }

  return results;
}
