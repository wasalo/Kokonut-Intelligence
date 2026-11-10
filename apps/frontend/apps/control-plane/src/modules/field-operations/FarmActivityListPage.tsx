import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
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
const DRAFT_WRITE_FIELDS = [
  "activity_date",
  "activity_type",
  "created_at",
  "crop_cycle_id",
  "description",
  "event_id",
  "evidence_urls",
  "farm_task_id",
  "id",
  "labor_cost",
  "labor_hours",
  "location_id",
  "materials_used",
  "notes",
  "plot_id",
  "source_system",
  "status",
  "updated_at",
].sort().join(",");
const DETAIL_FIELDS = [
  "activity_date",
  "activity_type",
  "created_at",
  "crop_cycle_id",
  "description",
  "evidence_urls",
  "farm_task_id",
  "id",
  "labor_cost",
  "labor_hours",
  "location_id",
  "materials_used",
  "notes",
  "operator_events",
  "plot_id",
  "source_system",
  "status",
  "updated_at",
].sort().join(",");
const EVENT_FIELDS = [
  "action",
  "actor_operator_id",
  "changed_fields",
  "created_at",
  "from_status",
  "reason",
  "to_status",
].sort().join(",");
const TRANSITION_FIELDS = [
  "action",
  "activity_id",
  "created_at",
  "event_id",
  "from_status",
  "location_id",
  "reason",
  "to_status",
].sort().join(",");
const FARM_ACTIVITY_ACTIONS = [
  "submit",
  "verify",
  "reject",
  "request-rework",
  "publish",
  "close-exception",
] as const;
const EVENT_ACTIONS = [
  "draft_created",
  "draft_edited",
  "submitted",
  "verified",
  "published",
  "rejected",
  "rework_requested",
  "exception_closed",
] as const;
const CHANGED_FIELDS = [
  "plot_id",
  "crop_cycle_id",
  "farm_task_id",
  "activity_type",
  "activity_date",
  "description",
  "labor_hours",
  "labor_cost",
  "materials_used",
  "evidence_urls",
  "notes",
] as const;
const ACTION_GRANTS: Record<FarmActivityAction, string> = {
  submit: "submit",
  verify: "verify",
  reject: "reject",
  "request-rework": "rework",
  publish: "publish",
  "close-exception": "close_exception",
};
const ACTION_LABELS: Record<FarmActivityAction, string> = {
  submit: "Submit for review",
  verify: "Verify",
  reject: "Reject for rework",
  "request-rework": "Request rework",
  publish: "Publish",
  "close-exception": "Close exception",
};
const ACTION_RESULT_STATUS: Record<FarmActivityAction, FarmActivityRecord["status"]> = {
  submit: "submitted",
  verify: "verified",
  reject: "rejected",
  "request-rework": "draft",
  publish: "published",
  "close-exception": "rejected",
};
const REASON_REQUIRED_ACTIONS = new Set<FarmActivityAction>([
  "reject",
  "request-rework",
  "close-exception",
]);
const STATUS_ACTIONS: Record<FarmActivityRecord["status"], FarmActivityAction[]> = {
  draft: ["submit"],
  submitted: ["verify", "reject"],
  verified: ["publish", "reject"],
  rejected: ["request-rework", "close-exception"],
  published: [],
};

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

type FarmActivityAction = typeof FARM_ACTIVITY_ACTIONS[number];
type FarmActivityEventAction = typeof EVENT_ACTIONS[number];
type FarmActivityChangedField = typeof CHANGED_FIELDS[number];

interface FarmActivityOperatorEvent {
  action: FarmActivityEventAction;
  actor_operator_id: string;
  changed_fields: FarmActivityChangedField[] | null;
  created_at: string;
  from_status: FarmActivityRecord["status"] | null;
  reason: string | null;
  to_status: FarmActivityRecord["status"];
}

interface FarmActivityDetail extends FarmActivityRecord {
  description: string | null;
  labor_hours: number | string | null;
  labor_cost: number | string | null;
  materials_used: unknown;
  evidence_urls: Array<string | null> | null;
  notes: string | null;
  operator_events: FarmActivityOperatorEvent[];
}

