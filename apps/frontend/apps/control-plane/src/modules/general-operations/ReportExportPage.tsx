import { useEffect, useMemo, useRef, useState } from "react";
import {
  GatewayRequestError,
  LatestRequest,
  requestOperatorJson,
} from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CANDIDATE_FIELDS = [
  "created_at",
  "location_id",
  "period_end",
  "period_start",
  "report_name",
  "report_type",
  "snapshot_hash",
  "snapshot_id",
  "status",
].sort().join(",");
const EXPORT_FIELDS = [
  "artifact_size",
  "attempt_count",
  "completed_at",
  "created_at",
  "last_error_class",
  "location_id",
  "request_id",
  "snapshot_id",
  "status",
  "updated_at",
].sort().join(",");
const PAGE_SIZE = 25;

type ExportStatus = "pending" | "processing" | "retryable" | "dead_letter" | "completed" | "cancelled";

interface ExportCandidate {
  snapshot_id: string;
  location_id: string;
  report_name: string;
  report_type: string | null;
  status: "verified" | "published";
  period_start: string | null;
  period_end: string | null;
  snapshot_hash: string;
  created_at: string | null;
}

interface CandidatePage {
  location_id: string;
  limit: number;
  offset: number;
  has_more: boolean;
  data: ExportCandidate[];
}

interface ExportRequest {
  request_id: string;
  snapshot_id: string;
  location_id: string;
  status: ExportStatus;
  attempt_count: number;
  artifact_size: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  last_error_class: string | null;
}

interface ExportRequestList {
  location_id: string;
  data: ExportRequest[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === "string" || value === null;
}

function validateCandidate(value: unknown, locationId: string): ExportCandidate {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== CANDIDATE_FIELDS) {
    throw new Error("The export candidate did not match its response contract.");
  }

  if (
    typeof value.snapshot_id !== "string" || !UUID_PATTERN.test(value.snapshot_id) ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    typeof value.report_name !== "string" ||
    !(typeof value.report_type === "string" || value.report_type === null) ||
    (value.status !== "verified" && value.status !== "published") ||
    !isNullableString(value.period_start) ||
    !isNullableString(value.period_end) ||
    typeof value.snapshot_hash !== "string" || !/^[0-9a-f]{64}$/.test(value.snapshot_hash) ||
    !isNullableString(value.created_at)
  ) {
    throw new Error("The export candidate did not match the selected location.");
  }

  return value as unknown as ExportCandidate;
}

function validateCandidatePage(value: unknown, locationId: string, offset: number): CandidatePage {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== "data,has_more,limit,location_id,offset" ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    value.limit !== PAGE_SIZE || value.offset !== offset || typeof value.has_more !== "boolean" ||
    !Array.isArray(value.data) || value.data.length > PAGE_SIZE
  ) {
    throw new Error("The export candidate page did not match its response contract.");
  }

  return {
    location_id: value.location_id,
    limit: PAGE_SIZE,
    offset,
    has_more: value.has_more,
    data: value.data.map((candidate) => validateCandidate(candidate, locationId)),
  };
}

function validateExport(value: unknown, locationId: string): ExportRequest {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== EXPORT_FIELDS) {
    throw new Error("The export request did not match its response contract.");
  }

  const validStatus = ["pending", "processing", "retryable", "dead_letter", "completed", "cancelled"]
    .includes(String(value.status));
  if (
    typeof value.request_id !== "string" || !UUID_PATTERN.test(value.request_id) ||
    typeof value.snapshot_id !== "string" || !UUID_PATTERN.test(value.snapshot_id) ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !validStatus ||
    typeof value.attempt_count !== "number" || !Number.isInteger(value.attempt_count) || value.attempt_count < 0 ||
    !(value.artifact_size === null || (typeof value.artifact_size === "number" && Number.isInteger(value.artifact_size) && value.artifact_size > 0 && value.artifact_size <= 524288)) ||
    typeof value.created_at !== "string" ||
    typeof value.updated_at !== "string" ||
    !isNullableString(value.completed_at) ||
    !isNullableString(value.last_error_class) ||
    (typeof value.last_error_class === "string" && !/^[A-Za-z][A-Za-z0-9_]{0,79}$/.test(value.last_error_class))
  ) {
    throw new Error("The export request did not match the selected location.");
  }

  return value as unknown as ExportRequest;
}

