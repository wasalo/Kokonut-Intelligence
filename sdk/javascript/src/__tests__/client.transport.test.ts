import { afterEach, describe, expect, it, vi } from 'vitest';

describe('KokonutClient REST transport boundary', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('serializes list, aggregate, and CRUD requests through the pinned SDK without networking', async () => {
    vi.resetModules();
    const requests: Array<{ url: string; method: string; body: string | null }> = [];
    const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input));
      const method = init?.method ?? 'GET';
      requests.push({
        url: url.toString(),
        method,
        body: typeof init?.body === 'string' ? init.body : null,
      });

      if (url.pathname === '/items/denied') {
        return new Response(JSON.stringify({ errors: [{ message: 'synthetic scope denial' }] }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      if (url.pathname.startsWith('/items/malformed-')) {
        const body = url.pathname.includes('/malformed-empty/')
          ? JSON.stringify({ errors: [{ message: '' }] })
          : 'not-json';
        return new Response(body, {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (method === 'DELETE') return new Response(null, { status: 204 });

      let data: unknown;
      if (
        url.pathname === '/items/harvest_event' &&
        url.searchParams.has('groupBy') &&
        !url.searchParams.has('search')
      ) {
        data = [{ location_id: 'location-1', count: { '*': 2 } }];
      } else if (url.pathname === '/items/harvest_event') {
        data = [{ id: 'event-1' }];
      } else if (method === 'GET') {
        data = { id: 'location-1', name: 'Synthetic Location' };
      } else if (method === 'PATCH') {
        data = { id: 'location-1', country: 'DO' };
      } else if (method === 'POST' && url.pathname === '/items/location') {
        data = { id: 'location-2', name: 'Synthetic Location' };
      } else if (method === 'POST' && url.pathname === '/items/farm') {
        data = [{ id: 'farm-1', name: 'Synthetic Farm' }];
      } else if (method === 'POST' && url.pathname.startsWith('/items/farm%2F')) {
        data = [];
      } else {
        throw new Error(`Unexpected Directus request: ${method} ${url.pathname}`);
      }

      return new Response(JSON.stringify({ data }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchStub);

    const { KokonutClient } = await import('../client.js');
    const { ForbiddenError, NotFoundError } = await import('../errors.js');
    const client = new KokonutClient('https://directus.invalid');
    const rows = await client.listItems('harvest_event', {
      search: 'coconut',
      aggregate: { count: '*' },
      deep: { location_id: { _filter: { status: { _eq: 'published' } } } },
      extraParams: { groupBy: ['location_id'] },
      fields: ['id', 'location_id'],
      limit: 25,
      offset: 10,
      page: 3,
    });
    const grouped = await client.aggregate('harvest_event', {
      aggregate: { count: '*' },
      groupBy: ['location_id'],
    });
    const detail = await client.getItem('location', 'location-1', ['id', 'name']);
    const created = await client.createItem('location', {
      name: 'Synthetic Location',
      slug: 'synthetic-location',
    });
    const createdBatch = await client.createItems('farm', [{ name: 'Synthetic Farm' }]);
    const updated = await client.updateItem('location', 'location-1', { country: 'DO' });
    await client.deleteItem('location', 'location-1');
    const denied = client.listItems('denied');
    await expect(denied).rejects.toBeInstanceOf(ForbiddenError);
    await expect(denied).rejects.toMatchObject({
      message: 'synthetic scope denial',
      statusCode: 403,
    });

    expect(rows).toEqual([{ id: 'event-1' }]);
    expect(grouped).toEqual([{ location_id: 'location-1', count: { '*': 2 } }]);
    expect(detail).toEqual({ id: 'location-1', name: 'Synthetic Location' });
    expect(created).toEqual({ id: 'location-2', name: 'Synthetic Location' });
    expect(createdBatch).toEqual([{ id: 'farm-1', name: 'Synthetic Farm' }]);
    expect(updated).toEqual({ id: 'location-1', country: 'DO' });
    expect(fetchStub).toHaveBeenCalledTimes(8);
    expect(requests.map((request) => request.method)).toEqual([
      'GET',
      'GET',
      'GET',
      'POST',
      'POST',
      'PATCH',
      'DELETE',
      'GET',
    ]);

    const listUrl = new URL(requests[0]!.url);
    expect(listUrl.searchParams.get('search')).toBe('coconut');
    expect(listUrl.searchParams.get('aggregate')).toBe(JSON.stringify({ count: '*' }));
    expect(listUrl.searchParams.get('deep')).toBe(
      JSON.stringify({ location_id: { _filter: { status: { _eq: 'published' } } } }),
    );
    expect(listUrl.searchParams.get('groupBy')).toBe('location_id');
    expect(listUrl.searchParams.get('fields')).toBe('id,location_id');
    expect(listUrl.searchParams.get('limit')).toBe('25');
    expect(listUrl.searchParams.get('offset')).toBe('10');
    expect(listUrl.searchParams.has('page')).toBe(false);

    const aggregateUrl = new URL(requests[1]!.url);
    expect(aggregateUrl.pathname).toBe('/items/harvest_event');
    expect(aggregateUrl.searchParams.get('aggregate')).toBe(JSON.stringify({ count: '*' }));
    expect(aggregateUrl.searchParams.get('groupBy')).toBe('location_id');

    const detailUrl = new URL(requests[2]!.url);
    expect(detailUrl.pathname).toBe('/items/location/location-1');
    expect(detailUrl.searchParams.get('fields')).toBe('id,name');
    expect(JSON.parse(requests[3]!.body ?? 'null')).toEqual({
      name: 'Synthetic Location',
      slug: 'synthetic-location',
    });
    expect(JSON.parse(requests[4]!.body ?? 'null')).toEqual([{ name: 'Synthetic Farm' }]);
    expect(new URL(requests[5]!.url).pathname).toBe('/items/location/location-1');
    expect(JSON.parse(requests[5]!.body ?? 'null')).toEqual({ country: 'DO' });
    expect(new URL(requests[6]!.url).pathname).toBe('/items/location/location-1');
    expect(requests[6]!.body).toBeNull();

    const hostileCollection = 'farm/../../auth';
    const hostileItemId = 'farm/../../auth?token=x#fragment%';
    await client.listItems(hostileCollection);
    await client.getItem('location', hostileItemId);
    await client.createItem(hostileCollection, {});
    await client.createItems(hostileCollection, []);
    await client.updateItem('location', 'farm/../../auth', {});
    await client.deleteItem('location', 'farm/../../auth');
    await client.aggregate(hostileCollection, { aggregate: { count: '*' } });

    expect(requests.slice(8).map((request) => new URL(request.url).pathname)).toEqual([
      '/items/farm%2F..%2F..%2Fauth',
      '/items/location/farm%2F..%2F..%2Fauth%3Ftoken%3Dx%23fragment%25',
      '/items/farm%2F..%2F..%2Fauth',
      '/items/farm%2F..%2F..%2Fauth',
      '/items/location/farm%2F..%2F..%2Fauth',
      '/items/location/farm%2F..%2F..%2Fauth',
      '/items/farm%2F..%2F..%2Fauth',
    ]);

    const requestCount = fetchStub.mock.calls.length;
    await expect(client.getItem('location', '..')).rejects.toThrow('path segment');
    await expect(client.listItems('')).rejects.toThrow('path segment');
    expect(fetchStub).toHaveBeenCalledTimes(requestCount);

    for (const kind of ['empty', 'invalid']) {
      const error = await client.getItem(`malformed-${kind}`, 'item').catch((caught) => caught);
      expect(error).toBeInstanceOf(NotFoundError);
      expect(error).toMatchObject({ message: 'HTTP 404', statusCode: 404 });
    }
  });

  it('forwards extension query parameters through typed location reads without weakening scope', async () => {
    vi.resetModules();
    const { KokonutClient } = await import('../client.js');
    const client = new KokonutClient('https://directus.invalid');
    const listItems = vi.spyOn(client, 'listItems').mockResolvedValue([]);
    await client.fieldNotes.listByLocation('location-1', {
      filter: { status: { _eq: 'submitted' }, location_id: { _eq: 'other-location' } },
      limit: 25,
      extraParams: {
        aggregate: { count: '*' },
        groupBy: ['location_id'],
        filter: { location_id: { _eq: 'another-location' } },
        limit: 999,
      },
    });

    expect(listItems).toHaveBeenCalledWith(
      'field_note',
      expect.objectContaining({
        extraParams: {
          aggregate: { count: '*' },
          groupBy: ['location_id'],
          filter: { location_id: { _eq: 'another-location' } },
          limit: 999,
        },
        filter: {
          status: { _eq: 'submitted' },
          location_id: { _eq: 'location-1' },
        },
        limit: 25,
      }),
    );
  });
});