interface FarmActivityTransition {
  event_id: string;
  activity_id: string;
  location_id: string;
  action: FarmActivityEventAction;
  from_status: FarmActivityRecord["status"] | null;
  to_status: FarmActivityRecord["status"];
  reason: string | null;
  created_at: string;
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

function localDateToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function validateDraftWrite(
  value: unknown,
  locationId: string,
  activityType: string,
  activityDate: string,
): string {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "data" || !isRecord(value.data)) {
    throw new Error("The save response could not be confirmed. Refresh the records before retrying.");
  }

  const draft = value.data;
  const isNullableUuid = (candidate: unknown) => candidate === null ||
    (typeof candidate === "string" && UUID_PATTERN.test(candidate));
  const isDecimalOrNull = (candidate: unknown) => candidate === null ||
    (typeof candidate === "number" && Number.isFinite(candidate)) ||
    (typeof candidate === "string" && /^\d+(?:\.\d+)?$/.test(candidate));

  if (
    Object.keys(draft).sort().join(",") !== DRAFT_WRITE_FIELDS ||
    typeof draft.id !== "string" || !UUID_PATTERN.test(draft.id) ||
    typeof draft.event_id !== "string" || !UUID_PATTERN.test(draft.event_id) ||
    typeof draft.location_id !== "string" || draft.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !isNullableUuid(draft.plot_id) || !isNullableUuid(draft.crop_cycle_id) || !isNullableUuid(draft.farm_task_id) ||
    draft.activity_type !== activityType || draft.activity_date !== activityDate ||
    draft.status !== "draft" || draft.source_system !== "kokonut_gateway" ||
    !(draft.description === null || typeof draft.description === "string") ||
    !(draft.notes === null || typeof draft.notes === "string") ||
    !isDecimalOrNull(draft.labor_hours) || !isDecimalOrNull(draft.labor_cost) ||
    !(Array.isArray(draft.materials_used) || isRecord(draft.materials_used)) ||
    !(Array.isArray(draft.evidence_urls) && draft.evidence_urls.every((url) => url === null || typeof url === "string")) ||
    !isTimestamp(draft.created_at) || !isTimestamp(draft.updated_at)
  ) {
    throw new Error("The save response could not be confirmed. Refresh the records before retrying.");
  }

  return draft.id;
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

function isActivityStatus(value: unknown): value is FarmActivityRecord["status"] {
  return value === "draft" || value === "submitted" || value === "verified" ||
    value === "published" || value === "rejected";
}

function isNullableText(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isDecimalOrNull(value: unknown): value is number | string | null {
  return value === null || (typeof value === "number" && Number.isFinite(value)) ||
    (typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value));
}

function validateDetail(value: unknown, activityId: string, locationId: string): FarmActivityDetail {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== "data" || !isRecord(value.data)) {
    throw new Error("The farm activity detail did not match the selected record.");
  }
  const detail = value.data;
  if (
    Object.keys(detail).sort().join(",") !== DETAIL_FIELDS ||
    typeof detail.id !== "string" || detail.id.toLowerCase() !== activityId.toLowerCase() ||
    typeof detail.location_id !== "string" || detail.location_id.toLowerCase() !== locationId.toLowerCase() ||
    !isUuidOrNull(detail.plot_id) || !isUuidOrNull(detail.crop_cycle_id) || !isUuidOrNull(detail.farm_task_id) ||
    typeof detail.activity_type !== "string" || !detail.activity_type.trim() || detail.activity_type.length > 100 ||
    !isDate(detail.activity_date) || !isActivityStatus(detail.status) ||
    !(detail.source_system === null || typeof detail.source_system === "string") ||
    detail.source_system === "field_collector" ||
    !isNullableText(detail.description) || !isNullableText(detail.notes) ||
    !isDecimalOrNull(detail.labor_hours) || !isDecimalOrNull(detail.labor_cost) ||
    !(detail.evidence_urls === null || (Array.isArray(detail.evidence_urls) &&
      detail.evidence_urls.every((url) => url === null || typeof url === "string"))) ||
    !(detail.created_at === null || isTimestamp(detail.created_at)) ||
    !(detail.updated_at === null || isTimestamp(detail.updated_at)) ||
    !Array.isArray(detail.operator_events) || detail.operator_events.length > 100
  ) {
    throw new Error("The farm activity detail did not match the selected location and record.");
  }

