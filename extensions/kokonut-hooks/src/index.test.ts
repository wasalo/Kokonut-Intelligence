import { describe, expect, it } from 'vitest';
import registerHook from './index.js';

describe('Directus hook event registration', () => {
  it('uses collection-qualified Directus item event names', () => {
    const events: string[] = [];
    const register = (event: string) => events.push(event);

    (registerHook as unknown as (hooks: Record<string, unknown>, context: unknown) => void)(
      {
        filter: register,
        action: register,
        schedule: () => undefined,
      },
      { database: {} },
    );

    expect(events.length).toBeGreaterThan(0);
    expect(events.every((event) => /^[a-z][a-z0-9_]*\.items\.(create|update)$/.test(event))).toBe(true);
    expect(events).toContain('farm_activity.items.create');
    expect(events).toContain('farm_activity.items.update');
    expect(events).toContain('harvest_event.items.create');
    expect(events).toContain('harvest_event.items.update');
  });
});
