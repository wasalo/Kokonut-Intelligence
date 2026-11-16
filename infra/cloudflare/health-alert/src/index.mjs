import { DurableObject } from "cloudflare:workers";
import { runMonitorCycle } from "./monitoring.mjs";

const INTERNAL_CHECK_PATH = "/internal/health-check";
const HEALTH_TIMEOUT_MS = 10_000;
const EMAIL_TIMEOUT_MS = 15_000;
const MAX_RESPONSE_BYTES = 4_096;

function internalJson(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

async function boundedText(response) {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > MAX_RESPONSE_BYTES) {
    await response.body?.cancel().catch(() => {});
    return null;
  }

  if (!response.body) return "";
  const reader = response.body.getReader();
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(bytes);
}

function validHealthUrl(value) {
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      url.hostname === "hub.kokonut.network" &&
      url.pathname === "/health/ready" &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash
    );
  } catch {
    return false;
  }
}

async function checkCandidateReadiness(env) {
  if (!validHealthUrl(env.HEALTH_URL)) {
    return { healthy: false, statusCode: null };
  }

  try {
    const response = await fetch(env.HEALTH_URL, {
      method: "GET",
      redirect: "manual",
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      headers: {
        accept: "application/json",
        "cache-control": "no-cache",
      },
    });
    if (!response.ok || response.status !== 200) {
      await response.body?.cancel().catch(() => {});
      return { healthy: false, statusCode: response.status };
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.toLowerCase().includes("application/json")) {
      await response.body?.cancel().catch(() => {});
      return { healthy: false, statusCode: response.status };
    }

    const body = await boundedText(response);
    if (body === null) {
      return { healthy: false, statusCode: response.status };
    }
    const payload = JSON.parse(body);
    return {
      healthy: payload?.status === "ready",
      statusCode: response.status,
    };
  } catch {
    return { healthy: false, statusCode: null };
  }
}

function emailContent(event, env) {
  const eventTime = new Date(event.occurredAt).toISOString();
  if (event.kind === "outage") {
    const observed = Number.isInteger(event.statusCode)
      ? `HTTP ${event.statusCode}`
      : "no HTTP response";
    return {
      subject: "[Kokonut Intelligence] Readiness check is failing",
      plain: [
        "Kokonut Intelligence has failed its confirmed readiness checks.",
        "",
        `Endpoint: ${env.HEALTH_URL}`,
        `First failed check: ${eventTime}`,
        `Latest failed response: ${observed}`,
        "",
        "Please inspect the independent Better Stack monitor and the candidate services. Follow the existing manual responder contact procedure.",
      ].join("\n"),
    };
  }

  return {
    subject: "[Kokonut Intelligence] Readiness check recovered",
    plain: [
      "Kokonut Intelligence has passed its confirmed recovery checks.",
      "",
      `Endpoint: ${env.HEALTH_URL}`,
      `Recovered at: ${eventTime}`,
      "",
      "Please confirm service health in the independent Better Stack monitor.",
    ].join("\n"),
  };
}

async function sendMailerooEmail(event, env) {
  if (!env.MAILEROO_API_KEY || !env.ALERT_EMAIL_FROM || !env.ALERT_EMAIL_TO) {
    return { ok: false, retryable: true, reason: "mail_configuration_missing" };
  }

  const content = emailContent(event, env);
  try {
    const response = await fetch("https://smtp.maileroo.com/api/v2/emails", {
      method: "POST",
      redirect: "error",
      signal: AbortSignal.timeout(EMAIL_TIMEOUT_MS),
      headers: {
        "content-type": "application/json",
        "x-api-key": env.MAILEROO_API_KEY,
      },
      body: JSON.stringify({
        from: {
          address: env.ALERT_EMAIL_FROM,
          display_name: env.ALERT_EMAIL_FROM_NAME || "Kokonut Intelligence Monitor",
        },
        to: [{ address: env.ALERT_EMAIL_TO }],
        subject: content.subject,
        plain: content.plain,
        tracking: false,
      }),
    });

    if (response.status === 200) {
      const body = await boundedText(response);
      let payload;
      try {
        payload = body === null ? null : JSON.parse(body);
      } catch {
        payload = null;
      }
      return payload?.success === true
        ? { ok: true }
        : { ok: false, retryable: false, reason: "mail_response_invalid" };
    }

    await response.body?.cancel().catch(() => {});
    const retryable = response.status === 429 || response.status >= 500;
    const retryAfterSeconds = Number(response.headers.get("retry-after"));
    return {
      ok: false,
      retryable,
      reason: retryable ? "mail_provider_unavailable" : "mail_provider_rejected",
      retryAfterMs: Number.isFinite(retryAfterSeconds)
        ? retryAfterSeconds * 1_000
        : undefined,
    };
  } catch {
    return { ok: false, retryable: true, reason: "mail_network_error" };
  }
}

export default {
  async fetch() {
    return new Response("Not found", {
      status: 404,
      headers: { "cache-control": "no-store" },
    });
  },

  async scheduled(controller, env) {
    const id = env.MONITOR_STATE.idFromName("kokonut-candidate-readiness");
    const monitor = env.MONITOR_STATE.get(id);
    const result = await monitor.fetch(
      new Request("https://monitor.internal/internal/health-check", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scheduledAt: controller.scheduledTime }),
      }),
    );
    if (!result.ok) {
      throw new Error(`health monitor state request failed (${result.status})`);
    }

    const summary = await result.json();
    console.log(
      JSON.stringify({
        event: "candidate_health_monitor_cycle",
        health: summary.health,
        statusCode: summary.statusCode,
        transition: summary.transition,
        notification: summary.notification,
        pendingNotifications: summary.pendingNotifications,
        suppressedNotificationCount: summary.suppressedNotificationCount,
      }),
    );
  },
};

export class MonitorState extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.inFlight = Promise.resolve();
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname !== INTERNAL_CHECK_PATH) {
      return internalJson({ error: "not_found" }, 404);
    }
    if (request.method !== "POST") {
      return internalJson({ error: "method_not_allowed" }, 405);
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return internalJson({ error: "invalid_request" }, 400);
    }
    if (!Number.isFinite(body?.scheduledAt) || body.scheduledAt < 0) {
      return internalJson({ error: "invalid_request" }, 400);
    }

    const cycle = this.inFlight.then(() =>
      runMonitorCycle({
        storage: this.ctx.storage,
        now: Math.max(Date.now(), body.scheduledAt),
        healthCheck: () => checkCandidateReadiness(this.env),
        sendEmail: (event) => sendMailerooEmail(event, this.env),
      }),
    );
    this.inFlight = cycle.then(
      () => undefined,
      () => undefined,
    );
    const result = await cycle;
    return internalJson(result);
  }
}
