/** Generated from docs/refactor/native-public-api-v1.openapi.json. Do not edit. */

export interface PublicAttestationCountsV1 {
  latest_attestation: string | null;
  published_count: number;
  total_attestations: number;
}

export interface PublicCrispAssessmentV1 {
  assessment_id: string;
  composite_score: number | null;
  confidence_level: "high" | "moderate" | "low" | "insufficient_evidence" | null;
  evidence_maturity_level: number | null;
  location_id: string;
  methodology_version: string;
  period_end: string;
  period_start: string;
  rating: "AAA" | "AA" | "A" | "B" | "C" | "D" | null;
  score_computed_at: string | null;
  status: "published";
}

export interface PublicCrispAssessmentEnvelopeV1 {
  data: PublicCrispAssessmentV1;
}

export interface PublicDriverCatalogEntryV1 {
  driver_name: string;
  driver_type: "sensor" | "remote_sensing" | "market" | "blockchain" | "weather" | "climate" | "gis";
  driver_version: string;
}

export interface PublicDriverCatalogEnvelopeV1 {
  data: PublicDriverCatalogResponseV1;
}

export interface PublicDriverCatalogResponseV1 {
  drivers: PublicDriverCatalogEntryV1[];
  has_more: boolean;
  limit: number;
  offset: number;
}

export interface PublicErrorV1 {
  error: string;
}

export interface PublicLocationV1 {
  country: string | null;
  id: string;
  name: string;
  region: string | null;
  status: "active";
}

export interface PublicLocationListResponseV1 {
  data: PublicLocationV1[];
}

export interface PublicLocationResponseV1 {
  data: PublicLocationV1;
}

export interface PublicLocationSummaryV1 {
  attestations: PublicAttestationCountsV1;
  location: PublicLocationV1;
  location_id: string;
  metrics: PublicMetricCountsV1;
  summary_type: "public_location_summary";
}

export interface PublicLocationSummaryEnvelopeV1 {
  data: PublicLocationSummaryV1;
}

export interface PublicMetricV1 {
  computed_at: string | null;
  display_name: string;
  metric_key: string;
  unit: string | null;
  value: number | null;
}

export interface PublicMetricCountsV1 {
  latest_computed_at: string | null;
  metric_count: number;
}

export interface PublicMetricSummaryV1 {
  computed: PublicMetricV1[];
  location_id: string;
  total_computed: number;
}

export interface PublicMetricSummaryEnvelopeV1 {
  data: PublicMetricSummaryV1;
}

export const publicApiPathsV1 = {
  getPublicCrispAssessmentV1: "/crisp/{location_id}",
  getPublicLocationSummaryV1: "/analytics/{location_id}/summary",
  getPublicLocationV1: "/locations/{location_id}",
  getPublicMetricSummaryV1: "/metrics/{location_id}",
  listPublicDriversV1: "/drivers",
  listPublicLocationsV1: "/locations",
} as const;
