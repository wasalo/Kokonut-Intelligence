import { useEffect, useMemo, useRef, useState } from "react";
import {
  GatewayRequestError,
  LatestRequest,
  requestOperatorJson,
} from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BLOCKERS = new Set([
  "self_review",
  "diversity_assessment_required",
  "minority_report_review_required",
]);
const PAGE_LIMIT = 20;
const MAX_OFFSET = 10_000;
const ITEM_FIELDS = [
  "blocked_reasons",
  "created_at",
  "recommendation_id",
  "recommendation_text",
  "review_ready",
  "study_id",
  "study_status",
  "study_title",
  "summary",
].sort().join(",");
const PAGE_FIELDS = ["has_more", "location_id", "offset", "recommendations"]
  .sort().join(",");

interface RecommendationReviewItem {
  blocked_reasons: string[];
  created_at: string | null;
  recommendation_id: string;
  recommendation_text: string;
  review_ready: boolean;
  study_id: string;
  study_status: "draft" | "open" | "closed";
  study_title: string;
  summary: string | null;
}

interface RecommendationReviewPage {
  has_more: boolean;
  location_id: string;
  offset: number;
  recommendations: RecommendationReviewItem[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value));
}

function validateItem(value: unknown): RecommendationReviewItem {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== ITEM_FIELDS ||
    typeof value.recommendation_id !== "string" || !UUID_PATTERN.test(value.recommendation_id) ||
    typeof value.study_id !== "string" || !UUID_PATTERN.test(value.study_id) ||
    typeof value.study_title !== "string" || value.study_title.length > 255 ||
    !(value.study_status === "draft" || value.study_status === "open" || value.study_status === "closed") ||
    !(value.summary === null || (typeof value.summary === "string" && value.summary.length <= 4000)) ||
    typeof value.recommendation_text !== "string" ||
    value.recommendation_text.length < 1 || value.recommendation_text.length > 20_000 ||
    !(value.created_at === null || isTimestamp(value.created_at)) ||
    typeof value.review_ready !== "boolean" ||
    !Array.isArray(value.blocked_reasons) || value.blocked_reasons.length > BLOCKERS.size ||
    !value.blocked_reasons.every((reason) => typeof reason === "string" && BLOCKERS.has(reason))
  ) {
    throw new Error("The recommendation review response contained an invalid item.");
  }

  const blockers = value.blocked_reasons as string[];
  if (
    new Set(blockers).size !== blockers.length ||
    value.review_ready !== (blockers.length === 0)
  ) {
    throw new Error("Recommendation readiness did not match its review blockers.");
  }

  return value as unknown as RecommendationReviewItem;
}

function validatePage(value: unknown, locationId: string, offset: number): RecommendationReviewPage {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== PAGE_FIELDS ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    value.offset !== offset || !Number.isSafeInteger(value.offset) ||
    typeof value.has_more !== "boolean" || !Array.isArray(value.recommendations) ||
    value.recommendations.length > PAGE_LIMIT || offset < 0 || offset > MAX_OFFSET
  ) {
    throw new Error("The recommendation page did not match this location and request.");
  }

  if (value.has_more && (
    value.recommendations.length !== PAGE_LIMIT || offset + PAGE_LIMIT > MAX_OFFSET
  )) {
    throw new Error("The recommendation page continuation was invalid.");
  }

  const recommendations = value.recommendations.map(validateItem);
  const ids = new Set<string>();
  for (const item of recommendations) {
    const id = item.recommendation_id.toLowerCase();
    if (ids.has(id)) throw new Error("The recommendation page contained duplicate items.");
    ids.add(id);
  }

  return {
    has_more: value.has_more,
    location_id: value.location_id,
    offset: value.offset as number,
    recommendations,
  };
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your exact location Delphi review grant is no longer active.";
    if (error.status === 404) return "Delphi recommendation review is unavailable for this location.";
    if (error.status === 503) return "The review queue is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "The Delphi review queue could not be loaded.";
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

