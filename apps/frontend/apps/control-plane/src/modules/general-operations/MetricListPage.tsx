import { useEffect, useMemo, useRef, useState } from "react";
import { GatewayRequestError, LatestRequest, operatorLocationLabel, requestOperatorJson } from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ITEM_FIELDS = [
  "computed_at",
  "display_name",
  "metric_key",
  "metric_value_id",
  "period_end",
  "period_start",
  "status",
  "unit",
  "value",
  "verified_at",
].sort().join(",");
const PAGE_FIELDS = ["cursor", "has_more", "items", "limit", "location_id", "next_cursor"]
  .sort().join(",");
const PAGE_LIMIT = 25;

interface MetricValueItem {
  computed_at: string;
  display_name: string;
  metric_key: string;
  metric_value_id: string;
  period_end: string | null;
  period_start: string | null;
  status: "draft" | "verified";
  unit: string | null;
  value: number | null;
  verified_at: string | null;
}

interface MetricValuePage {
  cursor: string;
  has_more: boolean;
  items: MetricValueItem[];
  limit: number;
  location_id: string;
  next_cursor: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" && value.includes("T") &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value));
}

function validateMetricItem(value: unknown): MetricValueItem {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== ITEM_FIELDS ||
    typeof value.metric_value_id !== "string" || !UUID_PATTERN.test(value.metric_value_id) ||
    typeof value.metric_key !== "string" || !/^[a-z][a-z0-9_]{0,99}$/.test(value.metric_key) ||
    typeof value.display_name !== "string" || !value.display_name.trim() || value.display_name.length > 255 ||
    !(value.period_start === null || isDate(value.period_start)) ||
    !(value.period_end === null || isDate(value.period_end)) ||
    (value.period_start !== null && value.period_end !== null && value.period_start > value.period_end) ||
    !(value.value === null || (typeof value.value === "number" && Number.isFinite(value.value))) ||
    !(value.unit === null || (typeof value.unit === "string" && value.unit.length <= 50)) ||
    !(value.status === "draft" || value.status === "verified") ||
    !isTimestamp(value.computed_at) ||
    !(value.verified_at === null || isTimestamp(value.verified_at)) ||
    ((value.status === "draft") !== (value.verified_at === null))
  ) {
    throw new Error("The metric page contained an invalid item.");
  }

  return value as unknown as MetricValueItem;
}

function validateMetricPage(
  value: unknown,
  locationId: string,
  cursor: string,
): MetricValuePage {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== PAGE_FIELDS ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    value.cursor !== cursor || value.limit !== PAGE_LIMIT ||
    typeof value.has_more !== "boolean" || !Array.isArray(value.items) ||
    value.items.length > PAGE_LIMIT || !/^(0|[1-9][0-9]*)$/.test(cursor) ||
    cursor.length > 5 || Number(cursor) > 10_000
  ) {
    throw new Error("The metric page did not match this location and request.");
  }

  const offset = Number(cursor);
  if (value.has_more) {
    if (
      value.items.length !== PAGE_LIMIT || offset + PAGE_LIMIT > 10_000 ||
      value.next_cursor !== String(offset + PAGE_LIMIT)
    ) {
      throw new Error("The metric page continuation was invalid.");
    }
  } else if (value.next_cursor !== null) {
    throw new Error("The final metric page included an invalid continuation.");
  }

  const items = value.items.map(validateMetricItem);
  const ids = new Set<string>();
  let previousTime = Number.POSITIVE_INFINITY;
  let previousId = "";
  for (const item of items) {
    const id = item.metric_value_id.toLowerCase();
    const normalizedId = id.replace(/-/g, "");
    const computedTime = Date.parse(item.computed_at);
    if (
      ids.has(id) || computedTime > previousTime ||
      (computedTime === previousTime && normalizedId > previousId)
    ) {
      throw new Error("The metric page ordering or identity was invalid.");
    }
    ids.add(id);
    previousTime = computedTime;
    previousId = normalizedId;
  }

  return {
    cursor: value.cursor as string,
    has_more: value.has_more,
    items,
    limit: value.limit as number,
    location_id: value.location_id,
    next_cursor: value.next_cursor as string | null,
  };
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your exact location metric-read grant is no longer active.";
    if (error.status === 404) return "Metric review is unavailable for this location.";
    if (error.status === 503) return "Metric review is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "Location metrics could not be loaded.";
}

function formatPeriod(item: MetricValueItem): string {
  if (!item.period_start && !item.period_end) return "All available data";
  return `${item.period_start || "—"} – ${item.period_end || "—"}`;
}

