import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { test } from "node:test";
import vaultModule from "../services/mobile/field-collector-vault.js";

const { EncryptedVault, createIndexedDbAdapter, createStateWriter, defaultVaultState } = vaultModule;
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

function immediateCompletionIndexedDb() {
  const values = new Map();
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
    close() {},
  };
  return {
    open() {
      const request = { result: database };
      queueMicrotask(() => request.onsuccess?.());
      return request;
    },
  };
}

test("IndexedDB adapter observes completion even when it follows request success immediately", { timeout: 2000 }, async () => {
  const adapter = createIndexedDbAdapter(immediateCompletionIndexedDb());
  const envelope = { version: 1, ciphertext: "opaque" };
  await adapter.put(envelope);
  assert.deepEqual(await adapter.get(), envelope);
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
