/** Typed client for the versioned native Kokonut public API. */

import { publicApiPathsV1 } from './generated/public-api-v1.js';
import type {
  PublicCrispAssessmentV1,
  PublicLocationV1,
  PublicLocationSummaryV1,
  PublicMetricSummaryV1,
} from './generated/public-api-v1.js';

export type {
  PublicAttestationCountsV1,
  PublicCrispAssessmentEnvelopeV1,
  PublicCrispAssessmentV1,
  PublicErrorV1,
  PublicLocationListResponseV1,
  PublicLocationResponseV1,
  PublicLocationSummaryEnvelopeV1,
  PublicLocationSummaryV1,
  PublicLocationV1,
  PublicMetricCountsV1,
  PublicMetricSummaryEnvelopeV1,
  PublicMetricSummaryV1,
  PublicMetricV1,
} from './generated/public-api-v1.js';

export interface PublicApiClientOptions {
  apiKey?: string;
  fetch?: PublicFetch;
}

export type PublicFetchResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type PublicFetch = (
  input: string,
  init: { headers: Record<string, string> },
) => Promise<PublicFetchResponse>;

export class PublicApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
  ) {
    super(message);
    this.name = 'PublicApiError';
  }
}

interface DataEnvelope<T> {
  data: T;
}

function encodePathSegment(value: string): string {
  return encodeURIComponent(value).replace(/[!'()*]/g, (character) =>
    `%${character.charCodeAt(0).toString(16).toUpperCase()}`,
  );
}

export class KokonutPublicApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: PublicFetch;
  private readonly apiKey?: string;

  public readonly locations: {
    list: () => Promise<PublicLocationV1[]>;
    get: (locationId: string) => Promise<PublicLocationV1>;
  };
  public readonly metrics: {
    get: (locationId: string) => Promise<PublicMetricSummaryV1>;
  };
  public readonly crisp: {
    get: (locationId: string) => Promise<PublicCrispAssessmentV1>;
  };
  public readonly analytics: {
    getSummary: (locationId: string) => Promise<PublicLocationSummaryV1>;
  };

  /**
   * `baseUrl` is the Gateway origin, for example `http://localhost:8098`.
   * It is separate from the Directus origin used by `KokonutClient`.
   */
  constructor(baseUrl: string, options: PublicApiClientOptions = {}) {
    this.baseUrl = `${baseUrl.replace(/\/+$/, '')}/api/v1`;
    const defaultFetch = (globalThis as typeof globalThis & { fetch?: PublicFetch }).fetch;
    if (!options.fetch && !defaultFetch) {
      throw new Error('KokonutPublicApiClient requires Fetch API support or a fetch implementation');
    }
    this.fetchImpl = options.fetch ?? defaultFetch!;
    this.apiKey = options.apiKey;
    this.locations = {
      list: () => this.get<PublicLocationV1[]>(publicApiPathsV1.listPublicLocationsV1, 'array'),
      get: (locationId: string) =>
        this.get<PublicLocationV1>(
          publicApiPathsV1.getPublicLocationV1.replace(
            '{location_id}',
            encodePathSegment(locationId),
          ),
          'object',
        ),
    };
    this.metrics = {
      get: (locationId: string) =>
        this.get<PublicMetricSummaryV1>(
          publicApiPathsV1.getPublicMetricSummaryV1.replace(
            '{location_id}',
            encodePathSegment(locationId),
          ),
          'object',
        ),
    };
    this.crisp = {
      get: (locationId: string) =>
        this.get<PublicCrispAssessmentV1>(
          publicApiPathsV1.getPublicCrispAssessmentV1.replace(
            '{location_id}',
            encodePathSegment(locationId),
          ),
          'object',
        ),
    };
    this.analytics = {
      getSummary: (locationId: string) =>
        this.get<PublicLocationSummaryV1>(
          publicApiPathsV1.getPublicLocationSummaryV1.replace(
            '{location_id}',
            encodePathSegment(locationId),
          ),
          'object',
        ),
    };
  }

  private async get<T>(path: string, dataShape: 'array' | 'object'): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.apiKey) headers['x-api-key'] = this.apiKey;

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, { headers });
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (!response.ok) {
        throw new PublicApiError(`HTTP ${response.status}`, response.status);
      }
      throw new PublicApiError('Invalid JSON response from Kokonut Gateway', response.status);
    }

    if (!response.ok) {
      const errorMessage =
        payload && typeof payload === 'object' && 'error' in payload
          ? payload.error
          : undefined;
      const message = typeof errorMessage === 'string' ? errorMessage : `HTTP ${response.status}`;
      throw new PublicApiError(message, response.status);
    }

    if (
      !payload ||
      typeof payload !== 'object' ||
      Array.isArray(payload) ||
      !('data' in payload)
    ) {
      throw new PublicApiError('Invalid public API response envelope', response.status);
    }
    const data = (payload as DataEnvelope<unknown>).data;
    const validData =
      dataShape === 'array'
        ? Array.isArray(data)
        : Boolean(data) && typeof data === 'object' && !Array.isArray(data);
    if (!validData) {
      throw new PublicApiError('Invalid public API response envelope', response.status);
    }
    return data as T;
  }
}