export function DelphiRecommendationReviewPage() {
  const sessionState = useOperatorSession();
  const pageRequest = useRef(new LatestRequest());
  const [locationId, setLocationId] = useState("");
  const [recommendations, setRecommendations] = useState<RecommendationReviewItem[]>([]);
  const [nextOffset, setNextOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const grantedLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "delphi" && scope.action === "review")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  useEffect(() => {
    if (!grantedLocations.length) {
      setLocationId("");
      setRecommendations([]);
      setNextOffset(0);
      setHasMore(false);
      setMessage("");
      return;
    }
    setLocationId((current) => grantedLocations.includes(current) ? current : grantedLocations[0]);
  }, [grantedLocations]);

  useEffect(() => {
    if (!locationId || !grantedLocations.includes(locationId)) {
      setRecommendations([]);
      setNextOffset(0);
      setHasMore(false);
      setMessage("");
      setLoading(false);
      return;
    }

    const request = pageRequest.current.begin();
    setRecommendations([]);
    setNextOffset(0);
    setHasMore(false);
    setMessage("Loading facilitator recommendation drafts…");
    setLoading(true);
    setLoadingMore(false);
    const params = new URLSearchParams({ limit: String(PAGE_LIMIT), offset: "0" });

    void requestOperatorJson<unknown>(
      `/operator/api/delphi/${encodeURIComponent(locationId)}/recommendations?${params}`,
      { signal: request.signal },
    )
      .then((payload) => {
        if (!request.isCurrent()) return;
        const page = validatePage(payload, locationId, 0);
        setRecommendations(page.recommendations);
        setNextOffset(page.recommendations.length);
        setHasMore(page.has_more);
        setMessage(page.recommendations.length
          ? `${page.recommendations.length} facilitator draft${page.recommendations.length === 1 ? "" : "s"} loaded. This view cannot approve or publish them.`
          : "No facilitator recommendation drafts are awaiting review for this location.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || isAbortError(error)) return;
        setRecommendations([]);
        setMessage(requestErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setLoading(false);
      });

    return () => pageRequest.current.cancel();
  }, [grantedLocations, locationId, refreshVersion]);

  async function loadMore() {
    if (!locationId || !hasMore || loadingMore || nextOffset >= MAX_OFFSET) return;
    const offset = nextOffset;
    const request = pageRequest.current.begin();
    const params = new URLSearchParams({ limit: String(PAGE_LIMIT), offset: String(offset) });
    setLoadingMore(true);
    setMessage("Loading more facilitator drafts…");
    try {
      const payload = await requestOperatorJson<unknown>(
        `/operator/api/delphi/${encodeURIComponent(locationId)}/recommendations?${params}`,
        { signal: request.signal },
      );
      if (!request.isCurrent()) return;
      const page = validatePage(payload, locationId, offset);
      const existingIds = new Set(recommendations.map((item) => item.recommendation_id.toLowerCase()));
      if (page.recommendations.some((item) => existingIds.has(item.recommendation_id.toLowerCase()))) {
        throw new Error("The next review page repeated a recommendation already shown.");
      }
      setRecommendations((current) => [...current, ...page.recommendations]);
      setNextOffset(offset + page.recommendations.length);
      setHasMore(page.has_more);
      setMessage(`${recommendations.length + page.recommendations.length} facilitator drafts loaded. This view cannot approve or publish them.`);
    } catch (error) {
      if (!request.isCurrent() || isAbortError(error)) return;
      setMessage(requestErrorMessage(error));
    } finally {
      if (request.isCurrent()) setLoadingMore(false);
    }
  }

  if (sessionState.status === "loading") {
    return <p role="status">Loading operator session…</p>;
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="delphi-review-heading">
        <p className="eyebrow">Governance</p>
        <h2 id="delphi-review-heading">Facilitator recommendation review</h2>
        <p className="lead">Sign in with an authorized reviewer account to view this private queue.</p>
        <a className="secondary-action" href="/operator/">Open operator sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return <p role="alert">{sessionState.message}</p>;
  }

  return (
    <section aria-labelledby="delphi-review-heading">
      <p className="eyebrow">Governance</p>
      <h2 id="delphi-review-heading">Facilitator recommendation review</h2>
      <p className="lead">
        Read submitted facilitator drafts and their recorded approval blockers for a granted location.
      </p>

      {grantedLocations.length === 0 ? (
        <p className="migration-note" role="status">
          Your operator session has no location-scoped Delphi review grants. No review queue was requested.
        </p>
      ) : (
        <>
          <div className="report-review-toolbar">
            <label htmlFor="delphi-review-location">Granted location</label>
            <select
              id="delphi-review-location"
              value={locationId}
              onChange={(event) => setLocationId(event.currentTarget.value)}
            >
              {grantedLocations.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={loading || loadingMore || !locationId}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              Refresh queue
            </button>
          </div>

          <p className="report-review-status" role="status" aria-live="polite">{message}</p>

          {recommendations.length > 0 && (
            <div className="delphi-review-list">
              {recommendations.map((item) => (
                <article className="delphi-review-card" key={item.recommendation_id}>
                  <header className="delphi-review-card-header">
                    <div>
                      <h3>{item.study_title || "Untitled study"}</h3>
                      <p>Study status: {item.study_status}</p>
                    </div>
                    <span className="status-label">
                      {item.review_ready ? "Ready for review" : "Review blocked"}
                    </span>
                  </header>
                  {item.blocked_reasons.length > 0 && (
                    <div>
                      <h4>Recorded blockers</h4>
                      <ul>
                        {item.blocked_reasons.map((reason) => <li key={reason}>{reason.replaceAll("_", " ")}</li>)}
                      </ul>
                    </div>
                  )}
                  <p>Created: {item.created_at ? new Date(item.created_at).toLocaleString() : "Date unavailable"}</p>
                  <details>
                    <summary>Read facilitator draft</summary>
                    <h4>Summary</h4>
                    <p className="delphi-review-text">{item.summary || "No summary provided."}</p>
                    <h4>Recommendation</h4>
                    <p className="delphi-review-text">{item.recommendation_text}</p>
                  </details>
                </article>
              ))}
            </div>
          )}

          {hasMore && (
            <button className="secondary-action" type="button" disabled={loadingMore} onClick={() => void loadMore()}>
              {loadingMore ? "Loading…" : "Load more drafts"}
            </button>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        This page has no decision or publication controls. Approval still requires an independent reviewer,
        the existing diversity and minority-report checks, and the current governed workflow.
      </p>
    </section>
  );
}
