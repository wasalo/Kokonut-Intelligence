import { describe, expect, it, vi } from 'vitest';
import { KokonutPublicApiClient, PublicApiError } from '../public-api.js';
import type { PublicFetch, PublicFetchResponse } from '../public-api.js';

const location = {
  id: 'location-1',
  name: 'Kokonut Adelphi',
  country: 'DO',
  region: 'Samaná',
  status: 'active' as const,
};

function response(status: number, payload?: unknown, invalidJson = false): PublicFetchResponse {
  return {
    ok: status >= 200 && status < 400,
    status,
    json: async () => {
      if (invalidJson) throw new Error('invalid json');
      return payload;
    },
  };
}

describe('KokonutPublicApiClient', () => {
  it('uses the shared v1 paths and returns typed payloads for all five reads', async () => {
    const fetch = vi.fn<PublicFetch>();
    fetch
      .mockResolvedValueOnce(response(200, { data: [location] }))
      .mockResolvedValueOnce(response(200, { data: location }))
      .mockResolvedValueOnce(
        response(200, {
          data: {
            location_id: 'location-1',
            computed: [
              {
                metric_key: 'soil_carbon',
                display_name: 'Soil carbon',
                unit: 't/ha',
                value: 12.5,
                computed_at: '2026-10-14T12:30:00Z',
              },
            ],
            total_computed: 1,
          },
        }),
      )
      .mockResolvedValueOnce(
        response(200, {
          data: {
            assessment_id: 'assessment-1',
            location_id: 'location-1',
            period_start: '2026-01-01',
            period_end: '2026-06-30',
            methodology_version: 'crisp-1',
            composite_score: 82,
            rating: 'AA',
            confidence_level: 'high',
            evidence_maturity_level: 3,
            score_computed_at: '2026-10-14T12:35:00+00:00',
            status: 'published',
          },
        }),
      )
      .mockResolvedValueOnce(
        response(200, {
          data: {
            summary_type: 'public_location_summary',
            location_id: 'location-1',
            location,
            metrics: {
              metric_count: 1,
              latest_computed_at: '2026-10-14T12:30:00Z',
            },
            attestations: {
              total_attestations: 2,
              published_count: 2,
              latest_attestation: '2026-10-14T12:35:00+00:00',
            },
          },
        }),
      );

    const client = new KokonutPublicApiClient('https://gateway.example///', {
      apiKey: 'test-key',
      fetch,
    });

    const locations = await client.locations.list();
    const detail = await client.locations.get('a/b +?');
    const metrics = await client.metrics.get('location-1');
    const crisp = await client.crisp.get('location-1');
    const summary = await client.analytics.getSummary('location-1');

    expect(locations).toEqual([location]);
    expect(detail).toEqual(location);
    expect(metrics.computed[0]?.value).toBe(12.5);
    expect(crisp.status).toBe('published');
    expect(summary.attestations.published_count).toBe(2);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      'https://gateway.example/api/v1/locations',
      'https://gateway.example/api/v1/locations/a%2Fb%20%2B%3F',
      'https://gateway.example/api/v1/metrics/location-1',
      'https://gateway.example/api/v1/crisp/location-1',
      'https://gateway.example/api/v1/analytics/location-1/summary',
    ]);
    expect(fetch.mock.calls.every(([, init]) => init.headers.Accept === 'application/json')).toBe(true);
    expect(fetch.mock.calls.every(([, init]) => init.headers['x-api-key'] === 'test-key')).toBe(true);
    expect(fetch.mock.calls.every(([, init]) => init.signal !== undefined)).toBe(true);
  });

  it('defaults to the Python SDK 10-second deadline and aborts a stalled fetch', async () => {
    vi.useFakeTimers();
    try {
      const fetch = vi.fn<PublicFetch>((_input, init) => new Promise((_resolve, reject) => {
        init.signal?.addEventListener('abort', () => reject(new Error('request aborted')));
      }));
      const client = new KokonutPublicApiClient('https://gateway.example', {
        fetch,
      });

      const request = client.locations.list();
      const aborted = expect(request).rejects.toThrow('request aborted');
      await vi.advanceTimersByTimeAsync(9_999);
      expect(fetch.mock.calls[0]?.[1].signal?.aborted).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      await aborted;
      expect(fetch.mock.calls[0]?.[1].signal?.aborted).toBe(true);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, 2_147_483_648])(
    'rejects invalid timeoutMs %s',
    (timeoutMs) => {
      expect(
        () => new KokonutPublicApiClient('https://gateway.example', { timeoutMs }),
      ).toThrow('timeoutMs must be finite and between 0 and 2147483647 milliseconds');
    },
  );

  it('rejects an explicitly null timeout instead of treating it as omitted', () => {
    expect(
      () =>
        new KokonutPublicApiClient('https://gateway.example', {
          timeoutMs: null as unknown as number,
        }),
    ).toThrow('timeoutMs must be finite and between 0 and 2147483647 milliseconds');
  });

  it('accepts the largest delay supported by browser and Node timers', () => {
    expect(
      () => new KokonutPublicApiClient('https://gateway.example', { timeoutMs: 2_147_483_647 }),
    ).not.toThrow();
  });

  it('clears the deadline timer after a successful response', async () => {
    vi.useFakeTimers();
    try {
      const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: [location] }));
      const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

      await expect(client.locations.list()).resolves.toEqual([location]);
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it('clears the deadline timer after a fetch failure', async () => {
    vi.useFakeTimers();
    try {
      const fetch = vi.fn<PublicFetch>().mockRejectedValue(new Error('network failure'));
      const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

      await expect(client.locations.list()).rejects.toThrow('network failure');
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    [response(403, { error: 'scope denied' }), 'scope denied', 403],
    [response(502, { unexpected: true }), 'HTTP 502', 502],
    [response(502, undefined, true), 'HTTP 502', 502],
    [response(200, undefined, true), 'Invalid JSON response from Kokonut Gateway', 200],
    [response(200, { data: null }), 'Invalid public API response envelope', 200],
  ])('normalizes API errors', async (mockResponse, message, status) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse as PublicFetchResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.locations.list()).rejects.toMatchObject({
      name: 'PublicApiError',
      message,
      statusCode: status,
    } satisfies Partial<PublicApiError>);
  });

  it.each([
    ['list', { data: location }],
    ['get', { data: [location] }],
  ])('rejects the wrong top-level data shape for %s', async (method, payload) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, payload));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const result = method === 'get' ? client.locations.get('location-1') : client.locations.list();

    await expect(result).rejects.toMatchObject({
      name: 'PublicApiError',
      message: 'Invalid public API response envelope',
      statusCode: 200,
    } satisfies Partial<PublicApiError>);
  });
});