  for (const event of detail.operator_events) {
    if (
      !isRecord(event) || Object.keys(event).sort().join(",") !== EVENT_FIELDS ||
      !(EVENT_ACTIONS as readonly unknown[]).includes(event.action) ||
      typeof event.actor_operator_id !== "string" || !UUID_PATTERN.test(event.actor_operator_id) ||
      !(event.from_status === null || isActivityStatus(event.from_status)) ||
      !isActivityStatus(event.to_status) || !isNullableText(event.reason) || !isTimestamp(event.created_at) ||
      !(event.changed_fields === null || (Array.isArray(event.changed_fields) &&
        event.changed_fields.every((field) => (CHANGED_FIELDS as readonly unknown[]).includes(field))))
    ) {
      throw new Error("The farm activity audit history did not match its response contract.");
    }
  }

  return detail as unknown as FarmActivityDetail;
}

function validateTransition(
  value: unknown,
  action: FarmActivityAction,
  activityId: string,
  locationId: string,
): FarmActivityTransition {
  if (!isRecord(value) || Object.keys(value).sort().join(",") !== TRANSITION_FIELDS) {
    throw new Error("The lifecycle decision could not be confirmed. Refresh the record before retrying.");
  }
  const expectedAction: Record<FarmActivityAction, FarmActivityEventAction> = {
    submit: "submitted",
    verify: "verified",
    reject: "rejected",
    "request-rework": "rework_requested",
    publish: "published",
    "close-exception": "exception_closed",
  };
  const expectedStatuses: Record<FarmActivityAction, [FarmActivityRecord["status"] | null, FarmActivityRecord["status"]]> = {
    submit: ["draft", "submitted"],
    verify: ["submitted", "verified"],
    reject: [null, "rejected"],
    "request-rework": ["rejected", "draft"],
    publish: ["verified", "published"],
    "close-exception": ["rejected", "rejected"],
  };
  const expected = expectedStatuses[action];
  const hasRequiredReason = typeof value.reason === "string" && Boolean(value.reason.trim());
  const fromStatusIsValid = action === "reject"
    ? value.from_status === "submitted" || value.from_status === "verified"
    : value.from_status === expected[0];
  if (
    typeof value.event_id !== "string" || !UUID_PATTERN.test(value.event_id) ||
    typeof value.activity_id !== "string" || value.activity_id.toLowerCase() !== activityId.toLowerCase() ||
    typeof value.location_id !== "string" || value.location_id.toLowerCase() !== locationId.toLowerCase() ||
    value.action !== expectedAction[action] || !fromStatusIsValid || value.to_status !== expected[1] ||
    !isNullableText(value.reason) || !isTimestamp(value.created_at) ||
    (REASON_REQUIRED_ACTIONS.has(action) && !hasRequiredReason)
  ) {
    throw new Error("The lifecycle decision response did not match the requested location, record, or transition.");
  }
  return value as unknown as FarmActivityTransition;
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

function detailErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.status === 401) return "Your operator session has expired. Sign in again to continue.";
    if (error.status === 403) return "Your exact location farm-activity detail grant is no longer active.";
    if (error.status === 404) return "This farm activity detail is unavailable for the selected location.";
    if (error.status === 503) return "Farm activity detail is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error ? error.message : "Farm activity detail could not be loaded.";
}

function draftRequestErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.code === "network_error" || error.code === "invalid_response") {
      return "The save could not be confirmed. Refresh or reload the page before retrying to avoid a duplicate draft.";
    }
    if (error.status === 401) return "Your operator session has expired. Sign in again before saving.";
    if (error.status === 403) return "Your exact location draft-entry grant is no longer active.";
    if (error.status === 503) return "Farm activity is temporarily unavailable. Refresh records before retrying.";
    return error.message;
  }
  return error instanceof Error
    ? error.message
    : "The draft could not be confirmed. Refresh records before retrying.";
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

function transitionErrorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError) {
    if (error.code === "network_error" || error.code === "invalid_response") {
      return "The decision could not be confirmed. Refresh the record before retrying.";
    }
    if (error.status === 401) return "Your operator session has expired. Sign in again before deciding.";
    if (error.status === 403) return "Your location does not have an active grant for this decision.";
    if (error.status === 404) return "The record or required location grant is no longer available.";
    if (error.status === 409) return "The record changed state. Refresh it before choosing another action.";
    if (error.status >= 500) return "The decision service is temporarily unavailable. The record was refreshed; review its current status before retrying.";
  }
  return error instanceof Error ? error.message : "The lifecycle decision could not be completed.";
}

export function FarmActivityListPage() {
  const sessionState = useOperatorSession();
  const listRequest = useRef(new LatestRequest());
  const detailRequest = useRef(new LatestRequest());
  const [locationId, setLocationId] = useState("");
  const [records, setRecords] = useState<FarmActivityRecord[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [activityType, setActivityType] = useState("");
  const [activityDate, setActivityDate] = useState(localDateToday);
  const [description, setDescription] = useState("");
  const [laborHours, setLaborHours] = useState("");
  const [laborCost, setLaborCost] = useState("");
  const [notes, setNotes] = useState("");
  const [draftFormDirty, setDraftFormDirty] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftFeedback, setDraftFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [selectedRecordId, setSelectedRecordId] = useState("");
  const [selectedDetail, setSelectedDetail] = useState<FarmActivityDetail | null>(null);
  const [detailMessage, setDetailMessage] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [transitionReason, setTransitionReason] = useState("");
  const [actionToConfirm, setActionToConfirm] = useState<FarmActivityAction | null>(null);
  const [transitionBusy, setTransitionBusy] = useState(false);
  const [transitionFeedback, setTransitionFeedback] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const grantedLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.action === "read")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  const draftableLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    const detailLocations = new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.action === "read_detail")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)));
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.action === "create_draft")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id) && detailLocations.has(id)))];
  }, [sessionState]);

  const detailableLocations = useMemo(() => {
    if (sessionState.status !== "ready") return [];
    return [...new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.action === "read_detail")
      .map((scope) => scope.location_id.toLowerCase())
      .filter((id) => UUID_PATTERN.test(id)))];
  }, [sessionState]);

  const locationActions = useMemo(() => {
    if (sessionState.status !== "ready" || !UUID_PATTERN.test(locationId)) return new Set<string>();
    return new Set(sessionState.session.scopes
      .filter((scope) => scope.resource === "farm_activity" && scope.location_id.toLowerCase() === locationId)
      .map((scope) => scope.action));
  }, [locationId, sessionState]);

  const selectableLocations = useMemo(
    () => [...new Set([...grantedLocations, ...draftableLocations])].sort(),
    [draftableLocations, grantedLocations],
  );

  useEffect(() => {
    if (!selectableLocations.length) {
      setLocationId("");
      setRecords([]);
      setMessage("");
      return;
    }
    setLocationId((current) => selectableLocations.includes(current) ? current : selectableLocations[0]);
  }, [selectableLocations]);

  useEffect(() => {
    if (!locationId || !grantedLocations.includes(locationId)) {
      setRecords([]);
      setMessage(locationId && draftableLocations.includes(locationId)
        ? "This location permits draft entry, but your session has no farm-activity read grant."
        : "");
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
  }, [draftableLocations, grantedLocations, locationId, refreshVersion]);

  useEffect(() => {
    if (!selectedRecordId || !locationId || !detailableLocations.includes(locationId)) {
      detailRequest.current.cancel();
      setSelectedDetail(null);
      setDetailMessage("");
      setDetailLoading(false);
      return;
    }

    const request = detailRequest.current.begin();
    const params = new URLSearchParams({ location_id: locationId });
    setSelectedDetail(null);
    setDetailMessage("Loading farm activity detail…");
    setDetailLoading(true);
    setActionToConfirm(null);

    void requestOperatorJson<unknown>(
      `/operator/api/farm-activity-records/${encodeURIComponent(selectedRecordId)}?${params}`,
      { signal: request.signal },
    )
      .then((payload) => {
        if (!request.isCurrent()) return;
        setSelectedDetail(validateDetail(payload, selectedRecordId, locationId));
        setDetailMessage("");
      })
      .catch((error: unknown) => {
        if (!request.isCurrent() || isAbortError(error)) return;
        setSelectedDetail(null);
        setDetailMessage(detailErrorMessage(error));
      })
      .finally(() => {
        if (request.isCurrent()) setDetailLoading(false);
      });

    return () => detailRequest.current.cancel();
  }, [detailableLocations, locationId, refreshVersion, selectedRecordId]);

  const currentDetail = selectedDetail &&
    selectedDetail.id.toLowerCase() === selectedRecordId.toLowerCase() &&
    selectedDetail.location_id.toLowerCase() === locationId
    ? selectedDetail
    : null;

  async function submitDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setDraftFeedback(null);
    if (!draftableLocations.includes(locationId)) {
      setDraftFeedback({ kind: "error", text: "Choose a location with an active draft-entry grant." });
      return;
    }
    const parsedHours = laborHours.trim() ? Number(laborHours) : null;
    const parsedCost = laborCost.trim() ? Number(laborCost) : null;
    const hasAtMostTwoDecimals = (value: number) => Math.abs(value * 100 - Math.round(value * 100)) < 1e-8;
    const normalizedActivityType = activityType.trim();
    if (!normalizedActivityType || normalizedActivityType.length > 100 || !isDate(activityDate)) {
      setDraftFeedback({ kind: "error", text: "Enter an activity name and a valid activity date." });
      return;
    }
    if (
      (parsedHours !== null && (!Number.isFinite(parsedHours) || parsedHours < 0 || parsedHours > 999999.99 || !hasAtMostTwoDecimals(parsedHours))) ||
      (parsedCost !== null && (!Number.isFinite(parsedCost) || parsedCost < 0 || parsedCost > 9999999999.99 || !hasAtMostTwoDecimals(parsedCost)))
    ) {
      setDraftFeedback({ kind: "error", text: "Labor values must be non-negative and use at most two decimal places." });
      return;
    }

    setSavingDraft(true);
    const content = {
      activity_type: normalizedActivityType,
      activity_date: activityDate,
      description: description.trim() || null,
      labor_hours: parsedHours,
      labor_cost: parsedCost,
      notes: notes.trim() || null,
    };

    try {
      const params = new URLSearchParams({ location_id: locationId });
      const payload = await requestOperatorJson<unknown>(`/operator/api/farm-activity-records?${params}`, {
        method: "POST",
        body: { content },
      });
      const draftId = validateDraftWrite(payload, locationId, normalizedActivityType, activityDate);
      setActivityType("");
      setActivityDate(localDateToday());
      setDescription("");
      setLaborHours("");
      setLaborCost("");
      setNotes("");
      setDraftFormDirty(false);
      setDraftFeedback({ kind: "success", text: `Draft saved. Record ${draftId} remains unsubmitted and unverified.` });
      if (grantedLocations.includes(locationId)) setRefreshVersion((version) => version + 1);
    } catch (error) {
      setDraftFeedback({ kind: "error", text: draftRequestErrorMessage(error) });
    } finally {
      setSavingDraft(false);
    }
  }

  async function transitionRecord(action: FarmActivityAction) {
    if (
      !currentDetail ||
      !selectedRecordId ||
      actionToConfirm !== action ||
      !locationActions.has(ACTION_GRANTS[action]) ||
      !STATUS_ACTIONS[currentDetail.status].includes(action) ||
      currentDetail.operator_events.some((event) => event.action === "exception_closed")
    ) return;
    const reason = transitionReason.trim();
    if (REASON_REQUIRED_ACTIONS.has(action) && !reason) {
      setTransitionFeedback({ kind: "error", text: "Enter a reason before recording this decision." });
      return;
    }

    setTransitionBusy(true);
    setTransitionFeedback(null);
    try {
      const params = new URLSearchParams({ location_id: locationId });
      const payload = await requestOperatorJson<unknown>(
        `/operator/api/farm-activity-records/${encodeURIComponent(selectedRecordId)}/${action}?${params}`,
        { method: "POST", body: reason ? { reason } : {} },
      );
      const transition = validateTransition(payload, action, selectedRecordId, locationId);
      setTransitionReason("");
      setActionToConfirm(null);
      setTransitionFeedback({
        kind: "success",
        text: `Decision recorded. The record is now ${statusLabel(transition.to_status)}.`,
      });
      setRefreshVersion((version) => version + 1);
    } catch (error) {
      setTransitionFeedback({ kind: "error", text: transitionErrorMessage(error) });
      setActionToConfirm(null);
      setTransitionReason("");
      setRefreshVersion((version) => version + 1);
    } finally {
      setTransitionBusy(false);
    }
  }

  const exceptionClosed = currentDetail?.operator_events.some((event) => event.action === "exception_closed") ?? false;
  const availableActions = currentDetail && !exceptionClosed
    ? STATUS_ACTIONS[currentDetail.status].filter((action) => locationActions.has(ACTION_GRANTS[action]))
    : [];

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
        Record location-scoped farm activities and review non-Collector entries and their governed status.
      </p>

      {selectableLocations.length === 0 ? (
        <p className="migration-note" role="status">
          Your operator session has no location-scoped farm-activity read or draft-entry grants. No record request was made.
        </p>
      ) : (
        <>
          <div className="location-filter-toolbar">
            <label htmlFor="farm-activity-location">Authorized location</label>
            <select
              id="farm-activity-location"
              value={locationId}
              disabled={savingDraft || draftFormDirty || transitionBusy}
              onChange={(event) => {
                setSelectedRecordId("");
                setSelectedDetail(null);
                setActionToConfirm(null);
                setTransitionFeedback(null);
                setLocationId(event.currentTarget.value);
              }}
            >
              {selectableLocations.map((id) => <option key={id} value={id}>{id}</option>)}
            </select>
            <button
              className="secondary-action"
              type="button"
              disabled={loading || !grantedLocations.includes(locationId)}
              onClick={() => setRefreshVersion((version) => version + 1)}
            >
              Refresh records
            </button>
          </div>
          {draftFormDirty && (
            <p className="migration-note" role="note">Clear the unsaved form before switching locations.</p>
          )}

          {draftableLocations.includes(locationId) && (
            <form className="farm-activity-draft-form" onSubmit={submitDraft}>
              <h3>Record a farm activity</h3>
              <p className="lead">Save a location-scoped draft. This does not submit, verify, or publish the activity.</p>
              <div className="farm-activity-form-grid">
                <div className="farm-activity-field">
                  <label htmlFor="farm-activity-type">Activity</label>
                  <input
                    id="farm-activity-type"
                    value={activityType}
                    onChange={(event) => { setDraftFormDirty(true); setActivityType(event.currentTarget.value); }}
                    disabled={savingDraft}
                    required
                    maxLength={100}
                  />
                </div>
                <div className="farm-activity-field">
                  <label htmlFor="farm-activity-date">Activity date</label>
                  <input
                    id="farm-activity-date"
                    type="date"
                    value={activityDate}
                    onChange={(event) => { setDraftFormDirty(true); setActivityDate(event.currentTarget.value); }}
                    disabled={savingDraft}
                    required
                  />
                </div>
                <div className="farm-activity-field">
                  <label htmlFor="farm-activity-hours">Labor hours</label>
                  <input
                    id="farm-activity-hours"
                    type="number"
                    min="0"
                    max="999999.99"
                    step="0.01"
                    value={laborHours}
                    onChange={(event) => { setDraftFormDirty(true); setLaborHours(event.currentTarget.value); }}
                    disabled={savingDraft}
                  />
                </div>
                <div className="farm-activity-field">
                  <label htmlFor="farm-activity-cost">Labor cost</label>
                  <input
                    id="farm-activity-cost"
                    type="number"
                    min="0"
                    max="9999999999.99"
                    step="0.01"
                    value={laborCost}
                    onChange={(event) => { setDraftFormDirty(true); setLaborCost(event.currentTarget.value); }}
                    disabled={savingDraft}
                  />
                </div>
                <div className="farm-activity-field farm-activity-field-wide">
                  <label htmlFor="farm-activity-description">Description</label>
                  <textarea
                    id="farm-activity-description"
                    value={description}
                    onChange={(event) => { setDraftFormDirty(true); setDescription(event.currentTarget.value); }}
                    disabled={savingDraft}
                    maxLength={10000}
                    rows={3}
                  />
                </div>
                <div className="farm-activity-field farm-activity-field-wide">
                  <label htmlFor="farm-activity-notes">Notes</label>
                  <textarea
                    id="farm-activity-notes"
                    value={notes}
                    onChange={(event) => { setDraftFormDirty(true); setNotes(event.currentTarget.value); }}
                    disabled={savingDraft}
                    maxLength={10000}
                    rows={3}
                  />
                </div>
              </div>
              <div className="farm-activity-form-actions">
                <button
                  className="primary-action"
                  type="submit"
                  disabled={savingDraft || !locationId}
                >
                  {savingDraft ? "Saving draft…" : "Save draft"}
                </button>
                <button
                  className="secondary-action"
                  type="button"
                  disabled={savingDraft || !draftFormDirty}
                  onClick={() => {
                    setActivityType("");
                    setActivityDate(localDateToday());
                    setDescription("");
                    setLaborHours("");
                    setLaborCost("");
                    setNotes("");
                    setDraftFormDirty(false);
                    setDraftFeedback(null);
                  }}
                >
                  Clear fields
                </button>
                {draftFeedback && (
                  <p className="operator-status-line" role={draftFeedback.kind === "error" ? "alert" : "status"} aria-live="polite">
                    {draftFeedback.text}
                  </p>
                )}
              </div>
              <p className="migration-note" role="note">
                Supporting files and offline Collector submissions use separate workflows and are not attached by this form.
              </p>
            </form>
          )}

          {!grantedLocations.includes(locationId) && (
            <p className="migration-note" role="status">This session can create drafts here but cannot read the farm activity list for this location.</p>
          )}

          {grantedLocations.includes(locationId) && (
            <>
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
                      {detailableLocations.includes(locationId) && (
                        <button
                          className="secondary-action"
                          type="button"
                          disabled={detailLoading || transitionBusy || selectedRecordId === record.id}
                          onClick={() => {
                            setTransitionFeedback(null);
                            setActionToConfirm(null);
                            setTransitionReason("");
                            setDetailMessage("Loading farm activity detail…");
                            setSelectedRecordId(record.id);
                          }}
                        >
                          {selectedRecordId === record.id ? "Details open" : "Open details and review"}
                        </button>
                      )}
                    </article>
                  ))}
                </div>
              )}

              {selectedRecordId && detailableLocations.includes(locationId) && (
                <section className="farm-activity-review" aria-labelledby="farm-activity-review-heading">
                  <h3 id="farm-activity-review-heading">Farm activity detail and lifecycle</h3>
                  {detailMessage && <p className="operator-status-line" role="status" aria-live="polite">{detailMessage}</p>}
                  {currentDetail && (
                    <>
                      <p><strong>{currentDetail.activity_type}</strong> · {currentDetail.activity_date} · {statusLabel(currentDetail.status)}</p>
                      <dl>
                        <div><dt>Description</dt><dd>{currentDetail.description || "None"}</dd></div>
                        <div><dt>Labor hours</dt><dd>{currentDetail.labor_hours ?? "Not recorded"}</dd></div>
                        <div><dt>Labor cost</dt><dd>{currentDetail.labor_cost ?? "Not recorded"}</dd></div>
                        <div><dt>Notes</dt><dd>{currentDetail.notes || "None"}</dd></div>
                        <div><dt>Materials</dt><dd><pre>{JSON.stringify(currentDetail.materials_used, null, 2)}</pre></dd></div>
                        <div><dt>Evidence URLs</dt><dd>{currentDetail.evidence_urls?.filter((url): url is string => Boolean(url)).join("\n") || "None"}</dd></div>
                      </dl>
                      <h4>Decision history</h4>
                      {currentDetail.operator_events.length ? (
                        <ol>
                          {currentDetail.operator_events.map((event, index) => (
                            <li key={`${event.action}-${event.created_at}-${index}`}>
                              <strong>{event.action.replaceAll("_", " ")}</strong> · {new Date(event.created_at).toLocaleString()}
                              {event.reason ? <p>{event.reason}</p> : null}
                              {event.changed_fields?.length ? <p>Changed fields: {event.changed_fields.join(", ")}</p> : null}
                              <small>Operator {event.actor_operator_id}</small>
                            </li>
                          ))}
                        </ol>
                      ) : <p>No lifecycle decisions have been recorded.</p>}

                      {availableActions.length > 0 ? (
                        <div className="farm-activity-lifecycle-actions">
                          <div className="farm-activity-form-actions">
                            {availableActions.map((action) => (
                              <button
                                className={action === "publish" ? "primary-action" : "secondary-action"}
                                key={action}
                                type="button"
                                disabled={transitionBusy || detailLoading || actionToConfirm !== null}
                                onClick={() => {
                                  setTransitionFeedback(null);
                                  setTransitionReason("");
                                  setActionToConfirm(action);
                                }}
                              >
                                {ACTION_LABELS[action]}
                              </button>
                            ))}
                          </div>
                          {actionToConfirm && (
                            <div className="farm-activity-decision-confirmation" role="group" aria-label="Confirm farm activity decision">
                              <p>
                                Confirm “{ACTION_LABELS[actionToConfirm]}”. The record will become {statusLabel(ACTION_RESULT_STATUS[actionToConfirm])}.
                              </p>
                              {REASON_REQUIRED_ACTIONS.has(actionToConfirm) && (
                                <div className="farm-activity-field farm-activity-field-wide">
                                  <label htmlFor="farm-activity-transition-reason">Decision reason (required)</label>
                                  <textarea
                                    id="farm-activity-transition-reason"
                                    value={transitionReason}
                                    onChange={(event) => setTransitionReason(event.currentTarget.value)}
                                    maxLength={2000}
                                    rows={3}
                                    disabled={transitionBusy}
                                  />
                                </div>
                              )}
                              <div className="farm-activity-form-actions">
                                <button
                                  className={actionToConfirm === "publish" ? "primary-action" : "secondary-action"}
                                  type="button"
                                  disabled={transitionBusy || detailLoading}
                                  onClick={() => void transitionRecord(actionToConfirm)}
                                >
                                  {transitionBusy ? "Recording decision…" : `Confirm ${ACTION_LABELS[actionToConfirm].toLowerCase()}`}
                                </button>
                                <button
                                  className="secondary-action"
                                  type="button"
                                  disabled={transitionBusy}
                                  onClick={() => {
                                    setActionToConfirm(null);
                                    setTransitionReason("");
                                    setTransitionFeedback(null);
                                  }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="migration-note" role="note">
                          No further lifecycle action is available to this session for the record’s current status.
                        </p>
                      )}
                    </>
                  )}
                  {transitionFeedback && (
                    <p className="operator-status-line" role={transitionFeedback.kind === "error" ? "alert" : "status"} aria-live="polite">
                      {transitionFeedback.text}
                    </p>
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}

      <p className="migration-note" role="note">
        This page excludes Field Collector submissions. Detail and lifecycle actions appear only when the session has the matching location-scoped grant; the Gateway and database still enforce every transition.
      </p>
    </section>
  );
}
