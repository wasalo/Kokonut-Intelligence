/**
 * Crop NOI Calculator
 *
 * Calculates Net Operating Income for a crop cycle:
 * NOI = Net Revenue - Direct Crop Costs - Allocated Shared Costs
 *
 * Net Revenue = Gross Sales - Returns - Discounts
 *
 * The NOI formula lives in the PostgreSQL view `v_crop_cycle_noi`
 * (migration 353) so Python and TypeScript share one implementation;
 * this module reads the view rather than re-implementing the SQL.
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
 * Main NOI calculation: reads the shared v_crop_cycle_noi view
 * (single formula owner) and maps it onto the calculation shape.
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

  const row = await db('v_crop_cycle_noi')
    .where('crop_cycle_id', cropCycleId)
    .first();

  if (!row) {
    return calculation;
  }

  calculation.locationId = row.location_id || '';
  if (row.period_start) {
    calculation.periodStart = new Date(row.period_start);
  }
  if (row.period_end) {
    calculation.periodEnd = new Date(row.period_end);
  }
  calculation.grossRevenue = parseFloat(row.gross_revenue ?? '0');
  calculation.returnsAndDiscounts = parseFloat(row.returns_discounts ?? '0');
  calculation.netRevenue = parseFloat(row.net_revenue ?? '0');
  calculation.directCropCosts = parseFloat(row.direct_crop_costs ?? '0');
  calculation.allocatedSharedCosts = parseFloat(row.allocated_shared_costs ?? '0');
  calculation.totalCosts = parseFloat(row.total_costs ?? '0');
  calculation.noi = parseFloat(row.noi ?? '0');
  calculation.operatingMarginPct = parseFloat(row.operating_margin_pct ?? '0');
  calculation.lossRatePct = parseFloat(row.loss_rate_pct ?? '0');

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

  // Upsert: insert or update existing snapshot for this crop_cycle_id
  await db('noi_snapshot')
    .insert(snapshotData)
    .onConflict('crop_cycle_id')
    .merge({
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
 * Calculate loss rate for a single crop cycle (reads the shared view).
 */
export async function calculateLossRate(cropCycleId: string): Promise<number> {
  const row = await db('v_crop_cycle_noi')
    .where('crop_cycle_id', cropCycleId)
    .first();
  return row ? parseFloat(row.loss_rate_pct ?? '0') : 0;
}

/**
 * Calculate operating margin for a single crop cycle
 */
export async function calculateOperatingMargin(cropCycleId: string): Promise<number> {
  const calc = await calculateNoi(cropCycleId);
  return calc.operatingMarginPct;
}
