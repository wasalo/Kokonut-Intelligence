import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { GatewayRequestError } from "./request";
import { LatestRequest } from "./latest-request";
import { requestOperatorJson } from "./request";
import type { OperatorScope, OperatorSession } from "./request";

export type OperatorSessionState =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "ready"; session: OperatorSession }
  | { status: "error"; message: string };

const OperatorSessionContext = createContext<OperatorSessionState | null>(null);

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isOperatorScope(value: unknown): value is OperatorScope {
  return isRecord(value) &&
    typeof value.resource === "string" &&
    typeof value.action === "string" &&
    typeof value.location_id === "string";
}

function parseOperatorSession(value: unknown): OperatorSession {
  if (!isRecord(value) || !isRecord(value.operator) || !Array.isArray(value.scopes)) {
    throw new Error("The operator session response is invalid.");
  }

  const operator = value.operator;
  if (
    typeof operator.operator_id !== "string" ||
    typeof operator.issuer !== "string" ||
    typeof operator.subject !== "string" ||
    !(typeof operator.display_name === "string" || operator.display_name === null) ||
    !(typeof operator.email === "string" || operator.email === null) ||
    !value.scopes.every(isOperatorScope)
  ) {
    throw new Error("The operator session response is invalid.");
  }

  return {
    operator: operator as OperatorSession["operator"],
    scopes: value.scopes,
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof GatewayRequestError && error.status === 503) {
    return "The operator session service is temporarily unavailable. Try again shortly.";
  }
  return error instanceof Error
    ? error.message
    : "The operator session could not be loaded.";
}

/** Shares one browser-session lookup across every route in the Control Plane. */
export function OperatorSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<OperatorSessionState>({ status: "loading" });
  const request = useRef(new LatestRequest());

  useEffect(() => {
    const current = request.current.begin();
    void requestOperatorJson<unknown>("/operator/auth/session", {
      signal: current.signal,
    })
      .then((payload) => {
        if (!current.isCurrent()) return;
        setState({ status: "ready", session: parseOperatorSession(payload) });
      })
      .catch((error: unknown) => {
        if (!current.isCurrent() || (error instanceof Error && error.name === "AbortError")) {
          return;
        }
        if (error instanceof GatewayRequestError && error.status === 401) {
          setState({ status: "signed-out" });
          return;
        }
        setState({ status: "error", message: errorMessage(error) });
      });

    return () => request.current.cancel();
  }, []);

  return createElement(OperatorSessionContext.Provider, { value: state }, children);
}

/** Reads the shared operator session; participant/device auth stays separate. */
export function useOperatorSession(): OperatorSessionState {
  const state = useContext(OperatorSessionContext);
  if (state === null) {
    throw new Error("useOperatorSession must be used within OperatorSessionProvider");
  }
  return state;
}
