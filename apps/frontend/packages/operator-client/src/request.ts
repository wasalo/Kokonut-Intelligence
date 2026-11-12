const OPERATOR_CSRF_COOKIE = "kokonut_operator_csrf";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
let cachedOperatorCsrfToken = "";

export interface OperatorScope {
  resource: string;
  action: string;
  location_id: string;
}

export interface OperatorLocationOption {
  id: string;
  name: string;
  country: string | null;
  region: string | null;
}

export interface OperatorSession {
  operator: {
    operator_id: string;
    issuer: string;
    subject: string;
    display_name: string | null;
    email: string | null;
  };
  scopes: OperatorScope[];
  locations: OperatorLocationOption[];
}

export function operatorLocationLabel(locations: OperatorLocationOption[], locationId: string): string {
  const location = locations.find((option) => option.id.toLowerCase() === locationId.toLowerCase());
  if (!location) return "Location unavailable";
  const context = [location.region, location.country].filter((part): part is string => Boolean(part?.trim()));
  return context.length ? `${location.name} · ${context.join(", ")}` : location.name;
}

export interface OperatorJsonRequestOptions
  extends Omit<RequestInit, "body" | "method"> {
  method?: string;
  body?: unknown;
}

export class GatewayRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "GatewayRequestError";
  }
}

function readCsrfCookie(): string {
  const prefix = `${OPERATOR_CSRF_COOKIE}=`;
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  if (!item) return "";

  try {
    return decodeURIComponent(item.slice(prefix.length));
  } catch {
    return "";
  }
}

function validateOperatorPath(path: string, method: string): URL {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new GatewayRequestError(
      "Operator requests must use a same-origin absolute path.",
      0,
      "invalid_path",
      false,
    );
  }

  const url = new URL(path, window.location.origin);
  const operatorApiPath = url.pathname.startsWith("/operator/api/");
  const sessionRead = method === "GET" && url.pathname === "/operator/auth/session";
  const sessionLogout = method === "POST" && url.pathname === "/operator/auth/logout";

  if (
    url.origin !== window.location.origin ||
    url.hash ||
    !(operatorApiPath || sessionRead || sessionLogout)
  ) {
    throw new GatewayRequestError(
      "This path is outside the operator Gateway API.",
      0,
      "path_not_allowed",
      false,
    );
  }

  return url;
}

function responseMessage(value: unknown, status: number): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    for (const key of ["error", "detail", "message"]) {
      if (typeof record[key] === "string" && record[key].trim()) {
        return record[key].trim().slice(0, 500);
      }
    }
  }

  return `The request failed (${status}).`;
}

function errorCode(value: unknown, status: number): string {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const code = (value as Record<string, unknown>).code;
    if (typeof code === "string" && /^[a-z0-9_.-]{1,80}$/i.test(code)) {
      return code;
    }
  }

  return `http_${status}`;
}

export async function requestOperatorJson<T>(
  path: string,
  options: OperatorJsonRequestOptions = {},
): Promise<T> {
  const method = (options.method ?? (options.body === undefined ? "GET" : "POST"))
    .toUpperCase();
  const url = validateOperatorPath(path, method);
  const headers = new Headers(options.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  let body: string | undefined;
  if (options.body !== undefined) {
    if (SAFE_METHODS.has(method)) {
      throw new GatewayRequestError(
        "Safe operator requests cannot include a request body.",
        0,
        "body_not_allowed",
        false,
      );
    }
    try {
      const serialized = JSON.stringify(options.body);
      if (serialized === undefined) throw new TypeError("Body is not JSON serializable");
      body = serialized;
    } catch {
      throw new GatewayRequestError(
        "The request body could not be encoded as JSON.",
        0,
        "invalid_request_body",
        false,
      );
    }
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  if (!SAFE_METHODS.has(method)) {
    const csrf = readCsrfCookie() || cachedOperatorCsrfToken;
    if (!csrf) {
      throw new GatewayRequestError(
        "Refresh the page to establish a protected operator session before saving.",
        0,
        "csrf_token_missing",
        false,
      );
    }
    headers.set("X-CSRF-Token", csrf);
  }

  let response: Response;
  try {
    response = await fetch(`${url.pathname}${url.search}`, {
      ...options,
      method,
      headers,
      body,
      credentials: "same-origin",
      cache: "no-store",
      mode: "same-origin",
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new GatewayRequestError(
      "The service could not be reached. Check your connection and try again.",
      0,
      "network_error",
      true,
    );
  }

  if (url.pathname === "/operator/auth/session") {
    const token = response.headers.get("X-Operator-CSRF-Token") ?? "";
    cachedOperatorCsrfToken = response.ok && /^[A-Za-z0-9_-]{1,128}$/.test(token)
      ? token
      : "";
  } else if (response.status === 401) {
    cachedOperatorCsrfToken = "";
  }

  const responseText = await response.text();
  let payload: unknown;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch {
      if (response.ok) {
        throw new GatewayRequestError(
          "The service returned an unreadable response.",
          response.status,
          "invalid_response",
          response.status >= 500,
        );
      }
    }
  }

  if (!response.ok) {
    throw new GatewayRequestError(
      responseMessage(payload, response.status),
      response.status,
      errorCode(payload, response.status),
      response.status === 429 || response.status >= 500,
    );
  }

  return payload as T;
}

export async function signOutOperatorSession(): Promise<void> {
  const result = await requestOperatorJson<unknown>("/operator/auth/logout", {
    method: "POST",
  });
  if (
    result === null ||
    typeof result !== "object" ||
    Array.isArray(result) ||
    (result as Record<string, unknown>).status !== "signed_out"
  ) {
    throw new GatewayRequestError(
      "The operator session could not be closed.",
      200,
      "invalid_logout_response",
      false,
    );
  }
}