function validateExportList(value: unknown, locationId: string): ExportRequestList {
  if (
    !isRecord(value) || Object.keys(value).sort().join(",") !== "data,location_id" ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !Array.isArray(value.data) || value.data.length > 50
  ) {
    throw new Error("The export request list did not match the selected location.");
  }

  return { location_id: value.location_id, data: value.data.map((item) => validateExport(item, locationId)) };
}

function validateCreateResult(value: unknown): { request_id: string; status: ExportStatus; created_at: string } {
  if (
    !isRecord(value) || Object.keys(value).sort().join(",") !== "created_at,request_id,status" ||
    typeof value.request_id !== "string" || !UUID_PATTERN.test(value.request_id) ||
    typeof value.created_at !== "string" ||
    !["pending", "processing", "retryable", "dead_letter", "completed", "cancelled"].includes(String(value.status))
  ) {
    throw new Error("The Gateway returned an invalid export request.");
  }

  return value as { request_id: string; status: ExportStatus; created_at: string };
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function errorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your report-export grant for this location is no longer active.";
    if (error.status === 404) return "The selected report is no longer available for export.";
    if (error.status === 409) return "The export request conflicted with an earlier request. Refresh before trying again.";
    if (error.status === 503) return "The report-export service is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "The report-export service is unavailable.";
}

function dateRange(candidate: Pick<ExportCandidate, "period_start" | "period_end">): string {
  return [candidate.period_start, candidate.period_end].filter(Boolean).join(" – ") || "—";
}

