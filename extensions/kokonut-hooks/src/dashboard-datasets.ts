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
