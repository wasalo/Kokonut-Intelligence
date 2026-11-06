import { useEffect, useMemo, useRef, useState } from "react";
import {
  GatewayRequestError,
  LatestRequest,
  requestOperatorJson,
} from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const COUNT_GROUPS = [
  {
    title: "Alliance lifecycle",
    items: [
      ["alliance_count", "Location-scoped alliances"],
      ["draft_alliance_count", "Draft alliances"],
      ["proposed_alliance_count", "Proposed alliances"],
      ["approved_alliance_count", "Approved alliances"],
      ["active_alliance_count", "Active alliances"],
      ["paused_alliance_count", "Paused alliances"],
      ["completed_alliance_count", "Completed alliances"],
      ["dissolved_alliance_count", "Dissolved alliances"],
      ["rejected_alliance_count", "Rejected alliances"],
      ["overdue_review_count", "Overdue reviews"],
    ],
  },
  {
    title: "Accountability",
    items: [
      ["open_conflict_declaration_count", "Open conflict declarations"],
      ["unreviewed_harm_analysis_count", "Unreviewed harm analyses"],
      ["open_appeal_count", "Open appeals"],
      ["open_remedy_count", "Open remedies"],
      ["preserved_minority_view_count", "Preserved minority views"],
    ],
  },
  {
    title: "Learning and measurement",
    items: [
      ["completed_knowledge_exchange_count", "Completed knowledge exchanges"],
      ["open_learning_link_count", "Open learning links"],
      ["draft_metric_observation_count", "Draft metric observations"],
      ["rejected_metric_observation_count", "Rejected metric observations"],
    ],
  },
] as const;

type CountKey = (typeof COUNT_GROUPS)[number]["items"][number][0];
type CoordinationSummary = { location_id: string } & Record<CountKey, number>;

const RESPONSE_FIELDS = [
  "location_id",
  ...COUNT_GROUPS.flatMap((group) => group.items.map(([key]) => key)),
].sort().join(",");

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validateSummary(value: unknown, locationId: string): CoordinationSummary {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== RESPONSE_FIELDS ||
    typeof value.location_id !== "string" ||
    value.location_id.toLowerCase() !== locationId.toLowerCase()
  ) {
    throw new Error("The coordination summary did not match the selected location.");
  }

  for (const group of COUNT_GROUPS) {
    for (const [key] of group.items) {
      const count = value[key];
      if (typeof count !== "number" || !Number.isSafeInteger(count) || count < 0) {
        throw new Error("The coordination summary contained an invalid count.");
      }
    }
  }

  return value as CoordinationSummary;
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your exact location coordination-read grant is no longer active.";
    if (error.status === 404) return "Coordination summary is unavailable for this location.";
    if (error.status === 503) return "The coordination summary is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "The coordination summary could not be loaded.";
}

export function CoordinationSummaryPage() {
  const sessionState = useOperatorSession();
  const summaryRequest = useRef(new LatestRequest());
  const [locationId, setLocationId] = useState("");
  const [summary, setSummary] = useState<CoordinationSummary | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const grantedLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "coordination" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  useEffect(() => {
    if (!grantedLocations.length) {
      setLocationId("");
      setSummary(null);
      setMessage("");
      return;
    }
    setLocationId((current) => grantedLocations.includes(current) ? current : grantedLocations[0]);
  }, [grantedLocations]);

  useEffect(() => {
    if (!locationId || !grantedLocations.includes(locationId)) {
      setSummary(null);
      setMessage("");
      setLoading(false);
      return;
    }

    const request = summaryRequest.current.begin();
    setSummary(null);
    setMessage("Loading coordination overview…");
    setLoading(true);

    void requestOperatorJson<unknown>(
      `/operator/api/coordination/${encodeURIComponent(locationId)}/summary`,
      { signal: request.signal },
    )
      .then((payload) => {
        if (!request.isCurrent()) return;
        setSummary(validateSummary(payload, locationId));
        setMessage("Read-only aggregate counts. No alliance state was changed.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || (error instanceof Error && error.name === "AbortError")) return;
        setSummary(null);
        setMessage(requestErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setLoading(false);
      });

    return () => summaryRequest.current.cancel();
  }, [grantedLocations, locationId, refreshVersion]);

  if (sessionState.status === "loading") {
    return <p role="status">Loading operator session…</p>;
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="coordination-heading">
        <p className="eyebrow">Planning and coordination</p>
        <h2 id="coordination-heading">Coordination overview</h2>
        <p className="lead">Sign in to view the location-scoped aggregate overview.</p>
        <a className="button-link" href="/operator/">Open operator sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return <p role="alert">{sessionState.message}</p>;
  }

  return (
    <section aria-labelledby="coordination-heading">
      <p className="eyebrow">Planning and coordination</p>
      <h2 id="coordination-heading">Coordination overview</h2>
      <p className="lead">
        Review aggregate alliance, accountability, and learning counts for a location you can access.
      </p>

      {grantedLocations.length === 0 ? (
        <p className="migration-note" role="status">
          Your operator session has no location-scoped coordination read grants. No summary was requested.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="coordination-location">Granted location</label>
            <select
              id="coordination-location"
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
              Refresh overview
            </button>
          </div>

          <p className="operator-status-line" role="status" aria-live="polite">{message}</p>

          {summary && (
            <div className="coordination-summary-groups">
              {COUNT_GROUPS.map((group) => (
                <section className="coordination-summary-group" key={group.title} aria-label={group.title}>
                  <h3>{group.title}</h3>
                  <dl className="coordination-summary-counts">
                    {group.items.map(([key, label]) => (
                      <div className="coordination-summary-count" key={key}>
                        <dt>{label}</dt>
                        <dd>{summary[key].toLocaleString()}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ))}
            </div>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        This page is read-only. The Gateway remains responsible for operator identity, location scope, and data access.
      </p>
    </section>
  );
}
