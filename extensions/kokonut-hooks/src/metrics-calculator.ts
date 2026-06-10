/**
 * Crop NOI Calculator
 *
 * Calculates Net Operating Income for a crop cycle:
 * NOI = Net Revenue - Direct Crop Costs - Allocated Shared Costs
 *
 * Net Revenue = Gross Sales - Returns - Discounts
 */

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
 * Main NOI calculation function
 * This would be called by Directus hooks or manually
 */
export async function calculateNoi(cropCycleId: string): Promise<NoiCalculation> {
  // In production, this would query the Directus API or database
  // For now, it's a structural skeleton

  const calculation: NoiCalculation = {
    cropCycleId,
    locationId: '', // populated from crop cycle
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

  // Step 1: Get all sales for this crop cycle
  // SELECT SUM(total_amount) FROM sales_event WHERE crop_cycle_id = $1 AND status = 'verified'
  // SELECT SUM(return_amount + discount_amount) FROM sales_event WHERE crop_cycle_id = $1

  // Step 2: Get all direct expenses for this crop cycle
  // SELECT SUM(amount) FROM expense_event WHERE crop_cycle_id = $1 AND status IN ('approved', 'paid')

  // Step 3: Get allocated shared expenses
  // SELECT SUM(allocated_amount) FROM crop_cost_allocation WHERE crop_cycle_id = $1

  // Step 4: Get harvest data for loss rate
  // SELECT SUM(quantity), SUM(loss_amount) FROM harvest_event WHERE crop_cycle_id = $1

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
  // Get all active crop cycles, optionally filtered by location
  const cropCycles: string[] = []; // populated from DB

  const results: NoiCalculation[] = [];
  for (const ccId of cropCycles) {
    const result = await calculateNoi(ccId);
    results.push(result);
  }

  return results;
}
