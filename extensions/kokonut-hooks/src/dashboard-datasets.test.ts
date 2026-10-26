import { describe, expect, it } from 'vitest';
import { omitLegacyDashboardQuerySql } from './dashboard-datasets.js';

describe('Directus dashboard dataset response fields', () => {
  it('omits archived SQL from item and page responses without mutating source records', () => {
    const first = {
      id: 'dataset-1',
      query_id: 'public_farm_summary_count',
      query_sql: 'SELECT secret_schema.private_data',
    };
    const second = { id: 'dataset-2', query_sql: null };

    expect(omitLegacyDashboardQuerySql(first)).toEqual({
      id: 'dataset-1',
      query_id: 'public_farm_summary_count',
    });
    expect(omitLegacyDashboardQuerySql([first, second])).toEqual([
      { id: 'dataset-1', query_id: 'public_farm_summary_count' },
      { id: 'dataset-2' },
    ]);
    expect(first.query_sql).toBe('SELECT secret_schema.private_data');
    expect(second.query_sql).toBeNull();
  });

  it('preserves null and non-object Directus read payloads', () => {
    expect(omitLegacyDashboardQuerySql(null)).toBeNull();
    expect(omitLegacyDashboardQuerySql('unchanged')).toBe('unchanged');
  });
});
