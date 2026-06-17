/**
 * Pagination and Error Handling Examples
 *
 * Demonstrates page-based pagination, offset pagination,
 * and error handling patterns with the Kokonut JS/TS SDK.
 *
 * Usage:
 *   KOKONUT_API_URL=http://localhost:8055 \
 *   KOKONUT_EMAIL=field@kokonut.local \
 *   KOKONUT_PASSWORD=field1234 \
 *   npx tsx sdk/javascript/examples/pagination-and-errors.ts
 */

import { KokonutClient, ListOptions } from '../src/index.js';

async function main() {
  const client = new KokonutClient(
    process.env.KOKONUT_API_URL || 'http://localhost:8055'
  );

  // --- Authentication with error handling ---
  const email = process.env.KOKONUT_EMAIL || 'field@kokonut.local';
  const password = process.env.KOKONUT_PASSWORD || 'field1234';

  try {
    await client.login(email, password);
    console.log(`Logged in as ${email}`);
  } catch (e: any) {
    console.error(`Authentication failed: ${e.message}`);
    return;
  }

  // --- Page-based pagination ---
  console.log('\n--- Page-based Pagination (Locations) ---');
  let page = 1;
  const pageSize = 5;
  const allLocations: any[] = [];

  while (true) {
    try {
      const locations = await client.locations.list({
        page,
        limit: pageSize,
        sort: ['name'],
        meta: 'total_count',
      } as ListOptions);

      if (!locations || locations.length === 0) break;

      allLocations.push(...locations);
      console.log(`  Page ${page}: ${locations.length} locations`);

      if (locations.length < pageSize) break;
      page++;
    } catch (e: any) {
      console.error(`  Error on page ${page}: ${e.message}`);
      break;
    }
  }

  console.log(`  Total: ${allLocations.length} locations`);

  // --- Offset-based pagination (harvest events) ---
  console.log('\n--- Offset-based Pagination (Harvest Events) ---');
  let offset = 0;
  const limit = 10;
  let totalFetched = 0;

  while (true) {
    try {
      const events = await client.harvestEvents.list({
        offset,
        limit,
        sort: ['-harvest_date'],
      } as ListOptions);

      if (!events || events.length === 0) break;

      for (const event of events) {
        totalFetched++;
        console.log(`  ${event.harvest_date}: ${event.quantity} ${event.unit}`);
      }

      if (events.length < limit) break;
      offset += limit;
    } catch (e: any) {
      console.error(`  Error at offset ${offset}: ${e.message}`);
      break;
    }
  }

  console.log(`  Total fetched: ${totalFetched}`);

  // --- Filter with error handling ---
  console.log('\n--- Filtered Query (Pending Sales) ---');
  try {
    const pendingSales = await client.salesEvents.list({
      filter: { payment_status: { _eq: 'pending' } },
      sort: ['-sale_date'],
      limit: 5,
    } as ListOptions);

    for (const sale of pendingSales) {
      console.log(`  ${sale.sale_date}: $${sale.total_amount} (${sale.payment_status})`);
    }
  } catch (e: any) {
    console.error(`  Error: ${e.message}`);
  }

  // --- Create with validation error handling ---
  console.log('\n--- Create with Error Handling ---');
  try {
    const newLocation = await client.locations.create({
      name: 'Test Pagination Farm',
      slug: 'test-pagination-farm-ts',
      country: 'Costa Rica',
      status: 'active',
    });
    console.log(`  Created: ${newLocation.name} (${newLocation.id})`);

    // Try duplicate (should fail gracefully)
    try {
      await client.locations.create({
        name: 'Test Pagination Farm',
        slug: 'test-pagination-farm-ts',
        country: 'Costa Rica',
        status: 'active',
      });
    } catch (e: any) {
      console.log(`  Duplicate slug caught: ${e.message}`);
    }
  } catch (e: any) {
    console.error(`  Create error: ${e.message}`);
  }

  // --- Generic error handler ---
  console.log('\n--- Generic Error Handling Pattern ---');
  try {
    const locations = await client.locations.list({ limit: 3 } as ListOptions);
    console.log(`  Fetched ${locations.length} locations`);
  } catch (e: any) {
    if (e.message?.includes('401')) {
      console.error('  Session expired. Re-login required.');
    } else if (e.message?.includes('403')) {
      console.error('  Insufficient permissions.');
    } else if (e.message?.includes('404')) {
      console.error('  Resource not found.');
    } else {
      console.error(`  API error: ${e.message}`);
    }
  }

  console.log('\nDone.');
}

main();
