import { createError } from '@directus/errors';

const ForbiddenDashboardQuery = createError<{ message: string }>(
  'FORBIDDEN',
  ({ message }) => message,
  403,
);

function denyLegacySqlQueryAccess(): never {
  // Do not reveal which archived field or query operation was rejected.
  throw new ForbiddenDashboardQuery({ message: 'Directus tenant access denied' });
}

function keyReferencesField(key: string, fieldName: string): boolean {
  return key.split(/[:,.]/).some((part) => part.replace(/^[+-]/, '') === fieldName);
}

function containsFieldReference(value: unknown, fieldName: string): boolean {
  if (Array.isArray(value)) return value.some((item) => containsFieldReference(item, fieldName));
  if (value === null || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, nested]) => (
    keyReferencesField(key, fieldName) || containsFieldReference(nested, fieldName)
  ));
}

function referencesField(value: unknown, fieldName: string): boolean {
  if (Array.isArray(value)) return value.some((item) => referencesField(item, fieldName));
  if (typeof value !== 'string') return false;
  return value.split(',').some((field) => (
    keyReferencesField(field.trim(), fieldName)
  ));
}

function containsAggregateFieldReference(value: unknown, fieldName: string): boolean {
  if (Array.isArray(value)) {
    return value.some((item) => containsAggregateFieldReference(item, fieldName));
  }
  if (typeof value === 'string') return referencesField(value, fieldName);
  if (value === null || typeof value !== 'object') return false;
  return Object.entries(value).some(([key, nested]) => (
    keyReferencesField(key, fieldName) || containsAggregateFieldReference(nested, fieldName)
  ));
}

/**
 * Prevent Directus query operators from using the archived SQL column as an
 * existence, ordering, or aggregate oracle. Response redaction remains a
 * separate defense for wildcard/default projections.
 */
export function denyLegacyDashboardSqlQueryAccess(query: Record<string, unknown>): void {
  if (!query || typeof query !== 'object' || Array.isArray(query)) denyLegacySqlQueryAccess();

  const fields = query.fields;
  if (referencesField(fields, 'query_sql')) denyLegacySqlQueryAccess();

  if (containsFieldReference(query.filter, 'query_sql')) denyLegacySqlQueryAccess();
  if (referencesField(query.sort, 'query_sql')) denyLegacySqlQueryAccess();
  if (referencesField(query.groupBy, 'query_sql')) denyLegacySqlQueryAccess();
  if (containsAggregateFieldReference(query.aggregate, 'query_sql')) denyLegacySqlQueryAccess();

  // Directus search is broad across collection fields; it cannot safely
  // exclude this archived column while the legacy field exists in the schema.
  if (typeof query.search === 'string' && query.search.trim() !== '') denyLegacySqlQueryAccess();
}

/** Remove archived arbitrary SQL from current Directus dashboard responses. */
export function omitLegacyDashboardQuerySql(payload: unknown): unknown {
  const omitFromItem = (item: unknown): unknown => {
    if (item === null || typeof item !== 'object' || Array.isArray(item)) return item;
    const safeItem = { ...(item as Record<string, unknown>) };
    delete safeItem.query_sql;
    return safeItem;
  };

  return Array.isArray(payload) ? payload.map(omitFromItem) : omitFromItem(payload);
}
