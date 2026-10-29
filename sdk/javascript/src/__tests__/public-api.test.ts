import { describe, expect, it, vi } from 'vitest';
import { KokonutPublicApiClient, PublicApiError } from '../public-api.js';
import type { PublicFetch, PublicFetchResponse } from '../public-api.js';

const location = {
  id: 'a0000000-0000-4000-8000-000000000001',
  name: 'Kokonut Adelphi',
  country: 'DO',
  region: 'Samaná',
  status: 'active' as const,
};
const crispAssessment = {
  assessment_id: 'b0000000-0000-4000-8000-000000000001',
  location_id: location.id,
  period_start: '2026-01-01',
  period_end: '2026-06-30',
  methodology_version: 'crisp-1',
  composite_score: 82,
  rating: 'AA',
  confidence_level: 'high',
  evidence_maturity_level: 3,
  score_computed_at: '2026-10-14T12:35:00+00:00',
  status: 'published',
};
const metricSummary = {
  location_id: location.id,
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
};
const locationSummary = {
  summary_type: 'public_location_summary',
  location_id: location.id,
  location,
  metrics: { metric_count: 1, latest_computed_at: '2026-10-14T12:30:00Z' },
  attestations: {
    total_attestations: 2,
    published_count: 2,
    latest_attestation: '2026-10-14T12:35:00+00:00',
  },
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
        response(200, { data: metricSummary }),
      )
      .mockResolvedValueOnce(
        response(200, {
          data: {
            ...crispAssessment,
          },
        }),
      )
      .mockResolvedValueOnce(
        response(200, { data: locationSummary }),
      );

    const client = new KokonutPublicApiClient('https://gateway.example///', {
      apiKey: 'test-key',
      fetch,
    });

    const locations = await client.locations.list();
    const detail = await client.locations.get(location.id);
    const metrics = await client.metrics.get(location.id);
    const crisp = await client.crisp.get(location.id);
    const summary = await client.analytics.getSummary(location.id);

    expect(locations).toEqual([location]);
    expect(detail).toEqual(location);
    expect(metrics.computed[0]?.value).toBe(12.5);
    expect(crisp.status).toBe('published');
    expect(summary.attestations.published_count).toBe(2);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      'https://gateway.example/api/v1/locations',
      `https://gateway.example/api/v1/locations/${location.id}`,
      `https://gateway.example/api/v1/metrics/${location.id}`,
      `https://gateway.example/api/v1/crisp/${location.id}`,
      `https://gateway.example/api/v1/analytics/${location.id}/summary`,
    ]);
    expect(fetch.mock.calls.every(([, init]) => init.headers.Accept === 'application/json')).toBe(true);
    expect(fetch.mock.calls.every(([, init]) => init.headers['x-api-key'] === 'test-key')).toBe(true);
    expect(fetch.mock.calls.every(([, init]) => init.signal !== undefined)).toBe(true);
  });

  it.each([
    metricSummary,
    { ...metricSummary, computed: [], total_computed: 0 },
    {
      ...metricSummary,
      computed: [
        {
          ...metricSummary.computed[0],
          unit: null,
          value: null,
          computed_at: null,
        },
      ],
    },
    {
      ...metricSummary,
      computed: [{ ...metricSummary.computed[0], unit: null, value: -2.5 }],
    },
  ])('accepts exact scoped metric summaries', async (summary) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: summary }));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.metrics.get(location.id)).resolves.toMatchObject({
      location_id: location.id,
      total_computed: summary.computed.length,
    });
  });

  it.each([
    { ...metricSummary, unexpected: 'field' },
    Object.fromEntries(Object.entries(metricSummary).filter(([key]) => key !== 'total_computed')),
    { ...metricSummary, location_id: 'not-a-uuid' },
    { ...metricSummary, location_id: 'c0000000-0000-4000-8000-000000000001' },
    { ...metricSummary, computed: {} },
    { ...metricSummary, total_computed: -1 },
    { ...metricSummary, total_computed: 1.5 },
    { ...metricSummary, total_computed: true },
    { ...metricSummary, total_computed: 0 },
    {
      ...metricSummary,
      computed: [{ ...metricSummary.computed[0], extra: 'field' }],
    },
    {
      ...metricSummary,
      computed: [
        Object.fromEntries(
          Object.entries(metricSummary.computed[0]).filter(([key]) => key !== 'unit'),
        ),
      ],
    },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], metric_key: 1 }] },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], display_name: null }] },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], unit: 4 }] },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], value: true }] },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], value: Number.POSITIVE_INFINITY }] },
    { ...metricSummary, computed: [{ ...metricSummary.computed[0], value: '12.5' }] },
    {
      ...metricSummary,
      computed: [{ ...metricSummary.computed[0], computed_at: '2026-10-14T12:30:00' }],
    },
    {
      ...metricSummary,
      computed: [{ ...metricSummary.computed[0], computed_at: '2026-02-30T12:30:00Z' }],
    },
    {
      ...metricSummary,
      computed: [{ ...metricSummary.computed[0], computed_at: '2026-10-14T12:30:00+01:60' }],
    },
  ])('rejects malformed or wrong-scope metric summaries', async (summary) => {
    const mockResponse = response(200, { data: summary });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.metrics.get(location.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it.each([
    locationSummary,
    {
      ...locationSummary,
      location: { ...location, country: null, region: null },
      metrics: { metric_count: 0, latest_computed_at: null },
      attestations: {
        total_attestations: 1,
        published_count: 1,
        latest_attestation: null,
      },
    },
    {
      ...locationSummary,
      attestations: {
        total_attestations: 2,
        published_count: 1,
        latest_attestation: '2026-10-14T12:35:00+00:00',
      },
    },
  ])('accepts exact scoped location summaries with consistent counts', async (summary) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: summary }));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.analytics.getSummary(location.id)).resolves.toMatchObject({
      location_id: location.id,
      location: { id: location.id },
      attestations: { published_count: summary.attestations.published_count },
    });
  });

  it.each([
    { ...locationSummary, unexpected: 'field' },
    Object.fromEntries(Object.entries(locationSummary).filter(([key]) => key !== 'summary_type')),
    { ...locationSummary, summary_type: 'other' },
    { ...locationSummary, location_id: 'not-a-uuid' },
    { ...locationSummary, location_id: 'c0000000-0000-4000-8000-000000000001' },
    {
      ...locationSummary,
      location: { ...location, id: 'c0000000-0000-4000-8000-000000000001' },
    },
    { ...locationSummary, location: { ...location, status: 'draft' } },
    {
      ...locationSummary,
      location: Object.fromEntries(
        Object.entries(location).filter(([key]) => key !== 'region'),
      ),
    },
    { ...locationSummary, location: { ...location, extra: 'field' } },
    {
      ...locationSummary,
      metrics: Object.fromEntries(
        Object.entries(locationSummary.metrics).filter(([key]) => key !== 'latest_computed_at'),
      ),
    },
    { ...locationSummary, metrics: { ...locationSummary.metrics, extra: 'field' } },
    { ...locationSummary, metrics: { metric_count: -1, latest_computed_at: null } },
    { ...locationSummary, metrics: { metric_count: true, latest_computed_at: null } },
    { ...locationSummary, metrics: { metric_count: 1.5, latest_computed_at: null } },
    {
      ...locationSummary,
      metrics: { metric_count: 0, latest_computed_at: '2026-10-14T12:30:00Z' },
    },
    { ...locationSummary, metrics: { metric_count: 1, latest_computed_at: null } },
    {
      ...locationSummary,
      metrics: { metric_count: 1, latest_computed_at: '2026-10-14T12:30:00' },
    },
    {
      ...locationSummary,
      attestations: Object.fromEntries(
        Object.entries(locationSummary.attestations).filter(([key]) => key !== 'published_count'),
      ),
    },
    { ...locationSummary, attestations: { ...locationSummary.attestations, extra: 'field' } },
    {
      ...locationSummary,
      attestations: { ...locationSummary.attestations, total_attestations: -1 },
    },
    {
      ...locationSummary,
      attestations: { ...locationSummary.attestations, published_count: true },
    },
    {
      ...locationSummary,
      attestations: { total_attestations: 1, published_count: 2, latest_attestation: null },
    },
    {
      ...locationSummary,
      attestations: {
        ...locationSummary.attestations,
        latest_attestation: '2026-10-14T12:35:00+01:60',
      },
    },
  ])('rejects malformed or wrong-scope location summaries', async (summary) => {
    const mockResponse = response(200, { data: summary });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.analytics.getSummary(location.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it.each([
    crispAssessment,
    {
      ...crispAssessment,
      composite_score: null,
      rating: null,
      confidence_level: null,
      evidence_maturity_level: null,
      score_computed_at: null,
    },
    { ...crispAssessment, composite_score: 0 },
    { ...crispAssessment, composite_score: 100 },
    { ...crispAssessment, evidence_maturity_level: 0 },
    { ...crispAssessment, evidence_maturity_level: 6 },
    { ...crispAssessment, score_computed_at: '2026-10-14T12:35:00.123456Z' },
    { ...crispAssessment, score_computed_at: '2026-10-14T12:35:00-05:30' },
  ])('accepts valid scoped CRISP assessments', async (assessment) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: assessment }));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.crisp.get(location.id)).resolves.toMatchObject({
      assessment_id: crispAssessment.assessment_id,
      location_id: location.id,
      status: 'published',
    });
  });

  it('normalizes UUID case when binding a CRISP response to its requested location', async () => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(
      response(200, { data: crispAssessment }),
    );
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.crisp.get(location.id.toUpperCase())).resolves.toMatchObject({
      location_id: location.id,
    });
    expect(fetch.mock.calls[0]?.[0]).toBe(
      `https://gateway.example/api/v1/crisp/${location.id.toUpperCase()}`,
    );
  });

  it.each([
    { ...crispAssessment, unexpected: 'field' },
    Object.fromEntries(
      Object.entries(crispAssessment).filter(([key]) => key !== 'status'),
    ),
    { ...crispAssessment, assessment_id: 'assessment-1' },
    { ...crispAssessment, location_id: 'not-a-uuid' },
    { ...crispAssessment, location_id: 'c0000000-0000-4000-8000-000000000001' },
    { ...crispAssessment, period_start: '2026-02-30' },
    { ...crispAssessment, period_end: 20260630 },
    { ...crispAssessment, methodology_version: 1 },
    { ...crispAssessment, composite_score: -0.01 },
    { ...crispAssessment, composite_score: 100.01 },
    { ...crispAssessment, composite_score: true },
    { ...crispAssessment, composite_score: Number.NaN },
    { ...crispAssessment, rating: 'F' },
    { ...crispAssessment, rating: [] },
    { ...crispAssessment, confidence_level: 'certain' },
    { ...crispAssessment, confidence_level: 1 },
    { ...crispAssessment, evidence_maturity_level: 1.5 },
    { ...crispAssessment, evidence_maturity_level: true },
    { ...crispAssessment, evidence_maturity_level: -1 },
    { ...crispAssessment, evidence_maturity_level: 7 },
    { ...crispAssessment, score_computed_at: '2026-10-14T12:35:00' },
    { ...crispAssessment, score_computed_at: '2026-02-30T12:35:00Z' },
    { ...crispAssessment, score_computed_at: '2026-10-14 12:35:00Z' },
    { ...crispAssessment, score_computed_at: '2026-10-14T12:35:00+25:00' },
    { ...crispAssessment, score_computed_at: '2026-10-14T12:35:00+01:60' },
    { ...crispAssessment, status: 'verified' },
  ])('rejects malformed or wrong-scope CRISP assessments', async (assessment) => {
    const mockResponse = response(200, { data: assessment });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.crisp.get(location.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it('rejects a malformed requested location UUID for CRISP response binding', async () => {
    const mockResponse = response(200, { data: crispAssessment });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.crisp.get('location-1').catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it('lists the bounded public driver catalog through the generated v1 route', async () => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(
      response(200, {
        data: {
          drivers: [
            {
              driver_name: 'weather_openweathermap',
              driver_version: '1.2.0',
              driver_type: 'weather',
            },
          ],
          limit: 1,
          offset: 12,
          has_more: true,
        },
      }),
    );
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.drivers.list({ limit: 1, offset: 12 })).resolves.toEqual({
      drivers: [
        {
          driver_name: 'weather_openweathermap',
          driver_version: '1.2.0',
          driver_type: 'weather',
        },
      ],
      limit: 1,
      offset: 12,
      has_more: true,
    });
    expect(fetch.mock.calls[0]?.[0]).toBe(
      'https://gateway.example/api/v1/drivers?limit=1&offset=12',
    );
  });

  it.each([
    { drivers: [], limit: 7, offset: 12, has_more: 'false' },
    {
      drivers: [{ driver_name: 'weather', driver_version: '1', driver_type: 'weather' }],
      limit: 7,
      offset: 12,
      has_more: true,
    },
    { drivers: [], limit: true, offset: 12, has_more: false },
    { drivers: [], limit: 7, offset: 5001, has_more: false },
    { drivers: [], limit: 7, offset: 13, has_more: false },
    { drivers: [], limit: 7, offset: 12, has_more: false, debug: 'extra' },
    {
      drivers: [{ driver_name: 'weather', driver_version: '1', driver_type: 'unknown' }],
      limit: 7,
      offset: 12,
      has_more: false,
    },
    {
      drivers: [{ driver_name: 4, driver_version: '1', driver_type: 'weather' }],
      limit: 7,
      offset: 12,
      has_more: false,
    },
    {
      drivers: [{ driver_name: 'weather', driver_version: '1', driver_type: [] }],
      limit: 7,
      offset: 12,
      has_more: false,
    },
    {
      drivers: [
        {
          driver_name: 'weather',
          driver_version: '1',
          driver_type: 'weather',
          private: 'extra',
        },
      ],
      limit: 7,
      offset: 12,
      has_more: false,
    },
    {
      drivers: [{ driver_name: 'w'.repeat(101), driver_version: '1', driver_type: 'weather' }],
      limit: 7,
      offset: 12,
      has_more: false,
    },
    {
      drivers: [{ driver_name: 'weather', driver_version: 'v'.repeat(21), driver_type: 'weather' }],
      limit: 7,
      offset: 12,
      has_more: false,
    },
  ])('rejects malformed driver catalog payloads', async (catalog) => {
    const mockResponse = response(200, { data: catalog });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    const error = await client.drivers.list({ limit: 7, offset: 12 }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it('rejects more when the next driver page exceeds the offset bound', async () => {
    const driver = {
      driver_name: 'weather',
      driver_version: '1',
      driver_type: 'weather',
    };
    const mockResponse = response(200, {
      data: {
        drivers: Array.from({ length: 7 }, () => ({ ...driver })),
        limit: 7,
        offset: 4994,
        has_more: true,
      },
    });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    const error = await client.drivers.list({ limit: 7, offset: 4994 }).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it.each([
    [0, 0],
    [51, 0],
    [1.5, 0],
    [1, -1],
    [1, 5001],
    [1, 0.5],
  ])('rejects invalid driver catalog page %s/%s before transport', (limit, offset) => {
    const fetch = vi.fn<PublicFetch>();
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    expect(() => client.drivers.list({ limit, offset })).toThrow(RangeError);
    expect(fetch).not.toHaveBeenCalled();
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
    [response(400, { error: 'Invalid location identifier' }), 'Invalid location identifier', 400],
    [response(400, { error: 'invalid', debug: 'extra' }), 'HTTP 400', 400],
    [response(400, { error: 7 }), 'HTTP 400', 400],
    [
      response(422, { detail: [{ loc: ['query', 'limit'], msg: 'Input should be >= 1' }] }),
      'HTTP 422',
      422,
    ],
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
    response(403, { error: 'scope denied' }),
    response(400, { error: 'invalid', debug: 'extra' }),
    response(422, {
      detail: [{ loc: ['query', 'limit'], msg: 'Input should be >= 1' }],
    }),
    response(502, undefined, true),
    response(200, { data: null }),
  ])('preserves the transport response on API errors', async (mockResponse) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    const error = await client.locations.list().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it.each([
    ['list', { data: location }],
    ['get', { data: [location] }],
  ])('rejects the wrong top-level data shape for %s', async (method, payload) => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, payload));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const result = method === 'get' ? client.locations.get(location.id) : client.locations.list();

    await expect(result).rejects.toMatchObject({
      name: 'PublicApiError',
      message: 'Invalid public API response envelope',
      statusCode: 200,
    } satisfies Partial<PublicApiError>);
  });

  it.each(['list', 'get'] as const)(
    'accepts an exact location with nullable fields in %s responses',
    async (method) => {
      const nullableLocation = { ...location, country: null, region: null };
      const fetch = vi.fn<PublicFetch>().mockResolvedValue(
        response(200, { data: method === 'list' ? [nullableLocation] : nullableLocation }),
      );
      const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
      const result =
        method === 'list'
          ? await client.locations.list()
          : await client.locations.get(location.id);

      expect(result).toEqual(method === 'list' ? [nullableLocation] : nullableLocation);
    },
  );

  it('binds location detail responses to the requested UUID after case normalization', async () => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: location }));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.locations.get(location.id.toUpperCase())).resolves.toEqual(location);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      `https://gateway.example/api/v1/locations/${location.id.toUpperCase()}`,
    );
  });

  it('rejects a valid-shaped location detail with a different requested UUID', async () => {
    const mockResponse = response(200, {
      data: { ...location, id: 'c0000000-0000-4000-8000-000000000001' },
    });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.locations.get(location.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it('requires exact data-only success envelopes', async () => {
    const mockResponse = response(200, { data: location, debug: 'unexpected' });
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
    const error = await client.locations.get(location.id).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(PublicApiError);
    expect(error).toMatchObject({
      message: 'Invalid public API response envelope',
      statusCode: 200,
    });
    expect((error as PublicApiError).response).toBe(mockResponse);
  });

  it('continues to encode path segments for location detail requests', async () => {
    const fetch = vi.fn<PublicFetch>().mockResolvedValue(response(200, { data: location }));
    const client = new KokonutPublicApiClient('https://gateway.example', { fetch });

    await expect(client.locations.get('a/b +?')).rejects.toBeInstanceOf(PublicApiError);
    expect(fetch.mock.calls[0]?.[0]).toBe(
      'https://gateway.example/api/v1/locations/a%2Fb%20%2B%3F',
    );
  });

  it.each(['list', 'get'] as const)(
    'rejects malformed location rows in %s responses',
    async (method) => {
      const malformedLocations: unknown[] = [
        { ...location, id: 'not-a-uuid' },
        { ...location, name: 4 },
        { ...location, country: 4 },
        { ...location, region: [] },
        { ...location, status: 'published' },
        {
          id: location.id,
          name: location.name,
          country: location.country,
          status: location.status,
        },
        { ...location, unexpected: 'field' },
      ];

      for (const malformedLocation of malformedLocations) {
        const mockResponse = response(200, {
          data: method === 'list' ? [malformedLocation] : malformedLocation,
        });
        const fetch = vi.fn<PublicFetch>().mockResolvedValue(mockResponse);
        const client = new KokonutPublicApiClient('https://gateway.example', { fetch });
        const result =
          method === 'list'
            ? client.locations.list()
            : client.locations.get(location.id);
        const error = await result.catch((caught: unknown) => caught);

        expect(error).toBeInstanceOf(PublicApiError);
        expect(error).toMatchObject({
          message: 'Invalid public API response envelope',
          statusCode: 200,
        });
        expect((error as PublicApiError).response).toBe(mockResponse);
      }
    },
  );
});
