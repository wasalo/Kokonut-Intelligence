import assert from "node:assert/strict";
import test from "node:test";

import { runMonitorCycle } from "../infra/cloudflare/health-alert/src/monitoring.mjs";

class MemoryStorage {
  value = null;

  async get(_key) {
    return this.value === null ? null : structuredClone(this.value);
  }

  async put(_key, value) {
    this.value = structuredClone(value);
  }
}

class CrashBeforeFinalSendStorage extends MemoryStorage {
  crashed = false;

  async put(key, value) {
    await super.put(key, value);
    const pending = value.outbox[0];
    if (!this.crashed && pending?.attempts === 3 && pending.nextAttemptAt === null) {
      this.crashed = true;
      throw new Error("simulated worker termination before final send");
    }
  }
}

async function cycle(storage, now, healthy, sendEmail) {
  return runMonitorCycle({
    storage,
    now,
    healthCheck: async () => ({ healthy, statusCode: healthy ? 200 : 503 }),
    sendEmail,
  });
}

test("confirmed outage and recovery each send once after their configured windows", async () => {
  const storage = new MemoryStorage();
  const delivered = [];
  const sendEmail = async event => {
    delivered.push(event.kind);
    return { ok: true };
  };
  const start = 1_000_000;

  assert.equal((await cycle(storage, start, false, sendEmail)).transition, "failure_observed");
  assert.equal((await cycle(storage, start + 119_999, false, sendEmail)).notification, "none");

  const outage = await cycle(storage, start + 120_000, false, sendEmail);
  assert.equal(outage.transition, "outage_confirmed");
  assert.equal(outage.notification, "accepted");
  assert.deepEqual(delivered, ["outage"]);

  const ongoing = await cycle(storage, start + 180_000, false, sendEmail);
  assert.equal(ongoing.transition, "none");
  assert.equal(ongoing.notification, "none");
  assert.deepEqual(delivered, ["outage"], "an ongoing outage must not repeat email");

  assert.equal(
    (await cycle(storage, start + 240_000, true, sendEmail)).transition,
    "recovery_observed",
  );
  assert.equal((await cycle(storage, start + 539_999, true, sendEmail)).notification, "none");

  const recovery = await cycle(storage, start + 540_000, true, sendEmail);
  assert.equal(recovery.transition, "recovery_confirmed");
  assert.equal(recovery.notification, "accepted");
  assert.deepEqual(delivered, ["outage", "recovery"]);
  assert.equal(recovery.pendingNotifications, 0);
});

test("transient email failures use bounded retries and eventually leave the outbox", async () => {
  const storage = new MemoryStorage();
  const attempts = [];
  const sendEmail = async event => {
    attempts.push(event.kind);
    return { ok: false, retryable: true, reason: "test_provider_unavailable" };
  };
  const start = 2_000_000;

  await cycle(storage, start, false, sendEmail);
  const first = await cycle(storage, start + 120_000, false, sendEmail);
  assert.equal(first.notification, "retry_scheduled");
  assert.equal(first.pendingNotifications, 1);

  const beforeFirstRetry = await cycle(storage, start + 419_999, false, sendEmail);
  assert.equal(beforeFirstRetry.notification, "none");
  assert.equal(attempts.length, 1);

  const second = await cycle(storage, start + 420_000, false, sendEmail);
  assert.equal(second.notification, "retry_scheduled");
  assert.equal(second.pendingNotifications, 1);

  const beforeSecondRetry = await cycle(storage, start + 1_319_999, false, sendEmail);
  assert.equal(beforeSecondRetry.notification, "none");
  assert.equal(attempts.length, 2);

  const third = await cycle(storage, start + 1_320_000, false, sendEmail);
  assert.equal(third.notification, "abandoned");
  assert.equal(third.pendingNotifications, 0);
  assert.equal(attempts.length, 3);
  assert.equal(storage.value.lastDeliveryFailure.attempts, 3);
});

test("a restart after the final attempt is claimed does not send beyond the retry limit", async () => {
  const storage = new CrashBeforeFinalSendStorage();
  let sendCount = 0;
  const sendEmail = async () => {
    sendCount += 1;
    return { ok: false, retryable: true, reason: "test_provider_unavailable" };
  };
  const start = 3_000_000;

  await cycle(storage, start, false, sendEmail);
  await cycle(storage, start + 120_000, false, sendEmail);
  await cycle(storage, start + 420_000, false, sendEmail);

  await assert.rejects(
    cycle(storage, start + 1_320_000, false, sendEmail),
    /simulated worker termination/,
  );
  assert.equal(sendCount, 2, "the claimed final attempt has not crossed the email boundary");

  const afterRestart = await cycle(storage, start + 1_320_000, false, sendEmail);
  assert.equal(afterRestart.notification, "abandoned");
  assert.equal(afterRestart.pendingNotifications, 0);
  assert.equal(sendCount, 2, "an uncertain final attempt must not be resent after restart");
  assert.equal(storage.value.lastDeliveryFailure.reason, "delivery_attempt_outcome_unknown");
});
