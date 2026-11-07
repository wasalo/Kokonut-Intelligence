import { useEffect, useMemo, useRef, useState } from "react";
import {
  GatewayRequestError,
  LatestRequest,
  requestOperatorJson,
} from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const TIMESTAMP_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/i;
const PAGE_LIMIT = 50;
const RECORD_FIELDS = [
  "activity_date",
  "activity_type",
  "created_at",
  "crop_cycle_id",
  "farm_task_id",
  "id",
  "location_id",
  "plot_id",
  "source_system",
  "status",
  "updated_at",
].sort().join(",");

interface FarmActivityRecord {
  activity_date: string;
  activity_type: string;
  created_at: string | null;
  crop_cycle_id: string | null;
  farm_task_id: string | null;
  id: string;
  location_id: string;
  plot_id: string | null;
  source_system: string | null;
  status: "draft" | "submitted" | "verified" | "published" | "rejected";
  updated_at: string | null;
}

interface FarmActivityListResponse {
  data: FarmActivityRecord[];
  location_id: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isUuidOrNull(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && UUID_PATTERN.test(value));
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && TIMESTAMP_PATTERN.test(value) && Number.isFinite(Date.parse(value));
}

function validateRecord(value: unknown, locationId: string): FarmActivityRecord {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== RECORD_FIELDS ||
    typeof value.id !== "string" || !UUID_PATTERN.test(value.id) ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !isUuidOrNull(value.plot_id) || !isUuidOrNull(value.crop_cycle_id) || !isUuidOrNull(value.farm_task_id) ||
    typeof value.activity_type !== "string" || !value.activity_type.trim() || value.activity_type.length > 100 ||
    !isDate(value.activity_date) ||
    !(value.status === "draft" || value.status === "submitted" || value.status === "verified" ||
      value.status === "published" || value.status === "rejected") ||
    !(value.source_system === null || typeof value.source_system === "string") ||
    value.source_system === "field_collector" ||
    !(value.created_at === null || isTimestamp(value.created_at)) ||
    !(value.updated_at === null || isTimestamp(value.updated_at))
  ) {
    throw new Error("A farm activity row did not match the location-scoped summary contract.");
  }

  return value as unknown as FarmActivityRecord;
}

function validateList(value: unknown, locationId: string): FarmActivityListResponse {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== "data,location_id" ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !Array.isArray(value.data) || value.data.length > PAGE_LIMIT
  ) {
    throw new Error("The farm activity list did not match the selected location.");
  }

  const data = value.data.map((item) => validateRecord(item, locationId));
  const ids = new Set<string>();
  let previousUpdatedAt: number | null = Number.POSITIVE_INFINITY;
  let previousId = "";
  for (const item of data) {
    const id = item.id.toLowerCase().replace(/-/g, "");
    if (ids.has(id)) throw new Error("The farm activity list contained duplicate records.");
    ids.add(id);

    const updatedAt = item.updated_at === null ? null : Date.parse(item.updated_at);
    if (
      (previousUpdatedAt === null && updatedAt !== null) ||
      (typeof previousUpdatedAt === "number" && updatedAt !== null && updatedAt > previousUpdatedAt) ||
      (updatedAt === previousUpdatedAt && id > previousId) ||
      (updatedAt === null && previousUpdatedAt === null && id > previousId)
    ) {
      throw new Error("The farm activity list ordering was invalid.");
    }
    previousUpdatedAt = updatedAt;
    previousId = id;
  }

  return { data, location_id: value.location_id };
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your exact location farm-activity read grant is no longer active.";
    if (error.status === 404) return "Farm activity summaries are unavailable for this location.";
    if (error.status === 503) return "Farm activity is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "Farm activity records could not be loaded.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function statusLabel(status: FarmActivityRecord["status"]): string {
  switch (status) {
    case "draft": return "Draft — unverified";
    case "submitted": return "Submitted for review";
    case "verified": return "Verified";
    case "published": return "Published";
    case "rejected": return "Rejected for rework";
  }
}

export function FarmActivityListPage() {
  const sessionState = useOperatorSession();
  const listRequest = useRef(new LatestRequest());
  const [locationId, setLocationId] = useState("");
  const [records, setRecords] = useState<FarmActivityRecord[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const grantedLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  useEffect(() => {
    if (!grantedLocations.length) {
      setLocationId("");
      setRecords([]);
      setMessage("");
      return;
    }
    setLocationId((current) => grantedLocations.includes(current) ? current : grantedLocations[0]);
  }, [grantedLocations]);

  useEffect(() => {
    if (!locationId || !grantedLocations.includes(locationId)) {
      setRecords([]);
      setMessage("");
      setLoading(false);
      return;
    }

    const request = listRequest.current.begin();
    const params = new URLSearchParams({ location_id: locationId, limit: String(PAGE_LIMIT) });
    setRecords([]);
    setMessage("Loading farm activity records…");
    setLoading(true);

    void requestOperatorJson<unknown>(`/operator/api/farm-activity-records?${params}`, {
      signal: request.signal,
    })
      .then((payload) => {
        if (!request.isCurrent()) return;
        const result = validateList(payload, locationId);
        setRecords(result.data);
        setMessage(result.data.length
          ? `${result.data.length} recent non-Collector farm activity record${result.data.length === 1 ? "" : "s"}.${result.data.length === PAGE_LIMIT ? " This endpoint does not provide a continuation token." : ""}`
          : "No non-Collector farm activity records are available for this location.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || isAbortError(error)) return;
        setRecords([]);
        setMessage(requestErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setLoading(false);
      });

    return () => listRequest.current.cancel();
  }, [grantedLocations, locationId, refreshVersion]);

  if (sessionState.status === "loading") {
    return <p role="status">Loading operator session…</p>;
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="farm-activity-heading">
        <p className="eyebrow">Field Operations</p>
        <h2 id="farm-activity-heading">Farm activity records</h2>
        <p className="lead">Sign in to view records for an authorized location.</p>
        <a className="secondary-action" href="/operator/">Open operator sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return <p role="alert">{sessionState.message}</p>;
  }

  return (
    <section aria-labelledby="farm-activity-heading">
      <p className="eyebrow">Field Operations</p>
      <h2 id="farm-activity-heading">Farm activity records</h2>
      <p className="lead">
        Review non-Collector records and their governed lifecycle status for an authorized location.
      </p>

      {grantedLocations.length === 0 ? (
        <p className="migration-note" role="status">
          Your operator session has no location-scoped farm-activity read grants. No record list was requested.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="farm-activity-location">Granted location</label>
            <select
              id="farm-activity-location"
              value={locationId}
              onChange={(event) => setLocationId(event.currentTarget.value)}
            >
              {grantedLocations.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={loading || !locationId}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              Refresh records
            </button>
          </div>

          <p className="operator-status-line" role="status" aria-live="polite">{message}</p>

          {records.length > 0 && (
            <div className="farm-activity-list">
              {records.map((record) => (
                <article className="farm-activity-card" key={record.id}>
                  <header>
                    <div>
                      <h3>{record.activity_type}</h3>
                      <p>Activity date: <time dateTime={record.activity_date}>{record.activity_date}</time></p>
                    </div>
                    <span className="status-label">{statusLabel(record.status)}</span>
                  </header>
                  <dl>
                    <div><dt>Last updated</dt><dd>{record.updated_at ? new Date(record.updated_at).toLocaleString() : "Not recorded"}</dd></div>
                    <div><dt>Source</dt><dd>{record.source_system || "Unspecified"}</dd></div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        This page is read-only and excludes Field Collector submissions. Draft verification and publication controls remain in the current supervisor console.
      </p>
    </section>
  );
}
