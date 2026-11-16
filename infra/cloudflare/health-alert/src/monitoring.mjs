const STATE_KEY = "monitor-state";
const STATE_VERSION = 1;
const MAX_PENDING_NOTIFICATIONS = 16;
const MAX_DELIVERY_ATTEMPTS = 3;
const RETRY_DELAYS_MS = [5 * 60_000, 15 * 60_000];

export const FAILURE_CONFIRMATION_MS = 2 * 60_000;
export const RECOVERY_CONFIRMATION_MS = 5 * 60_000;

function initialState() {
  return {
    version: STATE_VERSION,
    failureSince: null,
    outageSince: null,
    recoverySince: null,
    lastObservedAt: 0,
    lastHealth: "unknown",
    outbox: [],
    lastDelivered: null,
    lastDeliveryFailure: null,
    suppressedNotificationCount: 0,
  };
}

function validateState(state) {
  return (
    state &&
    state.version === STATE_VERSION &&
    (state.failureSince === null || Number.isFinite(state.failureSince)) &&
    (state.outageSince === null || Number.isFinite(state.outageSince)) &&
    (state.recoverySince === null || Number.isFinite(state.recoverySince)) &&
    Number.isFinite(state.lastObservedAt) &&
    Array.isArray(state.outbox) &&
    state.outbox.length <= MAX_PENDING_NOTIFICATIONS &&
    state.outbox.every(
      (item) =>
        item &&
        ["outage", "recovery"].includes(item.kind) &&
        Number.isFinite(item.occurredAt) &&
        Number.isInteger(item.attempts) &&
        item.attempts >= 0 &&
        item.attempts <= MAX_DELIVERY_ATTEMPTS &&
        (item.nextAttemptAt === null || Number.isFinite(item.nextAttemptAt)) &&
        (item.nextAttemptAt !== null || item.attempts === MAX_DELIVERY_ATTEMPTS),
    )
  );
}

function queueNotification(state, event) {
  if (state.outbox.length >= MAX_PENDING_NOTIFICATIONS) {
    state.suppressedNotificationCount += 1;
    return false;
  }

  state.outbox.push({
    ...event,
    attempts: 0,
    nextAttemptAt: event.confirmedAt,
  });
  return true;
}

function observe(state, observation, now) {
  let transition = "none";
  let notificationQueued = false;

  state.lastObservedAt = now;
  state.lastHealth = observation.healthy ? "healthy" : "unhealthy";

  if (observation.healthy) {
    state.failureSince = null;

    if (state.outageSince === null) {
      state.recoverySince = null;
      return { transition, notificationQueued };
    }

    if (state.recoverySince === null) {
      state.recoverySince = now;
      return { transition: "recovery_observed", notificationQueued };
    }

    if (now - state.recoverySince < RECOVERY_CONFIRMATION_MS) {
      return { transition, notificationQueued };
    }

    notificationQueued = queueNotification(state, {
      kind: "recovery",
      occurredAt: now,
      incidentStartedAt: state.outageSince,
      confirmedAt: now,
    });
    state.outageSince = null;
    state.recoverySince = null;
    transition = "recovery_confirmed";
    return { transition, notificationQueued };
  }

  state.recoverySince = null;
  if (state.outageSince !== null) {
    return { transition, notificationQueued };
  }

  if (state.failureSince === null) {
    state.failureSince = now;
    return { transition: "failure_observed", notificationQueued };
  }

  if (now - state.failureSince < FAILURE_CONFIRMATION_MS) {
    return { transition, notificationQueued };
  }

  const incidentStartedAt = state.failureSince;
  notificationQueued = queueNotification(state, {
    kind: "outage",
    occurredAt: incidentStartedAt,
    confirmedAt: now,
    statusCode: observation.statusCode,
  });
  state.outageSince = incidentStartedAt;
  state.failureSince = null;
  transition = "outage_confirmed";
  return { transition, notificationQueued };
}

function retryDelay(attempt) {
  return RETRY_DELAYS_MS[Math.min(attempt - 1, RETRY_DELAYS_MS.length - 1)];
}

