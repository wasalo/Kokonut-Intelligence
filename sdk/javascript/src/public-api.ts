/** Typed client for the versioned native Kokonut public API. */

export interface PublicLocationV1 {
  id: string;
  name: string;
  country: string | null;
  region: string | null;
  status: 'active';
}

export interface PublicMetricV1 {
  metric_key: string;
  display_name: string;
  unit: string | null;
  value: number | null;
  computed_at: string | null;
}

export interface PublicMetricSummaryV1 {
  location_id: string;
  computed: PublicMetricV1[];
  total_computed: number;
}

export interface PublicCrispAssessmentV1 {
  assessment_id: string;
  location_id: string;
  period_start: string;
  period_end: string;
  methodology_version: string;
  composite_score: number | null;
  rating: 'AAA' | 'AA' | 'A' | 'B' | 'C' | 'D' | null;
  confidence_level: 'high' | 'moderate' | 'low' | 'insufficient_evidence' | null;
  evidence_maturity_level: number | null;
  score_computed_at: string | null;
  status: 'published';
}

export interface PublicLocationSummaryV1 {
  summary_type: 'public_location_summary';
  location_id: string;
  location: PublicLocationV1;
  metrics: {
    metric_count: number;
    latest_computed_at: string | null;
  };
  attestations: {
    total_attestations: number;
    published_count: number;
    latest_attestation: string | null;
  };
}

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
      list: () => this.get<PublicLocationV1[]>('/locations'),
      get: (locationId: string) =>
        this.get<PublicLocationV1>(`/locations/${encodeURIComponent(locationId)}`),
    };
    this.metrics = {
      get: (locationId: string) =>
        this.get<PublicMetricSummaryV1>(`/metrics/${encodeURIComponent(locationId)}`),
    };
    this.crisp = {
      get: (locationId: string) =>
        this.get<PublicCrispAssessmentV1>(`/crisp/${encodeURIComponent(locationId)}`),
    };
    this.analytics = {
      getSummary: (locationId: string) =>
        this.get<PublicLocationSummaryV1>(`/analytics/${encodeURIComponent(locationId)}/summary`),
    };
  }

  private async get<T>(path: string): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.apiKey) headers['x-api-key'] = this.apiKey;

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, { headers });
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new PublicApiError('Invalid JSON response from Kokonut Gateway', response.status);
    }

    if (!payload || typeof payload !== 'object') {
      throw new PublicApiError('Invalid public API response envelope', response.status);
    }
    if (!response.ok) {
      const errorMessage = 'error' in payload ? payload.error : undefined;
      const message = typeof errorMessage === 'string' ? errorMessage : `HTTP ${response.status}`;
      throw new PublicApiError(message, response.status);
    }
    if (!('data' in payload)) {
      throw new PublicApiError('Invalid public API response envelope', response.status);
    }
    return (payload as DataEnvelope<T>).data;
  }
}
