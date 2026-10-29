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
    public readonly response?: PublicFetchResponse,
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

function isPublicLocation(value: unknown): value is PublicLocationV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  const expectedKeys = ['id', 'name', 'country', 'region', 'status'];
  if (
    Object.keys(candidate).length !== expectedKeys.length ||
    !expectedKeys.every((key) => Object.prototype.hasOwnProperty.call(candidate, key)) ||
    typeof candidate.id !== 'string' ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(candidate.id) ||
    typeof candidate.name !== 'string' ||
    (candidate.country !== null && typeof candidate.country !== 'string') ||
    (candidate.region !== null && typeof candidate.region !== 'string') ||
    candidate.status !== 'active'
  ) {
    return false;
  }
  return true;
}

function isPublicLocationList(value: unknown): value is PublicLocationV1[] {
  return Array.isArray(value) && value.every(isPublicLocation);
}

function normalizedUuid(value: unknown): string | undefined {
  if (
    typeof value !== 'string' ||
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
  ) {
    return undefined;
  }
  return value.toLowerCase();
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || month < 1 || month > 12) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysByMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= daysByMonth[month - 1];
}

function isRfc3339DateTime(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const match =
    /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-](\d{2}):(\d{2}))$/.exec(
      value,
    );
  if (!match || !isIsoDate(match[1])) return false;
  const hour = Number(match[2]);
  const minute = Number(match[3]);
  const second = Number(match[4]);
  if (hour > 23 || minute > 59 || second > 59) return false;
  if (match[5] !== 'Z') {
    const offsetHour = Number(match[6]);
    const offsetMinute = Number(match[7]);
    if (offsetHour > 23 || offsetMinute > 59) return false;
  }
  return true;
}

function isPublicCrispAssessment(
  value: unknown,
  requestedLocationId: string,
): value is PublicCrispAssessmentV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  const expectedKeys = [
    'assessment_id',
    'location_id',
    'period_start',
    'period_end',
    'methodology_version',
    'composite_score',
    'rating',
    'confidence_level',
    'evidence_maturity_level',
    'score_computed_at',
    'status',
  ];
  if (
    Object.keys(candidate).length !== expectedKeys.length ||
    !expectedKeys.every((key) => Object.prototype.hasOwnProperty.call(candidate, key))
  ) {
    return false;
  }

  const expectedLocationId = normalizedUuid(requestedLocationId);
  const score = candidate.composite_score;
  const maturity = candidate.evidence_maturity_level;
  const ratings = new Set(['AAA', 'AA', 'A', 'B', 'C', 'D']);
  const confidenceLevels = new Set(['high', 'moderate', 'low', 'insufficient_evidence']);
  return (
    expectedLocationId !== undefined &&
    normalizedUuid(candidate.assessment_id) !== undefined &&
    normalizedUuid(candidate.location_id) === expectedLocationId &&
    isIsoDate(candidate.period_start) &&
    isIsoDate(candidate.period_end) &&
    typeof candidate.methodology_version === 'string' &&
    (score === null ||
      (typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 100)) &&
    (candidate.rating === null ||
      (typeof candidate.rating === 'string' && ratings.has(candidate.rating))) &&
    (candidate.confidence_level === null ||
      (typeof candidate.confidence_level === 'string' &&
        confidenceLevels.has(candidate.confidence_level))) &&
    (maturity === null || (typeof maturity === 'number' && Number.isInteger(maturity))) &&
    (candidate.score_computed_at === null || isRfc3339DateTime(candidate.score_computed_at)) &&
    candidate.status === 'published'
  );
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

function isPublicMetricSummary(
  value: unknown,
  requestedLocationId: string,
): value is PublicMetricSummaryV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  const expectedLocationId = normalizedUuid(requestedLocationId);
  if (
    Object.keys(candidate).length !== 3 ||
    !Object.prototype.hasOwnProperty.call(candidate, 'location_id') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'computed') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'total_computed') ||
    expectedLocationId === undefined ||
    normalizedUuid(candidate.location_id) !== expectedLocationId ||
    !Array.isArray(candidate.computed) ||
    !isNonNegativeInteger(candidate.total_computed) ||
    candidate.total_computed !== candidate.computed.length
  ) {
    return false;
  }

  return candidate.computed.every((row: unknown) => {
    if (!row || typeof row !== 'object' || Array.isArray(row)) return false;
    const metric = row as Record<string, unknown>;
    return (
      Object.keys(metric).length === 5 &&
      Object.prototype.hasOwnProperty.call(metric, 'metric_key') &&
      Object.prototype.hasOwnProperty.call(metric, 'display_name') &&
      Object.prototype.hasOwnProperty.call(metric, 'unit') &&
      Object.prototype.hasOwnProperty.call(metric, 'value') &&
      Object.prototype.hasOwnProperty.call(metric, 'computed_at') &&
      typeof metric.metric_key === 'string' &&
      typeof metric.display_name === 'string' &&
      (metric.unit === null || typeof metric.unit === 'string') &&
      (metric.value === null ||
        (typeof metric.value === 'number' && Number.isFinite(metric.value))) &&
      (metric.computed_at === null || isRfc3339DateTime(metric.computed_at))
    );
  });
}

