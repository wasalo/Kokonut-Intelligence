import { describe, expect, it } from 'vitest';
import {
  denyLegacyDashboardSqlQueryAccess,
  omitLegacyDashboardQuerySql,
} from './dashboard-datasets.js';

describe('Directus dashboard dataset query fields', () => {
  it.each([
    ['explicit fields', { fields: ['id', 'query_sql'] }],
    ['aliased fields', { fields: ['archived_sql:query_sql'] }],
    ['filter', { filter: { query_sql: { _contains: 'private' } } }],
    ['nested filter', { filter: { _or: [{ query_sql: { _contains: 'private' } }] } }],
    ['qualified filter', { filter: { 'dashboard_dataset.query_sql': { _contains: 'private' } } }],
    ['sort', { sort: ['-query_sql'] }],
    ['grouping', { groupBy: ['query_sql'] }],
    ['aggregate', { aggregate: { countDistinct: ['query_sql'] } }],
    ['broad search', { search: 'private_schema' }],
  ])('denies %s access to archived SQL', (_caseName, query) => {
    let thrown: unknown;
    try {
      denyLegacyDashboardSqlQueryAccess(query);
    } catch (error) {
      thrown = error;
    }
    expect(thrown).toMatchObject({
      code: 'FORBIDDEN',
      status: 403,
      message: 'Directus tenant access denied',
    });
  });

  it('keeps ordinary metadata queries and wildcard reads available for response redaction', () => {
    expect(() => denyLegacyDashboardSqlQueryAccess({
      fields: ['id', 'name', 'query_id'],
      filter: { status: { _eq: 'published' } },
      sort: ['name'],
    })).not.toThrow();
    expect(() => denyLegacyDashboardSqlQueryAccess({ fields: ['*'] })).not.toThrow();
    expect(() => denyLegacyDashboardSqlQueryAccess({})).not.toThrow();
  });
});

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
