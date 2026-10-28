/** Typed client for the versioned native Kokonut public API. */

import { publicApiPathsV1 } from './generated/public-api-v1.js';
import type {
  PublicCrispAssessmentV1,
  PublicDriverCatalogResponseV1,
  PublicLocationV1,
  PublicLocationSummaryV1,
  PublicMetricSummaryV1,
} from './generated/public-api-v1.js';

export type {
  PublicAttestationCountsV1,
  PublicCrispAssessmentEnvelopeV1,
  PublicCrispAssessmentV1,
  PublicDriverCatalogEntryV1,
  PublicDriverCatalogEnvelopeV1,
  PublicDriverCatalogResponseV1,
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
  /** Request deadline in milliseconds (1 through 2^31-1). Defaults to 10 seconds. */
  timeoutMs?: number;
  fetch?: PublicFetch;
}

export interface PublicDriverListOptions {
  limit?: number;
  offset?: number;
}

export type PublicFetchResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type PublicAbortSignal = {
  readonly aborted: boolean;
  addEventListener: (type: 'abort', listener: () => void) => void;
};

export type PublicFetch = (
  input: string,
  init: { headers: Record<string, string>; signal?: PublicAbortSignal },
) => Promise<PublicFetchResponse>;

type PublicAbortController = {
  signal: PublicAbortSignal;
  abort: () => void;
};

type PublicTimerHost = {
  setTimeout: (callback: () => void, timeoutMs: number) => unknown;
  clearTimeout: (timer: unknown) => void;
};

// Browser and Node timers clamp larger delays to a near-immediate timeout.
const MAX_TIMEOUT_MS = 2_147_483_647;

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
  private readonly timeoutMs: number;

  public readonly locations: {
    list: () => Promise<PublicLocationV1[]>;
    get: (locationId: string) => Promise<PublicLocationV1>;
  };
  public readonly drivers: {
    list: (options?: PublicDriverListOptions) => Promise<PublicDriverCatalogResponseV1>;
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
    this.timeoutMs = options.timeoutMs === undefined ? 10_000 : options.timeoutMs;
    if (
      !Number.isFinite(this.timeoutMs) ||
      this.timeoutMs <= 0 ||
      this.timeoutMs > MAX_TIMEOUT_MS
    ) {
      throw new RangeError(`timeoutMs must be finite and between 0 and ${MAX_TIMEOUT_MS} milliseconds`);
    }
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
    this.drivers = {
      list: (options: PublicDriverListOptions = {}) => {
        const limit = options.limit ?? 50;
        const offset = options.offset ?? 0;
        if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
          throw new RangeError('limit must be an integer from 1 through 50');
        }
        if (!Number.isInteger(offset) || offset < 0 || offset > 5000) {
          throw new RangeError('offset must be an integer from 0 through 5000');
        }
        return this.get<PublicDriverCatalogResponseV1>(
          `${publicApiPathsV1.listPublicDriversV1}?limit=${limit}&offset=${offset}`,
          'object',
        );
      },
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

    const globals = globalThis as unknown as {
      AbortController?: new () => PublicAbortController;
    } & PublicTimerHost;
    if (typeof globals.AbortController !== 'function') {
      throw new Error('KokonutPublicApiClient requires AbortController support');
    }
    const controller = new globals.AbortController();
    const timer = globals.setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        headers,
        signal: controller.signal,
      });
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
    } finally {
      globals.clearTimeout(timer);
    }
  }
}