export function MetricListPage() {
  const sessionState = useOperatorSession();
  const pageRequest = useRef(new LatestRequest());
  const [locationId, setLocationId] = useState("");
  const [items, setItems] = useState<MetricValueItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const readLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "metric_value" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  useEffect(() => {
    if (readLocations.length === 0) {
      setLocationId("");
      setItems([]);
      setNextCursor(null);
      setHasMore(false);
      setMessage("");
      return;
    }
    setLocationId((current) => readLocations.includes(current) ? current : readLocations[0]);
  }, [readLocations]);

  useEffect(() => {
    if (!locationId) {
      setItems([]);
      setNextCursor(null);
      setHasMore(false);
      setMessage("");
      setLoading(false);
      return;
    }

    const request = pageRequest.current.begin();
    const params = new URLSearchParams({ cursor: "0", limit: String(PAGE_LIMIT) });
    setItems([]);
    setNextCursor(null);
    setHasMore(false);
    setMessage("Loading location metrics…");
    setLoading(true);

    void requestOperatorJson<unknown>(
      `/operator/api/metrics/${encodeURIComponent(locationId)}/values?${params}`,
      { signal: request.signal },
    )
      .then((payload) => {
        if (!request.isCurrent()) return;
        const page = validateMetricPage(payload, locationId, "0");
        setItems(page.items);
        setNextCursor(page.next_cursor);
        setHasMore(page.has_more);
        setMessage(page.items.length
          ? `${page.items.length} location metric${page.items.length === 1 ? "" : "s"} shown. Drafts remain unverified.`
          : "No metrics are available for this location.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || (error instanceof Error && error.name === "AbortError")) return;
        setItems([]);
        setNextCursor(null);
        setHasMore(false);
        setMessage(requestErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setLoading(false);
      });

    return () => pageRequest.current.cancel();
  }, [locationId, refreshVersion]);

  async function loadMore() {
    if (!locationId || !nextCursor || loading) return;
    const cursor = nextCursor;
    const request = pageRequest.current.begin();
    const params = new URLSearchParams({ cursor, limit: String(PAGE_LIMIT) });
    setMessage("Loading more metrics…");
    setLoading(true);

    try {
      const payload = await requestOperatorJson<unknown>(
        `/operator/api/metrics/${encodeURIComponent(locationId)}/values?${params}`,
        { signal: request.signal },
      );
      if (!request.isCurrent()) return;
      const page = validateMetricPage(payload, locationId, cursor);
      const previousIds = new Set(items.map((item) => item.metric_value_id.toLowerCase()));
      if (page.items.some((item) => previousIds.has(item.metric_value_id.toLowerCase()))) {
        throw new Error("The metric page repeated a record from the previous page.");
      }
      const combined = [...items, ...page.items];
      setItems(combined);
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      setMessage(page.items.length
        ? `${combined.length} location metrics shown. Drafts remain unverified.`
        : "No additional metrics are available.");
    } catch (error) {
      if (!request.isCurrent() || (error instanceof Error && error.name === "AbortError")) return;
      setMessage(requestErrorMessage(error));
    } finally {
      if (request.isCurrent()) setLoading(false);
    }
  }

  if (sessionState.status === "loading") {
    return (
      <section aria-labelledby="metric-list-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="metric-list-heading">Metrics</h2>
        <p role="status">Checking your operator session…</p>
      </section>
    );
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="metric-list-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="metric-list-heading">Metrics</h2>
        <p className="lead">Sign in to inspect metrics for your granted locations.</p>
        <a className="primary-action" href="/operator/auth/login?return_to=%2Fops%2Fmetrics&amp;prompt=select_account">Sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return (
      <section aria-labelledby="metric-list-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="metric-list-heading">Metrics</h2>
        <p role="alert" className="migration-note">{sessionState.message}</p>
        <a className="secondary-action" href="/operator/">Open current operator console</a>
      </section>
    );
  }

  return (
    <section aria-labelledby="metric-list-heading">
      <p className="eyebrow">General Operations</p>
      <h2 id="metric-list-heading">Metrics</h2>
      <p className="lead">
        Inspect location-scoped metric values. Draft values are not verified;
        verification remains a separate human decision.
      </p>

      {readLocations.length === 0 ? (
        <p role="status" className="migration-note">
          Your session has no active metric-read location grants.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="metric-list-location">Granted location</label>
            <select
              id="metric-list-location"
              value={locationId}
              onChange={(event) => setLocationId(event.currentTarget.value)}
            >
              {readLocations.map((id) => <option key={id} value={id}>{operatorLocationLabel(sessionState.session.locations, id)}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={loading}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              {loading ? "Refreshing…" : "Refresh metrics"}
            </button>
          </div>

          <p className="operator-status-line" role="status" aria-live="polite">{message}</p>
          <div className="table-scroll">
            <table className="report-review-table">
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  <th scope="col">Period</th>
                  <th scope="col">Value</th>
                  <th scope="col">State</th>
                  <th scope="col">Computed</th>
                  <th scope="col">Verified</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.metric_value_id}>
                    <td>{item.display_name} ({item.metric_key})</td>
                    <td>{formatPeriod(item)}</td>
                    <td>{item.value === null ? "—" : `${item.value}${item.unit ? ` ${item.unit}` : ""}`}</td>
                    <td>{item.status === "draft" ? "Draft · unverified" : "Verified"}</td>
                    <td>{new Date(item.computed_at).toLocaleString()}</td>
                    <td>{item.verified_at ? new Date(item.verified_at).toLocaleString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <button className="secondary-action" type="button" disabled={loading} onClick={() => void loadMore()}>
              {loading ? "Loading…" : "Load more metrics"}
            </button>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        This view does not compute or verify values. Those workflows remain in the
        <a href="/operator/"> current operator console</a>, where compute and verify
        grants are checked separately by the Gateway.
      </p>
    </section>
  );
}
