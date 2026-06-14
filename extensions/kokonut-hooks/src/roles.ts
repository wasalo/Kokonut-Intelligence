/**
 * Directus role resolution — maps role UUIDs to normalized slugs
 * for workflow authorization checks.
 */

const ROLE_CACHE = new Map<string, { slug: string; expiresAt: number }>();

const ROLE_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/** Normalize a Directus role display name to a slug. */
export function roleNameToSlug(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, '_');
}

/**
 * Resolve the current user's role slugs from Directus accountability metadata.
 * accountability.role is a UUID; we look up directus_roles.name and slugify it.
 */
export async function resolveUserRoles(
  db: any,
  meta: Record<string, any>
): Promise<string[]> {
  const accountability = meta?.accountability || meta?.payload?._accountability;
  if (!accountability) return [];
  if (accountability.admin) return ['admin'];

  const roleId = accountability.role as string | undefined;
  if (!roleId) return [];

  const cached = ROLE_CACHE.get(roleId);
  if (cached && Date.now() < cached.expiresAt) {
    return [cached.slug];
  }

  try {
    const role = await db('directus_roles').where('id', roleId).first('name');
    if (role?.name) {
      const slug = roleNameToSlug(role.name);
      ROLE_CACHE.set(roleId, { slug, expiresAt: Date.now() + ROLE_CACHE_TTL_MS });
      return [slug];
    }
  } catch (error) {
    console.error('[Kokonut] Failed to resolve role name:', error);
  }

  return [];
}

/** Clear the role cache (useful in tests). */
export function clearRoleCache(): void {
  ROLE_CACHE.clear();
}
