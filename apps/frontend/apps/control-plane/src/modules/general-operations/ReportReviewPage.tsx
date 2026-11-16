import { useEffect, useMemo, useRef, useState } from "react";
import {
  GatewayRequestError,
  LatestRequest,
  operatorLocationLabel,
  requestOperatorJson,
} from "@kokonut/operator-client";
import { useOperatorSession } from "@kokonut/operator-client/react";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SUMMARY_FIELDS = [
  "created_at",
  "id",
  "location_name",
  "period_end",
  "period_start",
  "report_name",
  "report_type",
  "snapshot_hash",
  "status",
].sort().join(",");

interface SubmittedReportSummary {
  id: string;
  report_name: string;
  report_type: string | null;
  status: "submitted";
  period_start: string | null;
  period_end: string | null;
  snapshot_hash: string | null;
  created_at: string | null;
  location_name: string;
}

interface ReportReviewQueue {
  data: SubmittedReportSummary[];
  location_id: string;
}

interface SubmittedReportDetail extends SubmittedReportSummary {
  report_data: Record<string, unknown>;
}

interface SubmittedReportDetailResponse {
  data: SubmittedReportDetail;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validateSummary(value: unknown): SubmittedReportSummary {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== SUMMARY_FIELDS) {
    throw new Error("The report review response did not match its contract.");
  }

  if (
    typeof value.id !== "string" || !UUID_PATTERN.test(value.id) ||
    typeof value.report_name !== "string" ||
    !(typeof value.report_type === "string" || value.report_type === null) ||
    value.status !== "submitted" ||
    !(typeof value.period_start === "string" || value.period_start === null) ||
    !(typeof value.period_end === "string" || value.period_end === null) ||
    !(typeof value.snapshot_hash === "string" || value.snapshot_hash === null) ||
    !(typeof value.created_at === "string" || value.created_at === null) ||
    typeof value.location_name !== "string"
  ) {
    throw new Error("The report review response did not match its contract.");
  }

  return value as unknown as SubmittedReportSummary;
}

function validateQueue(value: unknown, locationId: string): ReportReviewQueue {
  if (
    !isRecord(value) ||
    Object.keys(value).sort().join(",") !== "data,location_id" ||
    typeof value.location_id !== "string" ||
    value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !Array.isArray(value.data) ||
    value.data.length > 50
  ) {
    throw new Error("The report review queue did not match the selected location.");
  }

  return {
    location_id: value.location_id,
    data: value.data.map(validateSummary),
  };
}

function validateDetail(value: unknown, reportId: string): SubmittedReportDetailResponse {
  if (!isRecord(value) || Object.keys(value).join(",") !== "data" || !isRecord(value.data)) {
    throw new Error("The submitted report did not match its response contract.");
  }

  const { report_data: reportData, ...summaryValue } = value.data;
  const summary = validateSummary(summaryValue);
  if (
    summary.id.toLowerCase() !== reportId.toLowerCase() ||
    !isRecord(reportData)
  ) {
    throw new Error("The submitted report did not match the selected report.");
  }

  return { data: { ...summary, report_data: reportData } };
}

function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

function queueErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your report review grant for this location is no longer active.";
    if (error.status === 503) return "The report review service is temporarily unavailable. Try again shortly.";
    return error.message;
  }
  return error instanceof Error ? error.message : "The report review queue is unavailable.";
}

function detailErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your report review grant for this location is no longer active.";
    if (error.status === 404) return "This submitted report is no longer available for review.";
    if (error.status === 413) return "This report is larger than the private review limit.";
  }
  return error instanceof Error ? error.message : "The submitted report could not be loaded.";
}

