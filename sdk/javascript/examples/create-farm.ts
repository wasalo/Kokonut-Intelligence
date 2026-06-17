/**
 * Example: Create a location, farm, and plot using the Kokonut SDK.
 *
 * Usage:
 *   npx tsx examples/create-farm.ts
 */

import { KokonutClient } from '../src/index.js';

const client = new KokonutClient('http://localhost:8055', {
  token: process.env.KOKONUT_TOKEN,
});

async function main() {
  await client.login('admin@example.com', process.env.ADMIN_PASSWORD || 'changeme');

  const location = await client.locations.create({
    name: 'Finca El Paraiso',
    slug: 'finca-el-paraiso',
    description: 'Regenerative coffee and cacao farm in Huila, Colombia',
    baseline_revenue: 45000,
    baseline_asset_value: 120000,
    baseline_cash_flow: 12000,
    status: 'active',
  });
  console.log('Location created:', location.id);

  const farm = await client.farms.create({
    location_id: location.id,
    name: 'El Paraiso Main Farm',
    farm_type: 'operational',
    total_area: 25,
    area_unit: 'ha',
    status: 'active',
  });
  console.log('Farm created:', farm.id);

  const plotA = await client.plots.create({
    farm_id: farm.id,
    name: 'Plot A - Coffee',
    area: 12,
    area_unit: 'ha',
    soil_type: 'clay_loam',
    water_source: 'spring_fed_irrigation',
    status: 'active',
  });
  console.log('Plot A created:', plotA.id);

  const plotB = await client.plots.create({
    farm_id: farm.id,
    name: 'Plot B - Cacao',
    area: 8,
    area_unit: 'ha',
    soil_type: 'volcanic_loam',
    water_source: 'rainfed',
    status: 'active',
  });
  console.log('Plot B created:', plotB.id);

  console.log('\nFarm setup complete!');
  console.log('Location:', location.id);
  console.log('Farm:', farm.id);
  console.log('Plots:', plotA.id, plotB.id);
}

main().catch(console.error);
