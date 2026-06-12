/**
 * Example: Upload sensor readings in batch and run anomaly detection.
 *
 * Usage:
 *   npx tsx examples/sensor-data.ts
 */

import { KokonutClient } from '../src/index.js';

const client = new KokonutClient('http://localhost:8055', {
  token: process.env.KOKONUT_TOKEN,
});

interface SensorPayload {
  sensor_device_id: string;
  plot_id?: string;
  reading_date: string;
  value: number;
  unit: string;
}

function detectAnomaly(readings: SensorPayload[], windowSize = 5): boolean[] {
  return readings.map((_, i) => {
    if (i < windowSize) return false;
    const window = readings.slice(i - windowSize, i).map((r) => r.value);
    const mean = window.reduce((a, b) => a + b, 0) / window.length;
    const std = Math.sqrt(window.reduce((s, v) => s + (v - mean) ** 2, 0) / window.length);
    const zScore = std > 0 ? Math.abs(readings[i].value - mean) / std : 0;
    return zScore > 2.5;
  });
}

async function main() {
  await client.login('admin@example.com', 'password123');

  const deviceId = 'sensor-plot-a-001';
  const plotId = 'plot-a-id';

  const now = new Date();
  const readings: SensorPayload[] = Array.from({ length: 24 }, (_, i) => {
    const ts = new Date(now.getTime() - (23 - i) * 3600000);
    return {
      sensor_device_id: deviceId,
      plot_id: plotId,
      reading_date: ts.toISOString(),
      value: 22 + Math.random() * 3 + (i === 20 ? 15 : 0),
      unit: '°C',
    };
  });

  const anomalies = detectAnomaly(readings);

  const sensorRecords = readings.map((r, i) => ({
    ...r,
    quality: 'good' as const,
    anomaly_flag: anomalies[i],
    anomaly_score: anomalies[i] ? 3.0 + Math.random() * 2 : Math.random() * 0.5,
  }));

  const created = await client.sensorReadings.createMany(sensorRecords);
  console.log(`Uploaded ${created.length} sensor readings`);

  const anomalyReadings = created.filter((r: any) => r.anomaly_flag);
  console.log(`Detected ${anomalyReadings.length} anomalies`);

  for (const anom of anomalyReadings) {
    console.log(`  ${anom.reading_date}: ${anom.value}${anom.unit} (score: ${anom.anomaly_score?.toFixed(2)})`);
  }

  const recentAnomalies = await client.sensorReadings.listAnomalies({
    sort: ['-reading_date'],
    limit: 10,
  });
  console.log(`\nRecent anomalies from DB: ${recentAnomalies.length}`);
  for (const a of recentAnomalies) {
    console.log(`  ${a.reading_date} device=${a.sensor_device_id}: ${a.value}${a.unit}`);
  }
}

main().catch(console.error);