function recordDeliveryFailure(state, event, now, reason) {
  state.lastDeliveryFailure = {
    kind: event.kind,
    occurredAt: event.occurredAt,
    at: now,
    attempts: event.attempts,
    reason,
  };
}

async function attemptPendingNotification({ state, storage, now, sendEmail }) {
  const event = state.outbox[0];
  if (!event) return "none";

  // The final attempt is persisted before crossing the external email
  // boundary. After a Worker restart, a null due time means its result is
  // uncertain; abandon rather than risk sending a duplicate final alert.
  if (event.attempts >= MAX_DELIVERY_ATTEMPTS || event.nextAttemptAt === null) {
    state.outbox.shift();
    recordDeliveryFailure(state, event, now, "delivery_attempt_outcome_unknown");
    await storage.put(STATE_KEY, state);
    return "abandoned";
  }

  if (event.nextAttemptAt > now) {
    return "none";
  }

  event.attempts += 1;
  event.nextAttemptAt =
    event.attempts < MAX_DELIVERY_ATTEMPTS
      ? now + retryDelay(event.attempts)
      : null;

  // Persist the bounded retry before crossing the external email boundary.
  // A worker restart cannot turn one outage into an unbounded send loop.
  await storage.put(STATE_KEY, state);

  let result;
  try {
    result = await sendEmail(event);
  } catch {
    result = { ok: false, retryable: true, reason: "mail_network_error" };
  }

  if (result?.ok === true) {
    state.outbox.shift();
    state.lastDelivered = {
      kind: event.kind,
      occurredAt: event.occurredAt,
      acceptedAt: now,
      attempts: event.attempts,
    };
    await storage.put(STATE_KEY, state);
    return "accepted";
  }

  const retryable = result?.retryable === true;
  if (!retryable || event.attempts >= MAX_DELIVERY_ATTEMPTS) {
    state.outbox.shift();
    recordDeliveryFailure(
      state,
      event,
      now,
      typeof result?.reason === "string" ? result.reason : "mail_failed",
    );
    await storage.put(STATE_KEY, state);
    return "abandoned";
  }

  const providerDelay = Number.isFinite(result?.retryAfterMs)
    ? Math.max(0, Math.min(result.retryAfterMs, 60 * 60_000))
    : 0;
  event.nextAttemptAt = Math.max(event.nextAttemptAt, now + providerDelay);
  await storage.put(STATE_KEY, state);
  return "retry_scheduled";
}

/**
 * Run one health observation and, if due, one bounded email-outbox attempt.
 * Fetch/email functions are injected so this state machine remains testable
 * without live provider calls.
 */
export async function runMonitorCycle({
  storage,
  now,
  healthCheck,
  sendEmail,
}) {
  if (!Number.isFinite(now) || now < 0) {
    throw new TypeError("monitor time must be a non-negative timestamp");
  }

  const stored = await storage.get(STATE_KEY);
  const state = stored === undefined || stored === null ? initialState() : stored;
  if (!validateState(state)) {
    throw new Error("health monitor state is invalid");
  }

  const effectiveNow = Math.max(now, state.lastObservedAt);
  let observation;
  try {
    observation = await healthCheck();
  } catch {
    observation = { healthy: false, statusCode: null };
  }
  if (typeof observation?.healthy !== "boolean") {
    throw new TypeError("health check must return a boolean healthy value");
  }

  const observed = observe(state, observation, effectiveNow);
  await storage.put(STATE_KEY, state);

  const notification = await attemptPendingNotification({
    state,
    storage,
    now: effectiveNow,
    sendEmail,
  });

  return {
    health: state.lastHealth,
    statusCode: Number.isInteger(observation.statusCode)
      ? observation.statusCode
      : null,
    transition: observed.transition,
    notificationQueued: observed.notificationQueued,
    notification,
    pendingNotifications: state.outbox.length,
    suppressedNotificationCount: state.suppressedNotificationCount,
  };
}
