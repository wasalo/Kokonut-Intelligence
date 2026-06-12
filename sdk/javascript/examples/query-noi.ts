/**
 * Example: Query NOI snapshots for a crop cycle with filters.
 *
 * Usage:
 *   npx tsx examples/query-noi.ts
 */

import { KokonutClient } from '../src/index.js';

const client = new KokonutClient('http://localhost:8055', {
  token: process.env.KOKONUT_TOKEN,
});

async function main() {
  await client.login('admin@example.com', 'password123');

  const cropCycles = await client.cropCycles.list({
    filter: { status: { _in: ['harvested', 'completed'] } },
    sort: ['-planting_date'],
    limit: 5,
  });

  console.log(`Found ${cropCycles.length} completed crop cycles\n`);

  for (const cycle of cropCycles) {
    console.log(`--- ${cycle.cycle_name} (${cycle.id}) ---`);
    console.log(`  Planted: ${cycle.planting_date}`);
    console.log(`  Harvested: ${cycle.actual_harvest_date ?? 'N/A'}`);
    console.log(`  Yield: ${cycle.yield_actual ?? 'N/A'} ${cycle.yield_unit ?? ''}`);

    const harvests = await client.harvestEvents.listByCropCycle(cycle.id, {
      sort: ['-harvest_date'],
    });
    console.log(`  Harvest events: ${harvests.length}`);

    const sales = await client.salesEvents.listByCropCycle(cycle.id, {
      sort: ['-sale_date'],
    });
    const totalRevenue = sales.reduce((sum: number, s: any) => sum + (s.total_amount ?? 0), 0);
    console.log(`  Sales events: ${sales.length}`);
    console.log(`  Total revenue: $${totalRevenue.toLocaleString()}`);

    const expenses = await client.expenseEvents.listByCropCycle(cycle.id);
    const totalExpenses = expenses.reduce((sum: number, e: any) => sum + (e.amount ?? 0), 0);
    console.log(`  Expense events: ${expenses.length}`);
    console.log(`  Total expenses: $${totalExpenses.toLocaleString()}`);

    const noi = totalRevenue - totalExpenses;
    const margin = totalRevenue > 0 ? ((noi / totalRevenue) * 100).toFixed(1) : '0.0';
    console.log(`  NOI: $${noi.toLocaleString()} (${margin}% margin)\n`);
  }

  const reports = await client.reports.listByType('crop_noi', {
    sort: ['-created_at'],
    limit: 5,
  });
  console.log(`\nRecent NOI report snapshots: ${reports.length}`);
  for (const report of reports) {
    console.log(`  ${report.id} - ${report.created_at}`);
    console.log(`    Hash: ${report.snapshot_hash}`);
  }
}

main().catch(console.error);
