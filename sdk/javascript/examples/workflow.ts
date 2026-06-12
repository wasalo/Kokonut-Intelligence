/**
 * Example: Create a harvest event, submit for verification, verify, and publish.
 *
 * Usage:
 *   npx tsx examples/workflow.ts
 */

import { KokonutClient } from '../src/index.js';
import type { HarvestEvent } from '../src/index.js';

const client = new KokonutClient('http://localhost:8055', {
  token: process.env.KOKONUT_TOKEN,
});

const STATE_TRANSITIONS: Record<HarvestEvent['status'], HarvestEvent['status']> = {
  draft: 'submitted',
  submitted: 'verified',
  verified: 'published',
  published: 'published',
  rejected: 'submitted',
};

async function transitionHarvest(
  harvestId: string,
  targetState: HarvestEvent['status']
): Promise<HarvestEvent> {
  const current = await client.harvestEvents.get(harvestId);
  console.log(`  Current state: ${current.status}`);

  if (current.status === targetState) {
    console.log(`  Already in target state: ${targetState}`);
    return current;
  }

  const expectedNext = STATE_TRANSITIONS[current.status];
  if (expectedNext !== targetState) {
    throw new Error(`Invalid transition: ${current.status} -> ${targetState} (expected ${expectedNext})`);
  }

  const updated = await client.harvestEvents.update(harvestId, {
    status: targetState,
  });
  console.log(`  Transitioned to: ${updated.status}`);
  return updated;
}

async function main() {
  await client.login('admin@example.com', 'password123');

  const cropCycleId = 'crop-cycle-id';
  const plotId = 'plot-id';

  console.log('1. Creating draft harvest event...');
  const harvest = await client.harvestEvents.create({
    crop_cycle_id: cropCycleId,
    plot_id: plotId,
    harvest_date: new Date().toISOString(),
    quantity: 1500,
    unit: 'kg',
    quality_grade: 'A',
    gross_weight: 1500,
    net_weight: 1420,
    loss_quantity: 80,
    loss_reason: 'moisture_loss_during_drying',
    status: 'draft',
    recorded_by: 'field-supervisor-001',
  });
  console.log(`  Harvest created: ${harvest.id}\n`);

  console.log('2. Submitting harvest data...');
  await transitionHarvest(harvest.id, 'submitted');
  await client.harvestEvents.update(harvest.id, {
    quantity: 1420,
    loss_quantity: 80,
  });
  console.log('');

  console.log('3. Verifying harvest...');
  await transitionHarvest(harvest.id, 'verified');
  await client.harvestEvents.update(harvest.id, {
    status: 'verified',
  });
  console.log('');

  console.log('4. Publishing verified harvest...');
  await transitionHarvest(harvest.id, 'published');
  await client.harvestEvents.update(harvest.id, {
    status: 'published',
  });
  console.log('');

  console.log('5. Recording corresponding sale...');
  const sale = await client.salesEvents.create({
    crop_cycle_id: cropCycleId,
    harvest_event_id: harvest.id,
    buyer_name: 'Local Cooperative',
    sale_date: new Date().toISOString(),
    quantity: 1420,
    unit: 'kg',
    price_per_unit: 8.5,
    total_amount: 12070,
    currency: 'USD',
    payment_status: 'pending',
    status: 'draft',
  });
  console.log(`  Sale created: ${sale.id}`);

  console.log('\n6. Creating attestation record...');
  const attestation = await client.attestations.create({
    entity_type: 'harvest_event',
    entity_id: harvest.id,
    claim_type: 'verified_harvest',
    claim_data: {
      crop_cycle_id: cropCycleId,
      quantity: 1420,
      unit: 'kg',
      quality_grade: 'A',
      loss_rate_pct: 5.33,
      verified_by: 'field-supervisor-001',
    },
    status: 'draft',
  });
  console.log(`  Attestation created: ${attestation.id}`);

  console.log('\nWorkflow complete!');
}

main().catch(console.error);