export function ReportReviewPage() {
  const queueRequest = useRef(new LatestRequest());
  const detailRequest = useRef(new LatestRequest());
  const sessionState = useOperatorSession();
  const session = sessionState.status === "ready" ? sessionState.session : null;
  const [locationId, setLocationId] = useState("");
  const [queue, setQueue] = useState<SubmittedReportSummary[]>([]);
  const [queueMessage, setQueueMessage] = useState("");
  const [queueLoading, setQueueLoading] = useState(false);
  const [detail, setDetail] = useState<SubmittedReportDetail | null>(null);
  const [detailMessage, setDetailMessage] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const grantedLocations = useMemo(() => {
    if (!session) return [];
    return [...new Set(session.scopes
      .filter((scope) => scope.resource === "report_snapshot_review" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [session]);

  useEffect(() => {
    if (!grantedLocations.length) {
      setLocationId("");
      setQueue([]);
      setQueueMessage("");
      setDetail(null);
      setDetailMessage("");
      return;
    }

    setLocationId((current) => grantedLocations.includes(current) ? current : grantedLocations[0]);
  }, [grantedLocations]);

  useEffect(() => {
    detailRequest.current.cancel();
    setDetail(null);
    setDetailMessage("");

    if (!locationId) {
      setQueue([]);
      setQueueMessage("");
      setQueueLoading(false);
      return;
    }

    const request = queueRequest.current.begin();
    const params = new URLSearchParams({ location_id: locationId, limit: "50" });
    setQueue([]);
    setQueueMessage("Loading submitted reports…");
    setQueueLoading(true);

    void requestOperatorJson<unknown>(`/operator/api/report-review-queue?${params}`, {
      signal: request.signal,
    })
      .then((payload) => {
        if (!request.isCurrent()) return;
        const result = validateQueue(payload, locationId);
        setQueue(result.data);
        setQueueMessage(result.data.length
          ? `${result.data.length} submitted report${result.data.length === 1 ? "" : "s"}.`
          : "No submitted reports for this location.");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || isAbortError(error)) return;
        setQueue([]);
        setQueueMessage(queueErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setQueueLoading(false);
      });

    return () => queueRequest.current.cancel();
  }, [locationId, refreshVersion]);

  async function openReport(reportId: string) {
    if (!locationId) return;
    const request = detailRequest.current.begin();
    const params = new URLSearchParams({ location_id: locationId });
    setDetail(null);
    setDetailMessage("Loading report content…");
    setDetailLoading(true);

    try {
      const payload = await requestOperatorJson<unknown>(
        `/operator/api/report-review-queue/${encodeURIComponent(reportId)}?${params}`,
        { signal: request.signal },
      );
      if (!request.isCurrent()) return;
      const result = validateDetail(payload, reportId);
      setDetail(result.data);
      setDetailMessage("Report loaded in read-only mode.");
    } catch (error) {
      if (!request.isCurrent() || isAbortError(error)) return;
      setDetail(null);
      setDetailMessage(detailErrorMessage(error));
    } finally {
      if (request.isCurrent()) setDetailLoading(false);
    }
  }

  if (sessionState.status === "loading") {
    return (
      <section aria-labelledby="report-review-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-review-heading">Submitted report review</h2>
        <p role="status">Checking your operator session…</p>
      </section>
    );
  }

  if (sessionState.status === "signed-out") {
    return (
      <section aria-labelledby="report-review-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-review-heading">Submitted report review</h2>
        <p className="lead">Sign in to view report reviews for your granted locations.</p>
        <a className="primary-action" href="/operator/auth/login?return_to=%2Fops%2Freports&amp;prompt=select_account">Sign in</a>
      </section>
    );
  }

  if (sessionState.status === "error") {
    return (
      <section aria-labelledby="report-review-heading">
        <p className="eyebrow">General Operations</p>
        <h2 id="report-review-heading">Submitted report review</h2>
        <p role="alert" className="migration-note">{sessionState.message}</p>
        <a className="secondary-action" href="/operator/">Open current operator console</a>
      </section>
    );
  }

  return (
    <section aria-labelledby="report-review-heading">
      <p className="eyebrow">General Operations</p>
      <h2 id="report-review-heading">Submitted report review</h2>
      <p className="lead">
        Read submitted report snapshots for locations granted to your operator
        session. This view cannot verify, reject, or publish reports.
      </p>

      {grantedLocations.length === 0 ? (
        <p role="status" className="migration-note">
          Your session has no active report review location grants.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="report-review-location">Granted location</label>
            <select
              id="report-review-location"
              value={locationId}
              onChange={(event) => setLocationId(event.currentTarget.value)}
            >
              {grantedLocations.map((id) => <option key={id} value={id}>{operatorLocationLabel(sessionState.session.locations, id)}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={queueLoading}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              {queueLoading ? "Refreshing…" : "Refresh queue"}
            </button>
          </div>

          <p className="operator-status-line" role="status" aria-live="polite">
            {queueMessage}
          </p>

          <div className="table-scroll">
            <table className="report-review-table">
              <thead>
                <tr>
                  <th scope="col">Report</th>
                  <th scope="col">Period</th>
                  <th scope="col">Submitted</th>
                  <th scope="col">Snapshot hash</th>
                  <th scope="col"><span className="visually-hidden">Action</span></th>
                </tr>
              </thead>
              <tbody>
                {queue.map((report) => (
                  <tr key={report.id}>
                    <td>{report.report_name} ({report.report_type || "report"})</td>
                    <td>{[report.period_start, report.period_end].filter(Boolean).join(" – ") || "—"}</td>
                    <td>{report.created_at ? new Date(report.created_at).toLocaleString() : "—"}</td>
                    <td className="report-hash">{report.snapshot_hash || "—"}</td>
                    <td>
                      <button
                        className="secondary-action"
                        type="button"
                        disabled={detailLoading}
                        onClick={() => void openReport(report.id)}
                      >
                        Read report
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {detailMessage && (
            <p className="operator-status-line" role="status" aria-live="polite">
              {detailMessage}
            </p>
          )}
          {detail && (
            <section className="report-detail" aria-labelledby="report-detail-heading">
              <h3 id="report-detail-heading">{detail.report_name}</h3>
              <p>{detail.location_name} · Submitted report · Read-only</p>
              <pre>{JSON.stringify(detail.report_data, null, 2)}</pre>
            </section>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        Access is rechecked by the Gateway for every request. Existing operator
        workflows remain available in the <a href="/operator/">current console</a>.
      </p>
    </section>
  );
}
