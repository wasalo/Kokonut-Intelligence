import { afterEach, describe, expect, it, vi } from 'vitest';

describe('KokonutClient REST transport boundary', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('serializes extra Directus list options through the pinned SDK without networking', async () => {
    vi.resetModules();
    const requests: Array<{ url: string; method: string }> = [];
    const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      requests.push({ url: String(input), method: init?.method ?? 'GET' });
      return new Response(JSON.stringify({ data: [{ id: 'event-1' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchStub);

    const { KokonutClient } = await import('../client.js');
    const client = new KokonutClient('https://directus.invalid');
    const rows = await client.listItems('harvest_event', {
      search: 'coconut',
      aggregate: { count: '*' },
      deep: { location_id: { _filter: { status: { _eq: 'published' } } } },
      fields: ['id', 'location_id'],
      limit: 25,
      offset: 10,
      page: 3,
    });

    expect(rows).toEqual([{ id: 'event-1' }]);
    expect(fetchStub).toHaveBeenCalledTimes(1);
    expect(requests[0]?.method).toBe('GET');

    const query = new URL(requests[0]!.url).searchParams;
    expect(query.get('search')).toBe('coconut');
    expect(query.get('aggregate')).toBe(JSON.stringify({ count: '*' }));
    expect(query.get('deep')).toBe(
      JSON.stringify({ location_id: { _filter: { status: { _eq: 'published' } } } }),
    );
    expect(query.get('fields')).toBe('id,location_id');
    expect(query.get('limit')).toBe('25');
    expect(query.get('offset')).toBe('10');
    expect(query.has('page')).toBe(false);
  });
});