export function ReportExportPage() {
  const listRequest = useRef(new LatestRequest());
  const idempotencyKeys = useRef(new Map<string, string>());
  const sessionState = useOperatorSession();
  const session = sessionState.status === "ready" ? sessionState.session : null;
  const [locationId, setLocationId] = useState("");
  const [offset, setOffset] = useState(0);
  const [candidates, setCandidates] = useState<ExportCandidate[]>([]);
  const [requests, setRequests] = useState<ExportRequest[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [submittingSnapshotId, setSubmittingSnapshotId] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  const readableLocations = useMemo(() => {
    if (!session) return [];
    return [...new Set(session.scopes
      .filter((scope) => scope.resource === "report_snapshot_export" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [session]);
  const createLocations = useMemo(() => new Set(session?.scopes
    .filter((scope) => scope.resource === "report_snapshot_export" && scope.action === "create")
    .map((scope) => scope.location_id.toLowerCase()) ?? []), [session]);
  const downloadLocations = useMemo(() => new Set(session?.scopes
    .filter((scope) => scope.resource === "report_snapshot_export" && scope.action === "download")
    .map((scope) => scope.location_id.toLowerCase()) ?? []), [session]);
  const requestedSnapshots = useMemo(() => new Set(requests
    .filter((item) => item.status !== "cancelled")
    .map((item) => item.snapshot_id.toLowerCase())), [requests]);
  const canCreate = createLocations.has(locationId.toLowerCase());
  const canDownload = downloadLocations.has(locationId.toLowerCase());

  useEffect(() => {
    if (!readableLocations.length) {
      setLocationId("");
      setOffset(0);
      setCandidates([]);
      setRequests([]);
      setHasMore(false);
      setMessage("");
      return;
    }

    setLocationId((current) => readableLocations.includes(current) ? current : readableLocations[0]);
  }, [readableLocations]);

  useEffect(() => {
    const request = listRequest.current.begin();
    if (!locationId) {
      setCandidates([]);
      setRequests([]);
      setHasMore(false);
      setMessage("");
      setLoading(false);
      return () => listRequest.current.cancel();
    }

    const params = new URLSearchParams({ location_id: locationId, limit: String(PAGE_SIZE), offset: String(offset) });
    const requestParams = new URLSearchParams({ location_id: locationId, limit: "50" });
    setCandidates([]);
    setRequests([]);
    setMessage("Loading reviewed snapshots and private export requests…");
    setLoading(true);

    void Promise.all([
      requestOperatorJson<unknown>(`/operator/api/report-export-snapshots?${params}`, { signal: request.signal }),
      requestOperatorJson<unknown>(`/operator/api/report-exports?${requestParams}`, { signal: request.signal }),
    ])
      .then(([candidatePayload, requestPayload]) => {
        if (!request.isCurrent()) return;
        const candidatePage = validateCandidatePage(candidatePayload, locationId, offset);
        const exportList = validateExportList(requestPayload, locationId);
        setCandidates(candidatePage.data);
        setRequests(exportList.data);
        setHasMore(candidatePage.has_more);
        setMessage(candidatePage.data.length
          ? `${candidatePage.data.length} reviewed snapshot${candidatePage.data.length === 1 ? "" : "s"} available on this page.`
          : "No verified or published snapshots are available for private export at this location.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || isAbortError(error)) return;
        setCandidates([]);
        setRequests([]);
        setHasMore(false);
        setMessage(errorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setLoading(false);
      });

    return () => listRequest.current.cancel();
  }, [locationId, offset, refreshVersion]);

  async function requestExport(candidate: ExportCandidate) {
    if (!locationId || !canCreate || submittingSnapshotId || requestedSnapshots.has(candidate.snapshot_id.toLowerCase())) return;
    if (!window.confirm(
      `Request a private export of “${candidate.report_name}”? Confirm that its audience and disclosure have been reviewed. This creates a private artifact; it does not publish the report.`,
    )) return;

    setSubmittingSnapshotId(candidate.snapshot_id);
    setMessage("Creating a private export request…");
    try {
      let idempotencyKey = idempotencyKeys.current.get(candidate.snapshot_id);
      if (!idempotencyKey) {
        idempotencyKey = crypto.randomUUID();
        idempotencyKeys.current.set(candidate.snapshot_id, idempotencyKey);
      }
      const params = new URLSearchParams({ location_id: locationId });
      const result = validateCreateResult(await requestOperatorJson<unknown>(`/operator/api/report-exports?${params}`, {
        method: "POST",
        body: {
          report_snapshot_id: candidate.snapshot_id,
          idempotency_key: idempotencyKey,
        },
      }));
      idempotencyKeys.current.delete(candidate.snapshot_id);
      setMessage(`Private export request ${result.request_id} recorded as ${result.status}. Refresh to check its status.`);
      setRequests((current) => [
        {
          request_id: result.request_id,
          snapshot_id: candidate.snapshot_id,
          location_id: locationId,
          status: result.status,
          attempt_count: 0,
          artifact_size: null,
          created_at: result.created_at,
          updated_at: result.created_at,
          completed_at: null,
          last_error_class: null,
        },
        ...current.filter((item) => item.request_id !== result.request_id),
      ].slice(0, 50));
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setSubmittingSnapshotId("");
    }
  }

  if (sessionState.status === "loading") {
    return (
      <section aria-labelledby="report-export-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-export-heading">Private report exports</h2>
        <p role="status">Checking your operator session…</p>
      </section>
    );
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="report-export-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-export-heading">Private report exports</h2>
        <p className="lead">Sign in to view private export requests for your granted locations.</p>
        <a className="primary-action" href="/operator/auth/login?return_to=%2Fops%2Fexports&amp;prompt=select_account">Sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return (
      <section aria-labelledby="report-export-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-export-heading">Private report exports</h2>
        <p role="alert" className="migration-note">{sessionState.message}</p>
        <a className="secondary-action" href="/operator/">Open current operator console</a>
      </section>
    );
  }

  return (
    <section aria-labelledby="report-export-heading">
      <p className="eyebrow">General Operations</p>
      <h2 id="report-export-heading">Private report exports</h2>
      <p className="lead">
        Request a bounded private JSON copy of an already verified or published report snapshot.
        Exporting does not generate, verify, publish, or disclose a report to a new audience.
      </p>

      {readableLocations.length === 0 ? (
        <p role="status" className="migration-note">
          Your session has no active report-export read grants for a location.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="report-export-location">Granted location</label>
            <select
              id="report-export-location"
              value={locationId}
              onChange={(event) => {
                setLocationId(event.currentTarget.value);
                setOffset(0);
              }}
            >
              {readableLocations.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={loading || !locationId}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              {loading ? "Refreshing…" : "Refresh exports"}
            </button>
          </div>

          <p className="operator-status-line" role="status" aria-live="polite">{message}</p>

          <div className="report-export-panel">
            <div className="report-export-panel__header">
              <div>
                <h3>Reviewed snapshots</h3>
                <p>Only verified and published snapshots are listed.</p>
              </div>
              {hasMore && (
                <button
                  className="secondary-action"
                  type="button"
                  disabled={loading || offset + PAGE_SIZE > 5000}
                  onClick={() => setOffset((current) => Math.min(5000, current + PAGE_SIZE))}
                >
                  Next page
                </button>
              )}
              {offset > 0 && (
                <button
                  className="secondary-action"
                  type="button"
                  disabled={loading}
                  onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                >
                  Previous page
                </button>
              )}
            </div>
            {candidates.length === 0 ? (
              <p role="status">No exportable report snapshots are available for this location.</p>
            ) : (
              <div className="table-scroll">
                <table className="report-review-table">
                  <thead>
                    <tr>
                      <th scope="col">Report</th>
                      <th scope="col">Period</th>
                      <th scope="col">Reviewed state</th>
                      <th scope="col">Snapshot hash</th>
                      <th scope="col"><span className="visually-hidden">Action</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((candidate) => {
                      const alreadyRequested = requestedSnapshots.has(candidate.snapshot_id.toLowerCase());
                      return (
                        <tr key={candidate.snapshot_id}>
                          <td>{candidate.report_name} ({candidate.report_type || "report"})</td>
                          <td>{dateRange(candidate)}</td>
                          <td>{candidate.status}</td>
                          <td className="report-hash">{candidate.snapshot_hash}</td>
                          <td>
                            <button
                              className="secondary-action"
                              type="button"
                              disabled={!canCreate || alreadyRequested || submittingSnapshotId !== ""}
                              onClick={() => void requestExport(candidate)}
                              title={alreadyRequested
                                ? "An export request is already recorded for this snapshot."
                                : (canCreate ? undefined : "A separate report_snapshot_export:create grant is required.")}
                            >
                              {submittingSnapshotId === candidate.snapshot_id
                                ? "Requesting…"
                                : (alreadyRequested ? "Request already recorded" : "Request private export")}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {!canCreate && (
              <p className="migration-note" role="note">
                Your session can review eligible snapshots but cannot request exports without a separate
                location-scoped create grant.
              </p>
            )}
          </div>

          <div className="report-export-panel">
            <h3>Private export requests</h3>
            {requests.length === 0 ? (
              <p>No export requests are recorded for this location.</p>
            ) : (
              <div className="table-scroll">
                <table className="report-review-table">
                  <thead>
                    <tr>
                      <th scope="col">Report</th>
                      <th scope="col">Status</th>
                      <th scope="col">Attempts</th>
                      <th scope="col">Updated</th>
                      <th scope="col">Artifact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((item) => {
                      const candidate = candidates.find((entry) => entry.snapshot_id.toLowerCase() === item.snapshot_id.toLowerCase());
                      const download = new URLSearchParams({ location_id: locationId });
                      return (
                        <tr key={item.request_id}>
                          <td>{candidate?.report_name || item.snapshot_id}</td>
                          <td>
                            {item.status}
                            {item.last_error_class ? <span className="report-export-error"> · {item.last_error_class}</span> : null}
                          </td>
                          <td>{item.attempt_count}</td>
                          <td>{new Date(item.updated_at).toLocaleString()}</td>
                          <td>
                            {item.status === "completed" && canDownload ? (
                              <a
                                className="secondary-action report-export-download"
                                href={`/operator/api/report-exports/${encodeURIComponent(item.request_id)}/artifact?${download}`}
                              >
                                Download JSON
                              </a>
                            ) : item.status === "completed" ? (
                              <span>Separate download grant required</span>
                            ) : item.artifact_size ? (
                              `${item.artifact_size.toLocaleString()} bytes`
                            ) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      <p className="migration-note" role="note">
        Export requests are limited to this location and existing report snapshots. Review audience and disclosure
        before requesting an export. Private artifact access is rechecked by the Gateway; nothing is automatically
        published or sent to stakeholders.
      </p>
    </section>
  );
}