function isPublicLocationSummary(
  value: unknown,
  requestedLocationId: string,
): value is PublicLocationSummaryV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  const expectedLocationId = normalizedUuid(requestedLocationId);
  if (
    Object.keys(candidate).length !== 5 ||
    !Object.prototype.hasOwnProperty.call(candidate, 'summary_type') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'location_id') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'location') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'metrics') ||
    !Object.prototype.hasOwnProperty.call(candidate, 'attestations') ||
    expectedLocationId === undefined ||
    candidate.summary_type !== 'public_location_summary' ||
    normalizedUuid(candidate.location_id) !== expectedLocationId ||
    !isPublicLocation(candidate.location)
  ) {
    return false;
  }

  const location = candidate.location;
  const metrics = candidate.metrics;
  const attestations = candidate.attestations;
  if (
    normalizedUuid(location.id) !== expectedLocationId ||
    !metrics ||
    typeof metrics !== 'object' ||
    Array.isArray(metrics) ||
    !attestations ||
    typeof attestations !== 'object' ||
    Array.isArray(attestations)
  ) {
    return false;
  }

  const metricCounts = metrics as Record<string, unknown>;
  const attestationCounts = attestations as Record<string, unknown>;
  return (
    Object.keys(metricCounts).length === 2 &&
    Object.prototype.hasOwnProperty.call(metricCounts, 'metric_count') &&
    Object.prototype.hasOwnProperty.call(metricCounts, 'latest_computed_at') &&
    isNonNegativeInteger(metricCounts.metric_count) &&
    (metricCounts.latest_computed_at === null ||
      isRfc3339DateTime(metricCounts.latest_computed_at)) &&
    Object.keys(attestationCounts).length === 3 &&
    Object.prototype.hasOwnProperty.call(attestationCounts, 'total_attestations') &&
    Object.prototype.hasOwnProperty.call(attestationCounts, 'published_count') &&
    Object.prototype.hasOwnProperty.call(attestationCounts, 'latest_attestation') &&
    isNonNegativeInteger(attestationCounts.total_attestations) &&
    isNonNegativeInteger(attestationCounts.published_count) &&
    (attestationCounts.latest_attestation === null ||
      isRfc3339DateTime(attestationCounts.latest_attestation))
  );
}

function isDriverCatalogResponse(
  value: unknown,
  expectedLimit: number,
  expectedOffset: number,
): value is PublicDriverCatalogResponseV1 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const candidate = value as Record<string, unknown>;
  if (
    Object.keys(candidate).length !== 4 ||
    !Array.isArray(candidate.drivers) ||
    !Number.isInteger(candidate.limit) ||
    (candidate.limit as number) < 1 ||
    (candidate.limit as number) > 50 ||
    !Number.isInteger(candidate.offset) ||
    (candidate.offset as number) < 0 ||
    (candidate.offset as number) > 5000 ||
    candidate.limit !== expectedLimit ||
    candidate.offset !== expectedOffset ||
    typeof candidate.has_more !== 'boolean'
  ) {
    return false;
  }
  const driverTypes = new Set([
    'sensor',
    'remote_sensing',
    'market',
    'blockchain',
    'weather',
    'climate',
    'gis',
  ]);
  return candidate.drivers.every((driver: unknown) => {
    if (!driver || typeof driver !== 'object' || Array.isArray(driver)) return false;
    const entry = driver as Record<string, unknown>;
    return (
      Object.keys(entry).length === 3 &&
      typeof entry.driver_name === 'string' &&
      entry.driver_name.length <= 100 &&
      typeof entry.driver_version === 'string' &&
      entry.driver_version.length <= 20 &&
      typeof entry.driver_type === 'string' &&
      driverTypes.has(entry.driver_type)
    );
  });
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
      list: () =>
        this.get<PublicLocationV1[]>(
          publicApiPathsV1.listPublicLocationsV1,
          'array',
          isPublicLocationList,
        ),
      get: (locationId: string) =>
        this.get<PublicLocationV1>(
          publicApiPathsV1.getPublicLocationV1.replace(
            '{location_id}',
            encodePathSegment(locationId),
          ),
          'object',
          isPublicLocation,
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
          (value) => isDriverCatalogResponse(value, limit, offset),
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
          (value) => isPublicMetricSummary(value, locationId),
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
          (value) => isPublicCrispAssessment(value, locationId),
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
          (value) => isPublicLocationSummary(value, locationId),
        ),
    };
  }

  private async get<T>(
    path: string,
    dataShape: 'array' | 'object',
    dataValidator?: (value: unknown) => boolean,
  ): Promise<T> {
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
          throw new PublicApiError(`HTTP ${response.status}`, response.status, response);
        }
        throw new PublicApiError(
          'Invalid JSON response from Kokonut Gateway',
          response.status,
          response,
        );
      }

      if (!response.ok) {
        const errorMessage =
          payload && typeof payload === 'object' && 'error' in payload
            ? payload.error
            : undefined;
        const message = typeof errorMessage === 'string' ? errorMessage : `HTTP ${response.status}`;
        throw new PublicApiError(message, response.status, response);
      }

      if (
        !payload ||
        typeof payload !== 'object' ||
        Array.isArray(payload) ||
        !('data' in payload)
      ) {
        throw new PublicApiError('Invalid public API response envelope', response.status, response);
      }
      const data = (payload as DataEnvelope<unknown>).data;
      const validData =
        dataShape === 'array'
          ? Array.isArray(data)
          : Boolean(data) && typeof data === 'object' && !Array.isArray(data);
      if (!validData || (dataValidator && !dataValidator(data))) {
        throw new PublicApiError('Invalid public API response envelope', response.status, response);
      }
      return data as T;
    } finally {
      globals.clearTimeout(timer);
    }
  }
}
