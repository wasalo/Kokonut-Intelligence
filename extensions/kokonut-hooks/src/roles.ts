/**
 * Directus role resolution — maps role UUIDs to normalized slugs
 * for workflow authorization checks.
 */
import { errorClass } from './error-safety.js';

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
  // Trust only the server-provided accountability. Client-supplied
  // `payload._accountability` is never honored (spoofing risk).
  const accountability = meta?.accountability;
  if (!accountability) return [];
  if (accountability.admin) return ['admin'];

  const roleId = accountability.role as string | undefined;
  if (!roleId) return [];

  try {
    const role = await db('directus_roles').where('id', roleId).first('name');
    if (role?.name) {
      // The role name is part of the workflow authorization policy. Resolve it
      // from the request database on each check so a rename/revocation is not
      // masked by a process-local stale authorization cache.
      return [roleNameToSlug(role.name)];
    }
  } catch (error) {
    console.error(`[Kokonut] Failed to resolve role name: ${errorClass(error)}`);
  }

  return [];
}
