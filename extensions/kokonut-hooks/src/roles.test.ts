import { describe, expect, it, vi } from 'vitest';
import { resolveUserRoles } from './roles.js';

describe('Directus workflow role resolution', () => {
  it('observes role-name changes on the next authorization check', async () => {
    const names = ['Finance', 'Field Worker'];
    const database = vi.fn(() => ({
      where: vi.fn().mockReturnThis(),
      first: vi.fn().mockImplementation(async () => ({ name: names.shift() })),
    }));
    const meta = { accountability: { role: 'role-id' } };

    await expect(resolveUserRoles(database, meta)).resolves.toEqual(['finance']);
    await expect(resolveUserRoles(database, meta)).resolves.toEqual(['field_worker']);

    expect(database).toHaveBeenCalledTimes(2);
    expect(database).toHaveBeenNthCalledWith(1, 'directus_roles');
    expect(database).toHaveBeenNthCalledWith(2, 'directus_roles');
  });

  it('keeps the server-provided administrator bypass and ignores payload accountability', async () => {
    const database = vi.fn();

    await expect(resolveUserRoles(database, {
      accountability: { admin: true },
      payload: { _accountability: { role: 'privileged-role' } },
    })).resolves.toEqual(['admin']);
    await expect(resolveUserRoles(database, {
      payload: { _accountability: { role: 'privileged-role' } },
    })).resolves.toEqual([]);

    expect(database).not.toHaveBeenCalled();
  });
});
