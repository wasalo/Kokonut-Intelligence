import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { test } from "node:test";
import vaultModule from "../services/mobile/field-collector-vault.js";

const {
  EncryptedVault,
  createIndexedDbAdapter,
  createStateWriter,
  defaultVaultState,
  quarantineQueueForOwnerReview,
  requiresOwnerReview,
} = vaultModule;
const PASSPHRASE = "field notes stay private";

class MemoryAdapter {
  value = null;
  failWrite = false;

  async get() {
    return this.value;
  }

  async put(value) {
    if (this.failWrite) throw new Error("simulated persistence failure");
    this.value = value;
  }
}

class MemoryStorage {
  values = new Map();

  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

const makeVault = adapter => new EncryptedVault(adapter, webcrypto, { iterations: 1000 });

function immediateCompletionIndexedDb({ blockedDelete = false } = {}) {
  const values = new Map();
  let closed = false;
  const database = {
    objectStoreNames: { contains: () => true },
    transaction() {
      const transaction = {
        objectStore() {
          return {
            get(key) {
              const request = {};
              queueMicrotask(() => {
                request.result = values.get(key);
                request.onsuccess?.();
                transaction.oncomplete?.();
              });
              return request;
            },
            put(value, key) {
              const request = {};
              queueMicrotask(() => {
                values.set(key, structuredClone(value));
                request.onsuccess?.();
                transaction.oncomplete?.();
              });
              return request;
            },
          };
        },
        close() {},
      };
      return transaction;
    },
    close() { closed = true; },
  };
  return {
    open() {
      const request = { result: database };
      queueMicrotask(() => request.onsuccess?.());
      return request;
    },
    deleteDatabase() {
      const request = {};
      queueMicrotask(() => {
        if (blockedDelete) request.onblocked?.();
        values.clear();
        request.onsuccess?.();
      });
      return request;
    },
    triggerVersionChange() { database.onversionchange?.(); },
    get closed() { return closed; },
  };
}

test("IndexedDB adapter observes completion even when it follows request success immediately", { timeout: 2000 }, async () => {
  const adapter = createIndexedDbAdapter(immediateCompletionIndexedDb());
  const envelope = { version: 1, ciphertext: "opaque" };
  await adapter.put(envelope);
  assert.deepEqual(await adapter.get(), envelope);
});

test("IndexedDB adapter deletes the vault and can reopen an empty database", async () => {
  const indexedDb = immediateCompletionIndexedDb();
  const adapter = createIndexedDbAdapter(indexedDb);
  const envelope = { version: 1, ciphertext: "opaque" };
  await adapter.put(envelope);
  await adapter.deleteDatabase();
  assert.equal(indexedDb.closed, true);
  assert.equal(await adapter.get(), null);
});

test("IndexedDB adapter reports a blocked vault deletion", async () => {
  const indexedDb = immediateCompletionIndexedDb({ blockedDelete: true });
  const adapter = createIndexedDbAdapter(indexedDb);
  let notified = 0;
  await adapter.deleteDatabase(() => { notified += 1; });
  assert.equal(notified, 1);
  assert.equal(await adapter.get(), null);
});

test("IndexedDB version changes close storage and notify the application", async () => {
  const indexedDb = immediateCompletionIndexedDb();
  let notified = 0;
  const adapter = createIndexedDbAdapter(indexedDb, () => { notified += 1; });
  await adapter.get();
  indexedDb.triggerVersionChange();
  assert.equal(indexedDb.closed, true);
  assert.equal(notified, 1);
});

test("vault encrypts state, locks in memory, rejects a wrong passphrase, and unlocks", async () => {
  const adapter = new MemoryAdapter();
  const vault = makeVault(adapter);
  await vault.unlock(PASSPHRASE);
  const state = {
    ...defaultVaultState(),
    device: { device_id: "browser-1", device_token: "opaque-device-secret" },
    queue: [{ client_id: "c1", payload: { observation: "private field note" } }],
  };
  await vault.saveState(state);

  const envelope = await adapter.get();
  assert.equal(envelope.version, 1);
  assert.equal(envelope.ciphertext.includes("opaque-device-secret"), false);
  assert.equal(envelope.ciphertext.includes("private field note"), false);
  vault.lock();
  assert.equal(vault.isUnlocked(), false);
  assert.throws(() => vault.getState(), /locked/i);

  const wrong = makeVault(adapter);
  await assert.rejects(() => wrong.unlock("a different passphrase"), /passphrase|decrypt/i);
  assert.equal(wrong.isUnlocked(), false);

  const reopened = makeVault(adapter);
  await reopened.unlock(PASSPHRASE);
  assert.deepEqual(reopened.getState().queue, state.queue);
  assert.deepEqual(reopened.getState().device, state.device);
});

test("serialized state updates preserve concurrent queue additions", async () => {
  const vault = makeVault(new MemoryAdapter());
  await vault.unlock(PASSPHRASE);
  const writeState = createStateWriter(vault);
  await Promise.all([
    writeState(state => ({ ...state, queue: [...state.queue, "first"] })),
    writeState(state => ({ ...state, queue: [...state.queue, "second"] })),
  ]);
  assert.deepEqual(vault.getState().queue, ["first", "second"]);
});

test("owner transfer quarantines queued records without changing payloads or photos", async () => {
  const originalQueue = [{
    client_id: "old-device-record",
    origin_device_id: null,
    payload: { observation: "private field note" },
    offline_photos: [{ name: "soil.jpg", data: "data:image/jpeg;base64,cGhvdG8=" }],
    photo_refs: ["8aa53daa-c1e9-4be4-b68d-3799eefcf910"],
  }];
  const queue = quarantineQueueForOwnerReview(originalQueue, "old-device");

  assert.deepEqual(queue[0].payload, originalQueue[0].payload);
  assert.deepEqual(queue[0].offline_photos, originalQueue[0].offline_photos);
  assert.deepEqual(queue[0].photo_refs, originalQueue[0].photo_refs);
  assert.equal(queue[0].origin_device_id, "old-device");
  assert.equal(queue[0].tenant_review_required, true);
  assert.equal(requiresOwnerReview(queue[0], "new-owner-device"), true);
  assert.equal(requiresOwnerReview({ origin_device_id: "old-device" }, "new-owner-device"), true);
  assert.equal(requiresOwnerReview({ origin_device_id: "new-owner-device" }, "new-owner-device"), false);

  const adapter = new MemoryAdapter();
  const vault = makeVault(adapter);
  await vault.unlock(PASSPHRASE);
  await vault.saveState({
    ...defaultVaultState(),
    device: null,
    queue,
    settings: { apiBase: "https://api.example", deviceName: "Field phone", ownerReenrollmentRequired: true },
  });
  vault.lock();

  const reopened = makeVault(adapter);
  await reopened.unlock(PASSPHRASE);
  assert.deepEqual(reopened.getState().queue, queue);
  assert.equal(reopened.getState().settings.ownerReenrollmentRequired, true);
});

test("legacy localStorage data migrates only after encrypted persistence verifies", async () => {
  const adapter = new MemoryAdapter();
  const legacy = new MemoryStorage();
  legacy.setItem("kokonut_field_device", JSON.stringify({ device_id: "old", device_token: "legacy-token" }));
  legacy.setItem("kokonut_field_queue", JSON.stringify([{ client_id: "q1", payload: { note: "legacy note" } }]));
  legacy.setItem("kokonut_field_settings", JSON.stringify({ apiBase: "https://api.example", userId: "caller-value", locationId: "caller-location", deviceName: "Phone" }));

  const vault = makeVault(adapter);
  await vault.unlock(PASSPHRASE, legacy);
  assert.equal(vault.getState().device.device_token, "legacy-token");
  assert.equal(vault.getState().queue[0].payload.note, "legacy note");
  assert.equal(vault.getState().settings.apiBase, "https://api.example");
  assert.equal("userId" in vault.getState().settings, false);
  assert.equal("locationId" in vault.getState().settings, false);
  assert.equal(legacy.getItem("kokonut_field_device"), null);
  assert.equal(legacy.getItem("kokonut_field_queue"), null);
  assert.equal(legacy.getItem("kokonut_field_settings"), null);
  assert.equal((await adapter.get()).ciphertext.includes("legacy-token"), false);
});

test("unlocking an existing vault preserves coexisting legacy data that was not migrated", async () => {
  const adapter = new MemoryAdapter();
  const first = makeVault(adapter);
  await first.unlock(PASSPHRASE);
  const legacy = new MemoryStorage();
  const original = JSON.stringify({ device_id: "old", device_token: "legacy-token" });
  legacy.setItem("kokonut_field_device", original);

  const reopened = makeVault(adapter);
  await reopened.unlock(PASSPHRASE, legacy);
  assert.equal(legacy.getItem("kokonut_field_device"), original);
  assert.equal(reopened.legacyDataPreserved, true);
});

test("failed legacy migration leaves all original localStorage values intact", async () => {
  const adapter = new MemoryAdapter();
  adapter.failWrite = true;
  const legacy = new MemoryStorage();
  const original = JSON.stringify({ device_id: "old", device_token: "legacy-token" });
  legacy.setItem("kokonut_field_device", original);

  const vault = makeVault(adapter);
  await assert.rejects(() => vault.unlock(PASSPHRASE, legacy), /persistence failure/);
  assert.equal(legacy.getItem("kokonut_field_device"), original);
  assert.equal(vault.isUnlocked(), false);
});
